"""Background execution of agent runs for the local API: one daemon thread per run or correction."""
from collections.abc import Callable
from datetime import timedelta
from threading import Thread

from shortlist.agent.assumptions import merge
from shortlist.agent.jobboards import JobBoards
from shortlist.agent.models import Overrides, RunResult, Telemetry
from shortlist.agent.pages import fetch_document
from shortlist.agent.pipeline import AgentRunner, Providers
from shortlist.agent.providers import AgentProviderError, BasetenSkeptic, MetaInvestigator
from shortlist.agent.settings import AgentSettings
from shortlist.agent.storage import HISTORY_DAYS, SQLiteAgentRuns
from shortlist.domain import utcnow
from shortlist.fetch import FetchError, canonical_url, domain_of

ACTIVE = ("queued", "running")


class RunConflict(ValueError):
    pass


def real_providers(settings: AgentSettings) -> Providers:
    investigator = MetaInvestigator(settings)
    skeptic = BasetenSkeptic(settings) if settings.use_skeptic else None
    return Providers(investigator=investigator, skeptic=skeptic, fetcher=fetch_document, job_boards=JobBoards())


def website_url(value: str) -> str:
    value = (value or "").strip()
    if not value or " " in value:
        raise FetchError("Enter your company website, for example yourcompany.com")
    if value.startswith("//"):
        value = "https:" + value
    elif "://" not in value:
        value = "https://" + value
    if not value.startswith("https://"):
        raise FetchError("Use an https:// website")
    return canonical_url(value.split("#")[0])


class AgentService:
    def __init__(self, store: SQLiteAgentRuns, settings: Callable[[], AgentSettings] = AgentSettings.load,
                 providers: Callable[[AgentSettings], Providers] = real_providers,
                 history_days: int | None = HISTORY_DAYS):
        """history_days: set aside companies already researched for the same seller within this many days. None turns
        it off (the public demo: one visitor's searches must not show in another's)."""
        self.store = store
        self.settings = settings
        self.providers = providers
        self.history_days = history_days
        self.threads: dict[str, Thread] = {}

    def history(self, website: str) -> dict[str, dict]:
        if self.history_days is None:
            return {}
        return self.store.researched(domain_of(website), utcnow() - timedelta(days=self.history_days))

    def runner(self, run_id: str, settings: AgentSettings, providers: Providers) -> AgentRunner:
        return AgentRunner(providers, budget_usd=settings.run_budget_usd, concurrency=settings.concurrency,
                           use_skeptic=settings.use_skeptic,
                           on_event=lambda event: self.store.append_event(run_id, event), on_save=self.store.save)

    def start(self, website: str, overrides: Overrides | None = None) -> RunResult:
        settings = self.settings()
        overrides = overrides or Overrides()
        result = RunResult(website=website_url(website), status="queued", overrides=overrides,
                           company_count=overrides.company_count or 10, skeptic=settings.use_skeptic,
                           telemetry=Telemetry(budget_usd=settings.run_budget_usd))
        history = self.history(result.website)
        self.store.create(result)
        self._spawn(result.id, lambda runner: runner.run(result.website, overrides, run_id=result.id, history=history),
                    settings, result)
        return result

    def override(self, run_id: str, overrides: Overrides) -> RunResult:
        record = self.store.get(run_id)
        result: RunResult = record["result"]
        if result.status in ACTIVE:
            raise RunConflict("This run is still working; wait for it to finish before changing it")
        settings = self.settings()
        merged = merge(result.overrides, overrides)
        restart = result.status == "needs_choice" or result.profile is None or result.status == "failed"
        if restart:
            reading = None
            if overrides.interpretation and result.profile:
                reading = next((r for r in result.profile.interpretations if r.id == overrides.interpretation), None)
                if reading is None:
                    raise RunConflict("That reading is not part of this run")
            work = lambda runner: runner.run(result.website, merged, run_id=run_id, reading=reading)
        else:
            work = lambda runner: runner.reevaluate(result, overrides)
        self.store.set_status(run_id, "running")
        self._spawn(run_id, work, settings, result)
        return self.store.get(run_id)["result"]

    def _spawn(self, run_id: str, work, settings: AgentSettings, result: RunResult):
        def target():
            try:
                providers = self.providers(settings)
            except AgentProviderError as exc:
                failed = result.model_copy(update={"status": "failed", "error": str(exc)})
                self.store.save(failed)
                return
            work(self.runner(run_id, settings, providers))

        thread = Thread(target=target, name=f"agent-run-{run_id[:8]}", daemon=True)
        self.threads[run_id] = thread
        thread.start()

    def wait(self, run_id: str, timeout: float = 30) -> None:
        thread = self.threads.get(run_id)
        if thread is not None:
            thread.join(timeout)
