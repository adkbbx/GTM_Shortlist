from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, field_validator
from starlette.concurrency import run_in_threadpool
from starlette.middleware.trustedhost import TrustedHostMiddleware

from shortlist.auth import AuthenticationError, AuthUnavailable, verify_user
from shortlist.config import Settings
from shortlist.domain import OperatorReview, Profile, Research, Review, Target
from shortlist.export import export_run
from shortlist.fetch import canonical_url
from shortlist.local_credentials import (
    CredentialUnavailable,
    LocalCredentials,
    apply_local_credentials,
    validate_tavily_key,
)
from shortlist.progress import RunProgress
from shortlist.providers import SellerDraft
from shortlist.store import BudgetExceeded, Conflict, Store


class SellerInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    seller_url: str
    request_key: str = Field(min_length=8, max_length=100)

    @field_validator("seller_url")
    @classmethod
    def public_url(cls, value):
        return canonical_url(value)


class LocalKeyInput(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    key: SecretStr = Field(min_length=13, max_length=256)


class Confirmation(Target):
    company_limit: int = Field(default=3, ge=1, le=3)


class SavedRecord(BaseModel):
    research: Research
    review: Review | None = None
    operator_review: OperatorReview | None = None
    credits_used: int | None = Field(default=None, ge=0, le=1)


class RunCredits(BaseModel):
    maximum: int = Field(ge=1, le=3)
    used: int = Field(ge=0, le=3)
    reserved: int = Field(ge=0, le=3)
    returned: int = Field(ge=0, le=3)


class WalletView(BaseModel):
    mode: Literal["local", "hosted"]
    available: int = Field(default=0, ge=0)
    reserved: int = Field(default=0, ge=0)
    used: int = Field(default=0, ge=0)


class ServiceView(BaseModel):
    booking_url: str | None = None


class CreditEntry(BaseModel):
    id: str
    kind: Literal["signup", "purchase", "usage", "refund"]
    amount: int = Field(ge=-1)
    created_at: datetime


class CreditHistory(BaseModel):
    mode: Literal["local", "hosted"]
    entries: list[CreditEntry] = Field(max_length=50)
    next_cursor: UUID | None = None


class BookingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_key: str = Field(min_length=8, max_length=100)


class ReuseInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_key: str = Field(min_length=8, max_length=100)


class StopInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmation: Literal["stop"]


class AttemptView(BaseModel):
    provider: str
    kind: str
    state: str
    created_at: datetime


class RunView(BaseModel):
    id: str
    seller_url: str
    status: Literal["queued", "running", "awaiting_confirmation", "ready", "partial"]
    stage: str
    profile: Profile | None = None
    draft: SellerDraft | None = None
    records: list[SavedRecord]
    error: str | None = None
    created_at: datetime
    updated_at: datetime
    attempts: list[AttemptView]
    progress: RunProgress
    credits: RunCredits | None = None
    legacy_credit_exempt: bool = False
    reused_offer: bool = False
    draft_exclusions: list[str] = Field(default_factory=list)
    termination: Literal["user_stopped"] | None = None


class Health(BaseModel):
    local_search_error: Literal["unavailable"] | None = None
    mode: Literal["local", "hosted"] = "local"
    search_ready: bool
    gemma_ready: bool
    worker_online: bool


class LocalAuth(BaseModel):
    mode: Literal["local"] = "local"


class HostedAuth(BaseModel):
    mode: Literal["hosted"] = "hosted"
    supabase_url: str
    publishable_key: str
    redirect_url: str


AuthSetup = Annotated[LocalAuth | HostedAuth, Field(discriminator="mode")]


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.load()
    local_store = Store(settings.db_path) if settings.mode == "local" else None
    app = FastAPI(title="GTM Shortlist", version="0.1.0")
    hosts = ["localhost", "127.0.0.1", "testserver"] if settings.mode == "local" else [urlsplit(settings.app_url).hostname]
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=hosts)
    bearer = HTTPBearer(auto_error=False)

    def owned_store(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> Store:
        if local_store is not None:
            return local_store
        if credentials is None:
            raise AuthenticationError("Sign in to access your research")
        user = verify_user(settings, credentials.credentials)
        from shortlist.postgres import PostgresStore
        store = PostgresStore(settings.database_url, user.id)
        store.ensure_workspace()
        return store

    owned = Annotated[Store, Depends(owned_store)]

    @app.middleware("http")
    async def local_origin(request: Request, call_next):
        origin = request.headers.get("origin")
        expected_origin = settings.app_url.rstrip("/") if settings.mode == "hosted" else str(request.base_url).rstrip("/")
        if origin and origin != expected_origin:
            return JSONResponse({"detail": "Cross-origin access is not permitted"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/api/") else "no-cache"
        return response

    @app.exception_handler(KeyError)
    async def not_found(request, exc):
        return JSONResponse({"detail": "Saved run or record was not found"}, status_code=404)

    @app.exception_handler(Conflict)
    async def conflict(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.exception_handler(AuthenticationError)
    async def unauthorized(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=401, headers={"WWW-Authenticate": "Bearer"})

    @app.exception_handler(AuthUnavailable)
    async def auth_unavailable(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=503)

    @app.exception_handler(CredentialUnavailable)
    async def credential_unavailable(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=503)

    @app.exception_handler(BudgetExceeded)
    async def allowance_exhausted(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=403)

    def view(store: Store, run_id: str) -> RunView:
        run = store.get_run(run_id)
        profile = Profile.model_validate(run["profile"]) if run["profile"] else None
        return RunView(id=run_id, seller_url=profile.seller_url if profile else run["checkpoint"]["seller_url"],
                       status=run["status"], stage=run["stage"], profile=profile, draft=run["checkpoint"].get("draft"),
                       records=run["records"], error=run["error"], created_at=run["created_at"],
                       updated_at=run["updated_at"], attempts=run["attempts"], credits=run.get("credits"),
                       legacy_credit_exempt=run.get("legacy_credit_exempt", False),
                       reused_offer=run["checkpoint"].get("reused_offer", False),
                       termination=run["checkpoint"].get("termination"),
                       draft_exclusions=run["checkpoint"].get("draft_exclusions", []), progress=RunProgress(
                           worker_online=store.worker_online(), candidates=len(run["checkpoint"].get("candidates", [])),
                           sources=len({s["id"] for pages in run["checkpoint"].get("sources", {}).values() for s in pages}),
                           companies=len(run["records"]), events=run["events"]))

    @app.get("/api/health", response_model=Health)
    def health():
        error = None
        try:
            readiness = apply_local_credentials(settings).readiness()
        except CredentialUnavailable:
            readiness = {**settings.readiness(), "search": False}
            error = "unavailable"
        return Health(mode=settings.mode, search_ready=readiness["search"], gemma_ready=readiness["gemma"],
                      worker_online=local_store.worker_online() if local_store else False, local_search_error=error)

    @app.post("/api/local/tavily", response_model=Health, openapi_extra={
        "requestBody": {"required": True, "content": {"application/json": {"schema": LocalKeyInput.model_json_schema()}}}})
    async def configure_tavily(request: Request):
        if settings.mode != "local":
            raise HTTPException(404, "Local provider setup is unavailable")
        if request.headers.get("origin") != str(request.base_url).rstrip("/") or \
                request.client is None or request.client.host not in ("127.0.0.1", "::1", "testclient"):
            raise HTTPException(403, "Open provider setup from this local workspace")
        if request.headers.get("content-type", "").split(";", 1)[0].lower() != "application/json":
            raise HTTPException(415, "Provider setup requires JSON")
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 2048:
                raise HTTPException(413, "Provider setup request is too large")
        try:
            command = LocalKeyInput.model_validate_json(body)
            key = validate_tavily_key(command.key.get_secret_value())
        except (ValidationError, ValueError):
            # FastAPI's default validation response echoes rejected input. This
            # boundary deliberately returns no submitted key or parser details.
            raise HTTPException(422, "Enter a valid tvly-prefixed Tavily API key") from None
        finally:
            body.clear()
        # Short local I/O; native protection and the committed private database
        # are shared by this API and the separately running worker.
        await run_in_threadpool(LocalCredentials(settings.db_path).save, key)
        return await run_in_threadpool(health)

    @app.get("/api/auth/setup", response_model=AuthSetup)
    def auth_setup():
        if settings.mode == "local":
            return LocalAuth()
        return HostedAuth(supabase_url=settings.supabase_url, publishable_key=settings.supabase_publishable_key,
                          redirect_url=settings.app_url.rstrip("/") + "/")

    @app.get("/api/service", response_model=ServiceView)
    def service():
        return ServiceView(booking_url=settings.booking_url or None)

    @app.get("/api/runs", response_model=list[RunView])
    def runs(store: owned):
        return [view(store, run["id"]) for run in store.list_runs()]

    @app.get("/api/credits", response_model=WalletView)
    def credits(store: owned):
        if settings.mode == "local":
            return WalletView(mode="local")
        from shortlist.credits import CreditWallet
        return WalletView(mode="hosted", **CreditWallet(store).balance().model_dump())

    @app.get("/api/credits/history", response_model=CreditHistory)
    def credit_history(store: owned, before: UUID | None = None):
        if settings.mode == "local":
            return CreditHistory(mode="local", entries=[])
        from shortlist.credits import CreditWallet
        try:
            entries, next_cursor = CreditWallet(store).history_page(before)
        except KeyError:
            raise HTTPException(400, "Credit activity page is unavailable. Refresh to see the latest changes.") from None
        return CreditHistory(mode="hosted", entries=entries, next_cursor=next_cursor)

    @app.post("/api/sellers", response_model=RunView, status_code=201)
    def seller(input: SellerInput, store: owned):
        return view(store, store.create_draft(input.seller_url, input.request_key))

    @app.get("/api/runs/{run_id}", response_model=RunView)
    def read_run(run_id: str, store: owned):
        return view(store, run_id)

    @app.delete("/api/runs/{run_id}", status_code=204)
    def delete_run(run_id: str, store: owned):
        store.delete_run(run_id)
        return Response(status_code=204)

    @app.post("/api/runs/{run_id}/reuse", response_model=RunView, status_code=201)
    def reuse_offer(run_id: str, input: ReuseInput, store: owned):
        return view(store, store.reuse_draft(run_id, input.request_key))

    @app.post("/api/runs/{run_id}/booking-click", status_code=204)
    def booking_click(run_id: str, input: BookingInput, store: owned):
        if not settings.booking_url:
            raise Conflict("Setup-call booking is not configured")
        store.booking_click(run_id, input.request_key)
        return Response(status_code=204)

    @app.post("/api/runs/{run_id}/confirm", response_model=RunView)
    def confirm(run_id: str, input: Confirmation, store: owned):
        run = store.get_run(run_id)
        seller_url = run["profile"].get("seller_url") or run["checkpoint"]["seller_url"]
        profile = Profile(seller_url=seller_url, **input.model_dump(exclude={"company_limit"}))
        store.confirm_draft(run_id, profile, input.company_limit)
        return view(store, run_id)

    @app.post("/api/runs/{run_id}/stop", response_model=RunView)
    def stop(run_id: str, input: StopInput, store: owned):
        store.stop_run(run_id)
        return view(store, run_id)

    @app.post("/api/runs/{run_id}/records/{record_id}/review", response_model=RunView)
    def review(run_id: str, record_id: str, input: Review, store: owned):
        store.review(run_id, record_id, input)
        return view(store, run_id)

    @app.get("/api/runs/{run_id}/export")
    def export(run_id: str, store: owned, format: Literal["json", "csv"] = "json", accepted_only: bool = False):
        content = export_run(store.get_run(run_id), format, accepted_only)
        return Response(content, media_type="application/json" if format == "json" else "text/csv",
                        headers={"Content-Disposition": f'attachment; filename="shortlist-{run_id}.{format}"'})

    dist = Path(__file__).resolve().parents[2] / "dist"
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="ui")
    return app


app = create_app()
