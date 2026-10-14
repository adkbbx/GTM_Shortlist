from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return uuid4().hex


class Value(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, json_schema_serialization_defaults_required=True)


class Criterion(Value):
    id: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=3, max_length=500)
    required: bool = True


ExclusionText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)]


def exclusion_id(index: int) -> str:
    return f"exclude-{index + 1}"


class Target(Value):
    offer: str = Field(min_length=10, max_length=4000)
    target: str = Field(min_length=5, max_length=2000)
    criteria: tuple[Criterion, ...] = Field(min_length=1, max_length=12)
    exclusions: tuple[ExclusionText, ...] = Field(default=(), max_length=12)

    @model_validator(mode="after")
    def unique_criteria(self):
        if len({c.id for c in self.criteria}) != len(self.criteria):
            raise ValueError("Criterion IDs must be unique")
        if len({e.casefold() for e in self.exclusions}) != len(self.exclusions):
            raise ValueError("Exclusions must be unique")
        return self


class Profile(Target):
    id: str = Field(default_factory=new_id)
    seller_url: str
    confirmed_at: datetime = Field(default_factory=utcnow)


class Source(Value):
    id: str = Field(default_factory=new_id)
    url: str
    company_domain: str
    title: str
    text: str = Field(min_length=1)
    content_hash: str
    retrieved_at: datetime = Field(default_factory=utcnow)
    published_at: datetime | None = None
    research_links: tuple[str, ...] = Field(default=(), max_length=2)


class Evidence(Value):
    source_id: str
    passage: str = Field(min_length=15, max_length=1500)
    claim: str = Field(min_length=3, max_length=1500)


class Observed(Value):
    status: Literal["supported", "contradicted"]
    criterion_id: str
    evidence: tuple[Evidence, ...] = Field(min_length=1, max_length=6)


class Unknown(Value):
    status: Literal["unknown"] = "unknown"
    criterion_id: str
    reason: str = Field(min_length=3, max_length=1000)


Finding = Annotated[Observed | Unknown, Field(discriminator="status")]


class ExclusionObserved(Value):
    status: Literal["matched", "cleared"]
    exclusion_id: str
    evidence: tuple[Evidence, ...] = Field(min_length=1, max_length=6)


class ExclusionUnknown(Value):
    status: Literal["unknown"] = "unknown"
    exclusion_id: str
    reason: str = Field(min_length=3, max_length=1000)


ExclusionFinding = Annotated[ExclusionObserved | ExclusionUnknown, Field(discriminator="status")]


class Hypothesis(Value):
    text: str = Field(min_length=5, max_length=1500)
    assumptions: tuple[str, ...] = Field(min_length=1)


class Research(Value):
    id: str = Field(default_factory=new_id)
    domain: str
    name: str
    profile_id: str
    findings: tuple[Finding, ...]
    exclusion_findings: tuple[ExclusionFinding, ...] = ()
    hypotheses: tuple[Hypothesis, ...] = ()
    sources: tuple[Source, ...]
    qualification: Literal["fits", "needs_verification", "does_not_fit"]
    status: Literal["complete", "partial"]
    unknowns: tuple[str, ...] = ()


class Review(Value):
    decision: Literal["accepted", "rejected", "needs_research"]
    reason: str = Field(default="", max_length=2000)
    reviewed_at: datetime = Field(default_factory=utcnow)


class OperatorNoteBase(Value):
    reviewer: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)]
    note: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=2000)]
    source_ids: tuple[str, ...] = Field(default=(), max_length=21)

    @model_validator(mode="after")
    def unique_sources(self):
        if len(set(self.source_ids)) != len(self.source_ids):
            raise ValueError("Inspected source references must be unique")
        return self


class OperatorReviewed(OperatorNoteBase):
    outcome: Literal["reviewed"] = "reviewed"
    source_ids: tuple[str, ...] = Field(min_length=1, max_length=21)


class OperatorNeedsResearch(OperatorNoteBase):
    outcome: Literal["needs_research"] = "needs_research"


OperatorNote = Annotated[OperatorReviewed | OperatorNeedsResearch, Field(discriminator="outcome")]


class OperatorReview(Value):
    id: str = Field(default_factory=new_id)
    annotation: OperatorNote
    research_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    reviewed_at: datetime = Field(default_factory=utcnow)


class OperatorReviewCommand(Value):
    run_id: str = Field(min_length=1, max_length=100)
    record_id: str = Field(min_length=1, max_length=100)
    request_key: str = Field(min_length=8, max_length=100)
    previous_id: str | None = Field(default=None, min_length=1, max_length=100)
    annotation: OperatorNote


class Candidate(Value):
    domain: str
    name: str
    url: str
    query: str
    provider: str
    discovered_at: datetime = Field(default_factory=utcnow)
    excerpt: str = Field(default="", max_length=3000)


def qualify(profile: Profile, findings: tuple[Finding, ...], exclusions: tuple[ExclusionFinding, ...] = ()) -> str:
    by_id = {f.criterion_id: f for f in findings}
    required = [by_id.get(c.id) for c in profile.criteria if c.required]
    by_exclusion = {f.exclusion_id: f for f in exclusions}
    checks = [by_exclusion.get(exclusion_id(i)) for i in range(len(profile.exclusions))]
    if any(f and f.status == "contradicted" for f in required) or any(f and f.status == "matched" for f in checks):
        return "does_not_fit"
    if any(f is None or f.status == "unknown" for f in [*required, *checks]):
        return "needs_verification"
    return "fits"


def read_research(profile: Profile, raw: dict) -> Research:
    """Project old snapshots with visible unassessed exclusions, without rewriting them."""
    record = Research.model_validate(raw)
    by_id = {f.exclusion_id: f for f in record.exclusion_findings}
    checks = tuple(by_id.get(exclusion_id(i), ExclusionUnknown(exclusion_id=exclusion_id(i),
                   reason="This exclusion was not assessed in the saved research")) for i in range(len(profile.exclusions)))
    reasons = tuple(f.reason for f in checks if f.status == "unknown")
    return record.model_copy(update={"exclusion_findings": checks, "qualification": qualify(profile, record.findings, checks),
                                    "status": "partial" if reasons else record.status,
                                    "unknowns": tuple(dict.fromkeys((*record.unknowns, *reasons)))})
