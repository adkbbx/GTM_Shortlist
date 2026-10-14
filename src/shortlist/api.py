from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

from shortlist.auth import AuthenticationError, AuthUnavailable, verify_user
from shortlist.config import Settings
from shortlist.domain import Profile, Research, Review, Target
from shortlist.export import export_run
from shortlist.fetch import canonical_url
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


class Confirmation(Target):
    pass


class SavedRecord(BaseModel):
    research: Research
    review: Review | None = None


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


class Health(BaseModel):
    mode: Literal["local", "hosted"] = "local"
    search_ready: bool
    gemma_ready: bool
    worker_online: bool


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

    @app.exception_handler(BudgetExceeded)
    async def allowance_exhausted(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=403)

    def view(store: Store, run_id: str) -> RunView:
        run = store.get_run(run_id)
        profile = Profile.model_validate(run["profile"]) if run["profile"] else None
        return RunView(id=run_id, seller_url=profile.seller_url if profile else run["checkpoint"]["seller_url"],
                       status=run["status"], stage=run["stage"], profile=profile, draft=run["checkpoint"].get("draft"),
                       records=run["records"], error=run["error"], created_at=run["created_at"],
                       updated_at=run["updated_at"], attempts=run["attempts"], progress=RunProgress(
                           worker_online=store.worker_online(), candidates=len(run["checkpoint"].get("candidates", [])),
                           sources=len({s["id"] for pages in run["checkpoint"].get("sources", {}).values() for s in pages}),
                           companies=len(run["records"]), events=run["events"]))

    @app.get("/api/health", response_model=Health)
    def health():
        readiness = settings.readiness()
        return Health(mode=settings.mode, search_ready=readiness["search"], gemma_ready=readiness["gemma"],
                      worker_online=local_store.worker_online() if local_store else False)

    @app.get("/api/runs", response_model=list[RunView])
    def runs(store: owned):
        return [view(store, run["id"]) for run in store.list_runs()]

    @app.post("/api/sellers", response_model=RunView, status_code=201)
    def seller(input: SellerInput, store: owned):
        return view(store, store.create_draft(input.seller_url, input.request_key))

    @app.get("/api/runs/{run_id}", response_model=RunView)
    def read_run(run_id: str, store: owned):
        return view(store, run_id)

    @app.post("/api/runs/{run_id}/confirm", response_model=RunView)
    def confirm(run_id: str, input: Confirmation, store: owned):
        run = store.get_run(run_id)
        seller_url = run["profile"].get("seller_url") or run["checkpoint"]["seller_url"]
        profile = Profile(seller_url=seller_url, **input.model_dump())
        store.confirm_draft(run_id, profile)
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
