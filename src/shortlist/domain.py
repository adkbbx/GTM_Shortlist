from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return uuid4().hex


class Value(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Criterion(Value):
    id: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=3, max_length=500)
    required: bool = True


class Profile(Value):
    id: str = Field(default_factory=new_id)
    seller_url: str
    offer: str = Field(min_length=10, max_length=4000)
    target: str = Field(min_length=5, max_length=2000)
    criteria: tuple[Criterion, ...] = Field(min_length=1, max_length=12)
    exclusions: tuple[str, ...] = ()
    confirmed_at: datetime = Field(default_factory=utcnow)

    @model_validator(mode="after")
    def unique_criteria(self):
        if len({c.id for c in self.criteria}) != len(self.criteria):
            raise ValueError("Criterion IDs must be unique")
        return self


class Source(Value):
    id: str = Field(default_factory=new_id)
    url: str
    company_domain: str
    title: str
    text: str = Field(min_length=1)
    content_hash: str
    retrieved_at: datetime = Field(default_factory=utcnow)
    published_at: datetime | None = None


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


class Hypothesis(Value):
    text: str = Field(min_length=5, max_length=1500)
    assumptions: tuple[str, ...] = Field(min_length=1)


class Research(Value):
    id: str = Field(default_factory=new_id)
    domain: str
    name: str
    profile_id: str
    findings: tuple[Finding, ...]
    hypotheses: tuple[Hypothesis, ...] = ()
    sources: tuple[Source, ...]
    qualification: Literal["fits", "needs_verification", "does_not_fit"]
    status: Literal["complete", "partial"]
    unknowns: tuple[str, ...] = ()


class Review(Value):
    decision: Literal["accepted", "rejected", "needs_research"]
    reason: str = Field(default="", max_length=2000)
    reviewed_at: datetime = Field(default_factory=utcnow)


class Candidate(Value):
    domain: str
    name: str
    url: str
    query: str
    provider: str
    discovered_at: datetime = Field(default_factory=utcnow)


def qualify(profile: Profile, findings: tuple[Finding, ...]) -> str:
    by_id = {f.criterion_id: f for f in findings}
    required = [by_id.get(c.id) for c in profile.criteria if c.required]
    if any(f and f.status == "contradicted" for f in required):
        return "does_not_fit"
    if any(f is None or f.status == "unknown" for f in required):
        return "needs_verification"
    return "fits"
