"""Saved shapes of an agent run. Every claim shown to a person carries a Quote found in a fetched page.

There are no person, name or role fields: the agent qualifies companies only and never records or judges people.
"""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from shortlist.domain import new_id, utcnow

SourceType = Literal["own_site", "job_post", "news", "review", "competitor_site", "other"]
ClaimType = Literal["fit", "need", "timing", "disqualifier"]
Decision = Literal["supports", "contradicts", "insufficient"]
VerdictKind = Literal["shortlisted", "needs_look", "rejected"]
RuleKind = Literal["uses_direct_competitor", "is_competitor", "is_existing_customer",
                   "outside_stated_size_or_region", "inactive", "works_for_others"]
RunStatus = Literal["queued", "running", "needs_choice", "complete", "failed"]
CompanyStatus = Literal["pending", "investigating", "done", "budget_reached", "failed"]

BUDGET_REACHED = "Needs a look: budget reached"
MAX_COMPANIES = 20
DEFAULT_COMPANIES = 10


class Model(BaseModel):
    # Saved fields always appear in responses, so the generated browser types treat them as present.
    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)


class Quote(Model):
    """Exact words from a fetched page: location text means the readable page, html means the page's own code."""
    text: str = Field(min_length=1, max_length=1500)
    url: str
    source_type: SourceType
    published_date: date | None = None
    fetched_at: datetime
    location: Literal["text", "html"] = "text"
    # A job posting on an applicant-tracking system, read during the run and not marked closed (pages.open_posting).
    open_posting: bool = False


class Statement(Model):
    value: str = Field(min_length=1, max_length=1000)
    # The agent's statements always carry quotes; a statement you typed is your input, not a claim.
    quotes: list[Quote] = Field(default_factory=list, max_length=4)
    origin: Literal["agent", "interpretation", "user"] = "agent"


class FitCriterion(Model):
    id: str = Field(min_length=1, max_length=80)
    text: str = Field(min_length=3, max_length=500)
    required: bool = True
    enabled: bool = True
    quotes: list[Quote] = Field(default_factory=list, max_length=4)
    origin: Literal["agent", "user"] = "agent"


class Signal(Model):
    id: str = Field(min_length=1, max_length=80)
    kind: Literal["need", "timing"]
    text: str = Field(min_length=3, max_length=500)
    quotes: list[Quote] = Field(default_factory=list, max_length=4)
    # A common buying moment (a funding round, a launch) added when the seller's site gave none: a seller's site rarely
    # says when to buy, so live runs had no timing signal at all (vanta.com, crisp.chat). It is labelled, not quoted.
    standard: bool = False
    # A need a company shows on its own website (a trust or security page, compliance work it lists), so its own page
    # can prove it. Every other need must be shown elsewhere: a company's marketing cannot show that it needs help.
    own_site: bool = False

    @model_validator(mode="after")
    def quoted_unless_standard(self):
        if not self.standard and not self.quotes:
            raise ValueError("A signal inferred from the site needs a quote from it")
        return self


class ExistingCustomer(Model):
    name: str = Field(min_length=1, max_length=200)
    domain: str | None = None
    quotes: list[Quote] = Field(min_length=1, max_length=4)


class StatedLimit(Model):
    """Served size or region, only when the seller's own site states it."""
    kind: Literal["size", "region"]
    value: str = Field(min_length=2, max_length=300)
    quotes: list[Quote] = Field(min_length=1, max_length=4)


class Interpretation(Model):
    """One reading of a vague site, offered as a click; never a required text box."""
    id: str
    offer: str = Field(min_length=3, max_length=600)
    buyer: str = Field(min_length=3, max_length=600)
    quotes: list[Quote] = Field(min_length=1, max_length=3)


class PageRef(Model):
    url: str
    title: str = ""
    fetched_at: datetime


