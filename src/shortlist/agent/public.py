"""Public demo of the website-only agent: anyone can start a search with just a website, under fixed limits.

Kept apart from shortlist.api so the classic local and hosted apps are untouched. Limits: companies per search,
searches per visitor per hour, searches working at once, and a daily estimated-dollar cap across all visitors, plus an
optional Cloudflare Turnstile check. A search page is readable by anyone with its link (ids are random 128-bit hex);
only the browser that started it holds the edit token that lets it correct the assumptions.

Run with `uvicorn --factory shortlist.agent.public:create_public_app`, or deploy/modal_agent.py on Modal.
"""
import hashlib
import hmac
import json
import os
import time
from collections import defaultdict, deque
from collections.abc import Callable
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from threading import Lock
from urllib.parse import urlsplit

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

from shortlist.agent.api import AgentStartInput, RoutePolicy, register_agent_routes
from shortlist.agent.files import FileAgentRuns
from shortlist.agent.models import AgentEvent, Overrides, RunResult
from shortlist.agent.pipeline import Providers
from shortlist.agent.providers import ModelCheck, meta_model_check
from shortlist.agent.service import AgentService, real_providers
from shortlist.agent.settings import AgentSettings
from shortlist.domain import utcnow
from shortlist.fetch import canonical_url
from shortlist.site_icons import PUBLIC_HOST, SiteIconInfo, SiteIcons
from shortlist.turnstile import verify_turnstile

LOCAL_HOSTS = ("localhost", "127.0.0.1")
# Real searches saved from live runs, shipped with the app so an example opens even after a restart wipes /tmp.
SHOWCASE = Path(__file__).parent / "showcase"
START_FLOW = '<meta name="shortlist-start-flow" content="agent-only">'


def env_flag(name: str) -> bool:
    return os.getenv(name, "off").strip().lower() in ("1", "on", "true", "yes")


class PublicSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    app_url: str
    # Signs edit tokens and hashes visitor addresses for the hourly limit (raw addresses are never stored).
    secret: SecretStr
    data_dir: Path = Path("data/agent-public")
    dist_dir: Path | None = None
    max_companies: int = Field(default=5, ge=1, le=20)
    runs_per_hour: int = Field(default=3, ge=1, le=100)
    max_active: int = Field(default=3, ge=1, le=20)
    daily_usd: float = Field(default=10.0, gt=0, le=1000)
    turnstile_site_key: str = Field(default="", max_length=200)
    turnstile_secret: SecretStr = SecretStr("")
    # On only behind a proxy that sets X-Forwarded-For (Modal does); otherwise a visitor could pick their own address.
    trust_proxy: bool = False
    # LABELLED SYNTHETIC providers (shortlist.agent.synthetic): invented companies, no keys, no spending.
    synthetic: bool = False
    # Saved real searches offered as read-only examples; None for none.
    showcase_dir: Path | None = SHOWCASE
    # Brandfetch public client ID (never a secret key): company suggestions and logos in the browser; empty for none.
    brandfetch_client_id: str = Field(default="", max_length=200, pattern=r"^[A-Za-z0-9_-]*$")

    @field_validator("app_url")
    @classmethod
    def origin(cls, value):
        value = value.strip().rstrip("/")
        parts = urlsplit(value)
        if parts.path or parts.query or not parts.hostname:
            raise ValueError("AGENT_PUBLIC_URL is the site origin only, for example https://demo.example.com")
        if parts.scheme != "https" and not (parts.scheme == "http" and parts.hostname in LOCAL_HOSTS):
            raise ValueError("AGENT_PUBLIC_URL must use https (http only for localhost)")
        return value

    @field_validator("secret")
    @classmethod
    def long_secret(cls, value):
        if len(value.get_secret_value()) < 32:
            raise ValueError("AGENT_PUBLIC_SECRET needs at least 32 characters")
        return value

    @model_validator(mode="after")
    def turnstile_pair(self):
        if bool(self.turnstile_site_key) != bool(self.turnstile_secret.get_secret_value()):
            raise ValueError("Set both AGENT_PUBLIC_TURNSTILE_SITE_KEY and AGENT_PUBLIC_TURNSTILE_SECRET, or neither")
        return self

    @classmethod
    def load(cls) -> "PublicSettings":
        load_dotenv()
        env = os.getenv
        return cls(app_url=env("AGENT_PUBLIC_URL", ""), secret=env("AGENT_PUBLIC_SECRET", ""),
                   data_dir=env("AGENT_PUBLIC_DATA", "data/agent-public"), dist_dir=env("AGENT_PUBLIC_DIST") or None,
                   max_companies=env("AGENT_PUBLIC_MAX_COMPANIES", "5"), runs_per_hour=env("AGENT_PUBLIC_RUNS_PER_HOUR", "3"),
                   max_active=env("AGENT_PUBLIC_MAX_ACTIVE", "3"), daily_usd=env("AGENT_PUBLIC_DAILY_USD", "10"),
                   turnstile_site_key=env("AGENT_PUBLIC_TURNSTILE_SITE_KEY", ""),
                   turnstile_secret=env("AGENT_PUBLIC_TURNSTILE_SECRET", ""),
                   trust_proxy=env_flag("AGENT_PUBLIC_TRUST_PROXY"), synthetic=env_flag("AGENT_PUBLIC_SYNTHETIC"),
                   showcase_dir=None if env("AGENT_PUBLIC_SHOWCASE", "").lower() == "off"
                   else env("AGENT_PUBLIC_SHOWCASE") or SHOWCASE,
                   brandfetch_client_id=env("SHORTLIST_BRANDFETCH_CLIENT_ID", "").strip())


