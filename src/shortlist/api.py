from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

from shortlist.config import Settings
from shortlist.domain import Profile, Research, Review, Target
from shortlist.export import export_run
from shortlist.fetch import canonical_url
from shortlist.providers import SellerDraft
from shortlist.store import Conflict, Store


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


class Health(BaseModel):
    mode: Literal["local"] = "local"
    search_ready: bool
    gemma_ready: bool


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.load()
    store = Store(settings.db_path)
    app = FastAPI(title="GTM Shortlist local core", version="0.1.0")
    # Local-only until hosted identity and isolation are implemented.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"])

    @app.middleware("http")
    async def local_origin(request: Request, call_next):
        origin = request.headers.get("origin")
        if origin and origin != str(request.base_url).rstrip("/"):
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

    def view(run_id: str) -> RunView:
        run = store.get_run(run_id)
        profile = Profile.model_validate(run["profile"]) if run["profile"] else None
        return RunView(id=run_id, seller_url=profile.seller_url if profile else run["checkpoint"]["seller_url"],
                       status=run["status"], stage=run["stage"], profile=profile, draft=run["checkpoint"].get("draft"),
                       records=run["records"], error=run["error"], created_at=run["created_at"],
                       updated_at=run["updated_at"], attempts=run["attempts"])

    @app.get("/api/health", response_model=Health)
    def health():
        readiness = settings.readiness()
        return Health(search_ready=readiness["search"], gemma_ready=readiness["gemma"])

    @app.get("/api/runs", response_model=list[RunView])
    def runs():
        return [view(run["id"]) for run in store.list_runs()]

    @app.post("/api/sellers", response_model=RunView, status_code=201)
    def seller(input: SellerInput):
        return view(store.create_draft(input.seller_url, input.request_key))

    @app.get("/api/runs/{run_id}", response_model=RunView)
    def read_run(run_id: str):
        return view(run_id)

    @app.post("/api/runs/{run_id}/confirm", response_model=RunView)
    def confirm(run_id: str, input: Confirmation):
        run = store.get_run(run_id)
        seller_url = run["profile"].get("seller_url") or run["checkpoint"]["seller_url"]
        profile = Profile(seller_url=seller_url, **input.model_dump())
        store.confirm_draft(run_id, profile)
        return view(run_id)

    @app.post("/api/runs/{run_id}/records/{record_id}/review", response_model=RunView)
    def review(run_id: str, record_id: str, input: Review):
        store.review(run_id, record_id, input)
        return view(run_id)

    @app.get("/api/runs/{run_id}/export")
    def export(run_id: str, format: Literal["json", "csv"] = "json", accepted_only: bool = False):
        content = export_run(store.get_run(run_id), format, accepted_only)
        return Response(content, media_type="application/json" if format == "json" else "text/csv",
                        headers={"Content-Disposition": f'attachment; filename="shortlist-{run_id}.{format}"'})

    dist = Path(__file__).resolve().parents[2] / "dist"
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="ui")
    return app


app = create_app()
