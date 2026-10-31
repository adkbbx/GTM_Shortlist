"""The whole run: understand the seller, find competitors and companies, investigate in parallel, let the skeptic
judge each quote, then decide verdicts in code. Progress events and saved snapshots are emitted along the way."""
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from threading import Lock
from urllib.parse import urlsplit

from shortlist.agent import assumptions
from shortlist.agent.competitors import TARGET_SIZE_RULE, find_competitors
from shortlist.agent.discovery import discover
from shortlist.agent.investigation import HOMEPAGE_UNREADABLE, Context, Investigation
from shortlist.agent.jobboards import JobBoards
from shortlist.agent.llm import AgentOutputError, Calls
from shortlist.agent.models import (
    DEFAULT_COMPANIES,
    AgentEvent,
    CandidateRef,
    CompanyResult,
    EvidenceItem,
    Interpretation,
    Overrides,
    RunResult,
    SellerProfile,
    SetAside,
    Telemetry,
)
from shortlist.agent.outreach import pitch_or_none
from shortlist.agent.pages import COMPARISON, Fetcher
from shortlist.agent.providers import AgentProviderError, Investigator, SkepticModel
from shortlist.agent.scan import scan
from shortlist.agent.seller import understand_seller
from shortlist.agent.skeptic import judge
from shortlist.agent.telemetry import BudgetReached, Meter
from shortlist.agent.verdict import decide
from shortlist.domain import utcnow
from shortlist.fetch import FetchError

VERDICT_LABEL = {"shortlisted": "Shortlisted", "needs_look": "Needs a look", "rejected": "Rejected"}


@dataclass
class Providers:
    investigator: Investigator
    skeptic: SkepticModel | None
    fetcher: Fetcher
    synthetic: bool = False
    job_boards: JobBoards | None = None
    clock: Callable[[], datetime] = utcnow