class SellerProfile(Model):
    website: str
    domain: str
    name: str = Field(default="", max_length=200)
    offer: Statement | None = None
    buyer: Statement | None = None
    existing_customers: list[ExistingCustomer] = Field(default_factory=list, max_length=30)
    fit_criteria: list[FitCriterion] = Field(default_factory=list, max_length=12)
    need_signals: list[Signal] = Field(default_factory=list, max_length=6)
    timing_signals: list[Signal] = Field(default_factory=list, max_length=6)
    stated_limits: list[StatedLimit] = Field(default_factory=list, max_length=4)
    # The size and stage of company the offer is written for, stated or inferred from the site. Without it the agent
    # researched HubSpot and Salesforce for a startup agency (30 Oct live runs).
    target_size: Statement | None = None
    interpretations: list[Interpretation] = Field(default_factory=list, max_length=3)
    pages: list[PageRef] = Field(default_factory=list, max_length=6)


class Competitor(Model):
    name: str = Field(min_length=1, max_length=200)
    domain: str
    classification: Literal["direct", "adjacent", "not_competitor"]
    same_job: Quote | None = None
    same_buyer: Quote | None = None
    reason: str = Field(default="", max_length=600)
    found_via: str = Field(default="", max_length=500)
    origin: Literal["agent", "user"] = "agent"


class DisqualifierRule(Model):
    id: str
    rule: RuleKind
    text: str = Field(min_length=3, max_length=500)
    competitor_domain: str | None = None
    enabled: bool = True


class EvidenceItem(Model):
    id: str = Field(default_factory=new_id)
    claim_type: ClaimType
    # Fit: a criterion id; need/timing: a signal id; disqualifier: a rule id.
    criterion_id: str
    claim: str = Field(min_length=3, max_length=600)
    quote: Quote
    found_by: Literal["model", "scan", "profile"] = "model"


class SkepticDecision(Model):
    evidence_id: str
    decision: Decision
    reason: str = Field(default="", max_length=600)
    decided_by: Literal["skeptic", "rule", "no_skeptic", "budget"]


class DroppedClaim(Model):
    """A model claim whose quote was not found in the fetched page. Logged here, never shown as evidence."""
    stage: str
    company: str | None = None
    claim_type: str = ""
    quote: str = Field(default="", max_length=1500)
    url: str = ""
    reason: str


class Attribute(Model):
    tag: str
    attr: str
    value: str = Field(max_length=2048)


class PageSignature(Model):
    """Compact code-level observations of one fetched page, kept so competitors added later can be checked
    without fetching again."""
    url: str
    kind: Literal["homepage", "integrations", "other"]
    fetched_at: datetime
    attributes: list[Attribute] = Field(default_factory=list, max_length=400)
    powered_by: list[str] = Field(default_factory=list, max_length=20)
    lines: list[str] = Field(default_factory=list, max_length=300)


class Verdict(Model):
    kind: VerdictKind
    summary: str
    missing: list[str] = Field(default_factory=list)
    # Shortlisted, but a size or region rule that no quote addressed either way: shown so a reader checks it.
    unconfirmed: list[str] = Field(default_factory=list)
    disqualifier: EvidenceItem | None = None
    rule: RuleKind | None = None


class OutreachEmail(Model):
    """A cold email for a Shortlisted company, drafted on request from quotes the skeptic supported."""
    subject: str = Field(max_length=120)
    body: str = Field(max_length=1500)
    evidence_ids: list[str] = Field(default_factory=list)
    checked: bool = False  # Muse Spark Open found every statement in the quotes
    reason: str = ""


class Pitch(Model):
    """Why now and an opening line for a Shortlisted company, written only from quotes the skeptic supported."""
    why_now: str = Field(max_length=400)
    opener: str = Field(max_length=600)
    evidence_ids: list[str] = Field(default_factory=list)
    checked: bool = False  # Muse Spark Open found every statement in the quotes
    reason: str = ""


LeadSignal = Literal["", "hiring", "news", "social", "lookalike"]