class PublicHealth(BaseModel):
    mode: str = "public"
    max_companies: int
    turnstile_site_key: str | None = None
    synthetic: bool
    investigator_ready: bool
    skeptic_ready: bool
    # Whether Meta offers the configured model to this server (None: unknown or synthetic). False usually means the
    # host's region: model availability varies by country. The models Meta does offer here and where the server is
    # (country/data centre) say which.
    investigator_model_available: bool | None = None
    investigator_models_offered: list[str] = Field(default_factory=list)
    server_location: str | None = None
    examples: list["Example"] = Field(default_factory=list)


class Example(BaseModel):
    id: str
    website: str
    shortlisted: int
    created_at: datetime
    # What the example shows, so the start page can tell examples apart: company names by verdict, and the rule
    # behind each rejection.
    shortlisted_names: list[str] = Field(default_factory=list)
    rejected: list[str] = Field(default_factory=list)


PublicHealth.model_rebuild()


class PublicPolicy(RoutePolicy):
    listing = False

    def __init__(self, settings: PublicSettings, store: FileAgentRuns, agent_settings: Callable[[], AgentSettings], *,
                 clock: Callable[[], float] = time.monotonic, verify=verify_turnstile):
        self.settings, self.store, self.agent_settings = settings, store, agent_settings
        self.clock, self.verify = clock, verify
        self.lock = Lock()
        self.starts: dict[str, deque[float]] = defaultdict(deque)

    def address(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for", "") if self.settings.trust_proxy else ""
        return forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")

    def visitor(self, request: Request) -> str:
        key = self.settings.secret.get_secret_value().encode()
        return hmac.new(key, ("visitor:" + self.address(request)).encode(), hashlib.sha256).hexdigest()[:24]

    def token(self, run_id: str) -> str:
        key = self.settings.secret.get_secret_value().encode()
        return hmac.new(key, ("edit:" + run_id).encode(), hashlib.sha256).hexdigest()

    def hourly(self, request: Request) -> None:
        visitor, now = self.visitor(request), self.clock()
        with self.lock:
            window = self.starts[visitor]
            while window and now - window[0] >= 3600:
                window.popleft()
            if len(window) >= self.settings.runs_per_hour:
                raise HTTPException(429, f"This demo allows {self.settings.runs_per_hour} searches an hour from one "
                                         "connection. Please try again later.")
            window.append(now)

    def spending(self) -> None:
        day = datetime.combine(utcnow().date(), datetime.min.time(), tzinfo=UTC)
        spent, active = self.store.usage_since(day)
        if active >= self.settings.max_active:
            raise HTTPException(503, "The demo is busy with other searches. Please try again in a few minutes.")
        # Every working search may still spend its whole budget, so reserve it before allowing another.
        if spent + (active + 1) * self.agent_settings().run_budget_usd > self.settings.daily_usd:
            raise HTTPException(503, "Today's demo budget is used up. It resets at 00:00 UTC.")

    def capped(self, overrides: Overrides) -> Overrides:
        count = min(overrides.company_count or self.settings.max_companies, self.settings.max_companies)
        return overrides.model_copy(update={"company_count": count})

    def before_start(self, request: Request, body: AgentStartInput) -> AgentStartInput:
        if self.settings.turnstile_secret.get_secret_value() and not (
                body.turnstile and self.verify(self.settings.turnstile_secret, body.turnstile, self.address(request))):
            raise HTTPException(403, "The browser check did not pass. Reload the page and try again.")
        self.spending()
        self.hourly(request)
        return body.model_copy(update={"overrides": self.capped(body.overrides or Overrides()), "turnstile": None,
                                       "previous": body.previous})

    def started(self, result: RunResult) -> str:
        return self.token(result.id)

    def before_email(self, request: Request, run_id: str) -> None:
        if not hmac.compare_digest(request.headers.get("x-agent-edit-token", ""), self.token(run_id)):
            raise HTTPException(403, "Only the browser that started this search can draft emails for it.")
        self.spending()

    def history_runs(self, body: AgentStartInput) -> list[str]:
        """Only searches this browser proves it started: one visitor's searches never shape another's."""
        return [run.id for run in body.previous if hmac.compare_digest(run.token, self.token(run.id))]

    def before_override(self, request: Request, run_id: str, overrides: Overrides, current: RunResult) -> Overrides:
        if not hmac.compare_digest(request.headers.get("x-agent-edit-token", ""), self.token(run_id)):
            raise HTTPException(403, "Only the browser that started this search can change it. "
                                     "Start your own search to try different assumptions.")
        self.spending()
        if current.status in ("needs_choice", "failed") or current.profile is None:
            self.hourly(request)  # a restart researches from the beginning, like a new search
        return self.capped(overrides) if overrides.company_count else overrides


def ui_directory(configured: Path | None) -> Path | None:
    here = Path(__file__).resolve()
    folders = (configured,) if configured else (here.parents[3] / "dist", here.parents[1] / "web_dist")
    return next((folder for folder in folders if folder and (folder / "index.html").is_file()), None)


def load_showcase(store: FileAgentRuns, directory: Path | None) -> list[Example]:
    """Copy saved example runs into the store when missing. No browser holds their edit token, so they are read-only."""
    if directory is None or not Path(directory).is_dir():
        return []
    examples = []
    for path in sorted(Path(directory).glob("*.json")):
        result = RunResult.model_validate_json(path.read_text(encoding="utf-8"))
        if result.status != "complete" or result.synthetic:
            continue
        try:
            known = bool(store.read(result.id)["events"])
        except KeyError:
            store.create(result)
            known = False
        # The run's real activity log, as recorded when it ran, so the board and the landing replay show each step.
        log = Path(directory) / "events" / path.name
        if not known and log.is_file():
            for event in json.loads(log.read_text(encoding="utf-8")):
                store.append_event(result.id, AgentEvent.model_validate(event))
        decided = [c for c in result.companies if c.verdict]
        examples.append(Example(
            id=result.id, website=result.website, created_at=result.created_at,
            shortlisted=sum(c.verdict.kind == "shortlisted" for c in decided),
            shortlisted_names=[c.name or c.domain for c in decided if c.verdict.kind == "shortlisted"],
            rejected=[(f"{c.name or c.domain}: “{c.verdict.disqualifier.quote.text[:110]}”" if c.verdict.disqualifier
                      else f"{c.name or c.domain}: {c.verdict.summary}")[:200] for c in decided if c.verdict.kind == "rejected"]))
    return examples


def create_public_app(settings: PublicSettings | None = None, *, agent_settings: Callable[[], AgentSettings] | None = None,
                      providers: Callable[[AgentSettings], Providers] | None = None,
                      after_write: Callable[[], None] | None = None,
                      model_check: Callable[[AgentSettings], ModelCheck] = meta_model_check) -> FastAPI:
    settings = settings or PublicSettings.load()
    load_agent = agent_settings or AgentSettings.load
    if providers is None and settings.synthetic:
        from shortlist.agent.synthetic import synthetic_providers
        providers = lambda agent: synthetic_providers(pace=0.08)
    store = FileAgentRuns(settings.data_dir, after_write=after_write)
    store.recover_interrupted()
    examples = load_showcase(store, settings.showcase_dir) if not settings.synthetic else []
    # No search history here: one visitor's searches must never appear in another's.
    service = AgentService(store, load_agent, providers or real_providers, history_days=None)
    policy = PublicPolicy(settings, store, load_agent)

    app = FastAPI(title="GTM Shortlist agent demo", version="0.1.0", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.public_policy = policy
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=[urlsplit(settings.app_url).hostname])

    @app.middleware("http")
    async def same_origin(request: Request, call_next):
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") != settings.app_url:
            return JSONResponse({"detail": "Cross-origin access is not permitted"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/api/") else "no-cache"
        return response

    @app.exception_handler(KeyError)
    async def not_found(request, exc):
        return JSONResponse({"detail": "This search was not found. Check the link or start a new search."}, status_code=404)

    checked: dict = {"at": 0.0, "result": ModelCheck()}

    def model_state(agent: AgentSettings) -> ModelCheck:
        if settings.synthetic:
            return ModelCheck()
        if time.monotonic() - checked["at"] > 600:  # at most one /models request per ten minutes
            checked["result"], checked["at"] = model_check(agent), time.monotonic()
        return checked["result"]

    icons = SiteIcons()

    @app.get("/api/site-icon/{domain}", response_model=SiteIconInfo)
    def site_icon(domain: str):
        """The icon a company's homepage declares, for logos and suggestions when no directory logo exists. One homepage
        read per domain per day, two at a time, with the shared fetcher's limits and private-address checks."""
        if not PUBLIC_HOST.fullmatch(domain):
            raise HTTPException(404, "Enter a public website domain")
        try:
            canonical = urlsplit(canonical_url(f"https://{domain}/")).hostname
        except ValueError:
            raise HTTPException(404, "Enter a public website domain") from None
        if canonical != domain or settings.synthetic:  # synthetic demo: no network
            return SiteIconInfo()
        return SiteIconInfo(url=icons.get(domain))

    @app.get("/api/health", response_model=PublicHealth)
    def health():
        agent = load_agent()
        ready = agent.readiness()
        model = model_state(agent)
        return PublicHealth(max_companies=settings.max_companies, turnstile_site_key=settings.turnstile_site_key or None,
                            synthetic=settings.synthetic, investigator_ready=settings.synthetic or ready["investigator"],
                            skeptic_ready=settings.synthetic or ready["skeptic"],
                            investigator_model_available=model.available,
                            investigator_models_offered=list(model.offered), server_location=model.location,
                            examples=examples)

    register_agent_routes(app, None, service, policy)

    dist = ui_directory(settings.dist_dir)
    if dist is not None:
        @app.get("/", response_class=HTMLResponse, include_in_schema=False)
        @app.get("/index.html", response_class=HTMLResponse, include_in_schema=False)
        def ui_index(agent: str | None = None):
            html = (dist / "index.html").read_text(encoding="utf-8")
            # Public ID only; the settings pattern allows letters, digits, _ and - before it reaches the HTML.
            brand = (f'<meta name="shortlist-company-suggestions-client-id" content="{settings.brandfetch_client_id}">'
                     if settings.brandfetch_client_id else "")
            return HTMLResponse(html.replace("<head>", "<head>" + START_FLOW + brand + preview(agent), 1))

        def preview(run_id: str | None) -> str:
            """Link preview for a shared, finished board: what was found, never who looked."""
            try:
                result = store.get(run_id)["result"] if run_id else None
            except KeyError:
                result = None
            if result is None or result.status != "complete":
                return ""
            seller = urlsplit(result.website).hostname or result.website
            shortlisted = [c.name or c.domain for c in result.companies if c.verdict and c.verdict.kind == "shortlisted"]
            title = f"{len(shortlisted)} {'company' if len(shortlisted) == 1 else 'companies'} that need what {seller} sells"
            text = (f"Shortlisted: {', '.join(shortlisted[:4])}. " if shortlisted else "") + \
                "Each verdict shows the exact quote behind it. Found by an agent on Muse Spark; every quote checked " \
                "by Muse Spark Open."
            tags = {"og:title": title, "og:description": text, "og:type": "website",
                    "og:url": f"{settings.app_url}/?agent={result.id}", "twitter:card": "summary",
                    "twitter:title": title, "twitter:description": text}
            return "".join(f'<meta {"name" if key.startswith("twitter") else "property"}="{key}" '
                           f'content="{escape(value, quote=True)}">' for key, value in tags.items())

        app.mount("/", StaticFiles(directory=dist, html=True), name="ui")
    return app