class AgentRunner:
    def __init__(self, providers: Providers, *, budget_usd: float = 1.0, concurrency: int = 5, use_skeptic: bool = True,
                 on_event: Callable[[AgentEvent], None] | None = None,
                 on_save: Callable[[RunResult], None] | None = None):
        self.providers = providers
        self.budget_usd = budget_usd
        self.concurrency = concurrency
        self.use_skeptic = use_skeptic and providers.skeptic is not None
        self.on_event = on_event
        self.on_save = on_save
        self.lock = Lock()
        self.meter: Meter | None = None
        self.sequence = 0

    # Events and snapshots --------------------------------------------------------------------------------------
    def emit(self, stage: str, message: str, company: str | None = None, level: str = "info"):
        with self.lock:
            self.sequence += 1
            event = AgentEvent(seq=self.sequence, at=self.providers.clock(), stage=stage, message=message[:500],
                               company=company, level=level)
        if self.on_event:
            self.on_event(event)

    def save(self, result: RunResult):
        if self.on_save is None:
            return
        with self.lock:
            if self.meter is not None:
                with self.meter.lock:
                    snapshot = result.model_copy(deep=True)
            else:
                snapshot = result.model_copy(deep=True)
        self.on_save(snapshot)

    def calls(self, result: RunResult) -> Calls:
        self.meter = Meter(result.telemetry)
        return Calls(self.meter, self.providers.investigator, self.providers.skeptic if self.use_skeptic else None)

    # Run -------------------------------------------------------------------------------------------------------
    def run(self, website: str, overrides: Overrides | None = None, *, run_id: str | None = None,
            domains: list[str] | None = None, reading: Interpretation | None = None,
            history: dict[str, dict] | None = None) -> RunResult:
        """history: companies already researched for this seller (storage.prior_research); discovery sets them aside."""
        self.history = history or {}
        overrides = overrides or Overrides()
        result = RunResult(website=website, status="running", skeptic=self.use_skeptic,
                           synthetic=self.providers.synthetic, overrides=overrides,
                           company_count=overrides.company_count or (len(domains) if domains else DEFAULT_COMPANIES),
                           telemetry=Telemetry(budget_usd=self.budget_usd))
        if run_id:
            result.id = run_id
        calls = self.calls(result)
        started = time.monotonic()
        self.emit("run", f"Started research for {website}")
        self.save(result)
        try:
            self._run(result, calls, overrides, domains, reading)
        except BudgetReached:
            self.emit("run", "Run budget reached; no new model calls were started", level="warn")
            result.status = "complete"
        except (AgentProviderError, AgentOutputError, FetchError) as exc:
            result.status, result.error = "failed", str(exc)[:500]
            self.emit("run", f"Stopped: {result.error}", level="warn")
        finally:
            result.telemetry.elapsed_ms += int((time.monotonic() - started) * 1000)
            if result.status == "running":
                result.status = "complete"
            if result.status in ("complete", "failed"):
                result.finished_at = self.providers.clock()
            self.save(result)
        if result.status == "complete":
            counts = {kind: sum(1 for c in result.companies if c.verdict and c.verdict.kind == kind)
                      for kind in VERDICT_LABEL}
            self.emit("run", f"Done: {counts['shortlisted']} shortlisted, {counts['needs_look']} need a look, "
                             f"{counts['rejected']} rejected", level="done")
        return result

    def _run(self, result: RunResult, calls: Calls, overrides: Overrides, domains: list[str] | None,
             reading: Interpretation | None):
        fetcher = self.providers.fetcher
        chosen = reading is not None or bool(overrides.offer and overrides.buyer)
        hint = (reading.offer, reading.buyer) if reading else \
            (overrides.offer, overrides.buyer) if overrides.offer and overrides.buyer else None
        profile = understand_seller(result.website, calls, fetcher, self.emit, result.dropped, hint=hint)
        calls.meter.fetched(len(profile.pages))
        result.profile = profile
        assumptions.apply_reading(result, overrides, reading)
        self.save(result)
        if not (profile.offer and profile.buyer and profile.fit_criteria):
            if profile.interpretations and not chosen:
                result.status = "needs_choice"
                self.emit("seller", "Your site can be read more than one way: choose the closest reading", level="warn")
            else:
                result.status = "failed"
                result.error = ("We could not tell what you sell and to whom from your website. You can optionally "
                                "describe your offer and buyer in a sentence each and run again.")
                self.emit("seller", result.error, level="warn")
            return
        competitors = find_competitors(profile, comparison_pages(profile), calls, fetcher, self.emit, result.dropped)
        result.competitors = competitors
        changes = assumptions.apply(result, overrides)
        if not changes.count_changed and overrides.company_count is None and domains:
            result.company_count = len(domains)
        self.save(result)
        if domains:
            refs = [CandidateRef(domain=domain, name=domain, url=f"https://{domain}/", found_via="your list")
                    for domain in domains]
        else:
            refs, aside = discover(profile, result.competitors, result.company_count, calls, self.emit,
                                   prior=getattr(self, "history", {}), boards=self.providers.job_boards)
            result.set_aside = aside
        result.candidate_pool = refs
        self.research(result, calls, refs[:result.company_count])

    def research(self, result: RunResult, calls: Calls, refs: list[CandidateRef]):
        """Research refs; a company whose homepage cannot be read (blocked, gone, or redirecting to another domain) is
        set aside and the next untried candidate takes its place. Live runs lost up to two of three slots this way,
        and an unreadable homepage stops before any model call, so a replacement costs only its own research."""
        tried: set[str] = set()
        while refs:
            tried |= {ref.domain for ref in refs}
            self._research(result, calls, refs)
            batch = {ref.domain for ref in refs}
            unreadable = [c for c in result.companies if c.domain in batch and c.error == HOMEPAGE_UNREADABLE]
            if not unreadable or calls.meter.telemetry.budget_reached:
                return
            with self.lock:
                gone = {c.domain for c in unreadable}
                result.companies = [c for c in result.companies if c.domain not in gone]
                for company in unreadable:
                    reason = (company.blocked[0].split(": ", 1)[-1] if company.blocked else "no response")[:300]
                    result.set_aside.append(SetAside(domain=company.domain, url=company.url,
                                                     reason=f"Website could not be read: {reason}"))
                taken = {c.domain for c in result.companies}
                refs = [ref for ref in result.candidate_pool if ref.domain not in tried and ref.domain not in taken]
                refs = refs[:len(unreadable)]
            self.emit("investigation", f"{len(unreadable)} website(s) could not be read; "
                      + (f"researching {len(refs)} more candidate(s) instead" if refs else "no more candidates to try"),
                      level="warn")
            self.save(result)

    def _research(self, result: RunResult, calls: Calls, refs: list[CandidateRef]):
        with self.lock:
            known = {c.domain for c in result.companies}
            for ref in refs:
                if ref.domain not in known:
                    result.companies.append(CompanyResult(domain=ref.domain, name=ref.name, url=ref.url,
                                                          found_via=ref.found_via))
        self.save(result)
        ctx = Context(calls=calls, fetcher=self.providers.fetcher, profile=result.profile, competitors=result.competitors,
                      rules=result.disqualifiers, emit=self.emit, dropped=result.dropped,
                      job_boards=self.providers.job_boards)
        self.emit("investigation", f"Investigating {len(refs)} companies, {self.concurrency} at a time")
        with ThreadPoolExecutor(max_workers=self.concurrency) as pool:
            for _ in pool.map(lambda ref: self.process(result, calls, ctx, ref), refs):
                pass

    def process(self, result: RunResult, calls: Calls, ctx: Context, ref: CandidateRef):
        if calls.meter.telemetry.budget_reached:
            company = CompanyResult(domain=ref.domain, name=ref.name, url=ref.url, found_via=ref.found_via,
                                    status="budget_reached")
        else:
            self.emit("investigation", f"Investigating {ref.domain}", company=ref.domain)
            self.replace(result, CompanyResult(domain=ref.domain, name=ref.name, url=ref.url, found_via=ref.found_via,
                                               status="investigating"))
            company = Investigation(ref, ctx).run()
        company.evidence += self.profile_evidence(result, company)
        if company.evidence and company.status != "budget_reached":
            self.emit("skeptic", f"Skeptic checking {len(company.evidence)} quotes", company=ref.domain)
        company.decisions = judge(company, result.profile, result.disqualifiers, calls, use_skeptic=self.use_skeptic)
        company.verdict = decide(company, result.profile, result.disqualifiers, self.providers.clock().date(),
                                 result.overrides.exclusions)
        self.add_pitch(result, company, calls)
        company.cost_usd = calls.meter.company_cost(ref.domain)
        self.replace(result, company)
        self.emit("verdict", f"{ref.domain}: {VERDICT_LABEL[company.verdict.kind]}", company=ref.domain, level="done")

    def add_pitch(self, result: RunResult, company: CompanyResult, calls: Calls):
        """Why now and an opening line for a Shortlisted company; any other verdict has none."""
        if company.verdict is None or company.verdict.kind != "shortlisted":
            company.pitch = None
            return
        if company.pitch is not None:
            return
        self.emit("outreach", "Writing why now and an opening line from the supported quotes", company=company.domain)
        company.pitch = pitch_or_none(company, result.profile, calls, use_skeptic=self.use_skeptic,
                                      dropped=result.dropped)
        if company.pitch is None:
            self.emit("outreach", "No opening line kept: nothing it said could be checked against the quotes",
                      company=company.domain, level="warn")

    def replace(self, result: RunResult, company: CompanyResult):
        with self.lock:
            result.companies = [company if c.domain == company.domain else c for c in result.companies]
        self.save(result)

    @staticmethod
    def profile_evidence(result: RunResult, company: CompanyResult) -> list[EvidenceItem]:
        """A company that is a direct competitor or a named customer is disqualified by quotes already checked."""
        items = []
        present = {e.criterion_id for e in company.evidence}
        competitor = next((c for c in result.competitors if c.domain == company.domain and c.classification == "direct"), None)
        if competitor and competitor.same_job and "is_competitor" not in present:
            items.append(EvidenceItem(claim_type="disqualifier", criterion_id="is_competitor", found_by="profile",
                                      claim=f"{competitor.name} sells the same kind of product to the same buyers",
                                      quote=competitor.same_job))
        customer = next((c for c in result.profile.existing_customers if c.domain == company.domain), None)
        if customer and "is_existing_customer" not in present:
            items.append(EvidenceItem(claim_type="disqualifier", criterion_id="is_existing_customer", found_by="profile",
                                      claim=f"Your site names {customer.name} as a customer", quote=customer.quotes[0]))
        return items

    # Overrides -------------------------------------------------------------------------------------------------
    def reevaluate(self, result: RunResult, overrides: Overrides) -> RunResult:
        """Apply corrections. Skeptic and verdict re-run on saved evidence; only an added criterion re-researches."""
        merged = assumptions.merge(result.overrides, overrides)
        calls = self.calls(result)
        started = time.monotonic()
        result.status = "running"
        try:
            changes = assumptions.apply(result, merged)
            self.emit("overrides", "Applying your changes to the saved evidence")
            direct = [c for c in changes.added_competitors if c.classification == "direct"]
            removed = {f"uses_direct_competitor:{domain}" for domain in changes.removed_competitors}
            for index, company in enumerate(result.companies):
                if company.status not in ("done", "budget_reached"):
                    continue
                company = company.model_copy(deep=True)
                company.evidence = [e for e in company.evidence if e.criterion_id not in removed]
                rejudge = {e.id for e in company.evidence if e.claim_type == "fit" and e.criterion_id in changes.edited_criteria}
                if changes.target_size_changed:  # the size rule's text changed, so its quotes are judged again
                    rejudge |= {e.id for e in company.evidence if e.criterion_id == TARGET_SIZE_RULE}
                for competitor in direct:
                    for sig in company.signatures:
                        for item in scan(sig, [competitor], company.name or company.domain):
                            if all(e.quote.text != item.quote.text or e.criterion_id != item.criterion_id
                                   for e in company.evidence):
                                company.evidence.append(item)
                                rejudge.add(item.id)
                    place = f"saved page code rescanned for {competitor.name} (no new search)"
                    if company.signatures and place not in company.checked_places:
                        company.checked_places.append(place)
                company.evidence += self.profile_evidence(result, company)
                rejudge |= {e.id for e in company.evidence if e.id not in {d.evidence_id for d in company.decisions}}
                if rejudge:
                    self.emit("skeptic", f"Skeptic re-checking {len(rejudge)} quotes", company=company.domain)
                    company.decisions = judge(company, result.profile, result.disqualifiers, calls,
                                              use_skeptic=self.use_skeptic, only=rejudge)
                else:
                    company.decisions = [d for d in company.decisions if any(e.id == d.evidence_id for e in company.evidence)]
                company.verdict = decide(company, result.profile, result.disqualifiers, self.providers.clock().date(),
                                         merged.exclusions)
                if company.pitch is not None and rejudge & set(company.pitch.evidence_ids):
                    company.pitch = None  # a quote it was written from was judged again
                self.add_pitch(result, company, calls)
                company.cost_usd = calls.meter.company_cost(company.domain)
                result.companies[index] = company
            self.save(result)
            if changes.needs_research:
                self.emit("overrides", "A new fit check was added: researching the companies again")
                refs = [CandidateRef(domain=c.domain, name=c.name, url=c.url, found_via=c.found_via)
                        for c in result.companies]
                result.companies = []
                self.research(result, calls, refs)
            elif len(result.companies) < result.company_count:
                more = [r for r in result.candidate_pool if r.domain not in {c.domain for c in result.companies}]
                more = more[:result.company_count - len(result.companies)]
                if more:
                    self.research(result, calls, more)
                else:
                    self.emit("overrides", "No more saved candidates to research; start a new run to search again",
                              level="warn")
        except BudgetReached:
            self.emit("overrides", "Run budget reached; no new model calls were started", level="warn")
        except (AgentProviderError, AgentOutputError, FetchError) as exc:
            self.emit("overrides", f"Could not finish applying changes: {exc}", level="warn")
        finally:
            result.status = "complete"
            result.finished_at = self.providers.clock()
            result.telemetry.elapsed_ms += int((time.monotonic() - started) * 1000)
            self.save(result)
        self.emit("overrides", "Changes applied", level="done")
        return result


def comparison_pages(profile: SellerProfile) -> list[str]:
    """The seller's own comparison pages that were read, for the competitor search."""
    return [page.url for page in profile.pages if COMPARISON.search(urlsplit(page.url).path)]