class CandidateRef(Model):
    domain: str
    name: str = ""
    url: str
    found_via: str = ""
    signal: LeadSignal = ""  # the kind of signal discovery found the company by
    source_url: str = ""  # the news article or post where discovery saw it; the investigation reads it first


class SetAside(Model):
    domain: str
    url: str = ""
    reason: str
    # Set when the company was researched for this seller in an earlier run: that run's id, to open it.
    previous_run: str | None = None


class CompanyResult(Model):
    domain: str
    name: str = ""
    url: str
    found_via: str = ""
    signal: LeadSignal = ""
    status: CompanyStatus = "pending"
    evidence: list[EvidenceItem] = Field(default_factory=list)
    decisions: list[SkepticDecision] = Field(default_factory=list)
    checked_places: list[str] = Field(default_factory=list)
    disqualifier_check_completed: bool = False
    blocked: list[str] = Field(default_factory=list)
    signatures: list[PageSignature] = Field(default_factory=list)
    searches: int = 0
    fetches: int = 0
    turns: int = 0
    verdict: Verdict | None = None
    pitch: Pitch | None = None
    outreach: OutreachEmail | None = None
    latency_ms: int = 0
    cost_usd: float = 0.0
    error: str | None = None


class ModelCall(Model):
    provider: str
    model: str
    operation: str
    company: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    searches: int = 0
    latency_ms: int = 0
    usd: float = 0.0
    ok: bool = True
    error: str | None = None


class Telemetry(Model):
    budget_usd: float
    budget_reached: bool = False
    cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    searches: int = 0
    model_calls: int = 0
    pages_fetched: int = 0
    elapsed_ms: int = 0
    calls: list[ModelCall] = Field(default_factory=list)


class CriterionOverride(Model):
    id: str = Field(min_length=1, max_length=80)
    text: str | None = Field(default=None, min_length=3, max_length=500)
    required: bool | None = None
    enabled: bool | None = None


class Overrides(Model):
    """Optional corrections merged on top of what the agent inferred. None is required."""
    add_competitors: list[str] = Field(default_factory=list, max_length=10)
    remove_competitors: list[str] = Field(default_factory=list, max_length=20)
    exclusions: list[str] = Field(default_factory=list, max_length=20)
    criteria: list[CriterionOverride] = Field(default_factory=list, max_length=12)
    company_count: int | None = Field(default=None, ge=1, le=MAX_COMPANIES)
    interpretation: str | None = Field(default=None, max_length=80)
    offer: str | None = Field(default=None, min_length=3, max_length=600)
    buyer: str | None = Field(default=None, min_length=3, max_length=600)
    target_size: str | None = Field(default=None, min_length=3, max_length=300)


class AgentEvent(Model):
    seq: int = 0
    at: datetime = Field(default_factory=utcnow)
    stage: Literal["seller", "competitors", "discovery", "investigation", "skeptic", "verdict", "outreach", "overrides", "run"]
    message: str = Field(max_length=500)
    company: str | None = None
    level: Literal["info", "warn", "done"] = "info"


class RunResult(Model):
    id: str = Field(default_factory=new_id)
    website: str
    status: RunStatus = "queued"
    created_at: datetime = Field(default_factory=utcnow)
    finished_at: datetime | None = None
    company_count: int = Field(default=DEFAULT_COMPANIES, ge=1, le=MAX_COMPANIES)
    skeptic: bool = True
    # Labelled synthetic run: invented companies and pages from shortlist.agent.synthetic, no network.
    synthetic: bool = False
    profile: SellerProfile | None = None
    competitors: list[Competitor] = Field(default_factory=list)
    disqualifiers: list[DisqualifierRule] = Field(default_factory=list)
    overrides: Overrides = Field(default_factory=Overrides)
    companies: list[CompanyResult] = Field(default_factory=list)
    candidate_pool: list[CandidateRef] = Field(default_factory=list)
    set_aside: list[SetAside] = Field(default_factory=list)
    dropped: list[DroppedClaim] = Field(default_factory=list)
    telemetry: Telemetry
    error: str | None = None
