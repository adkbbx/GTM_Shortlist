"""Separate semantic judgments; missing or inconclusive judgments never pass."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from shortlist.domain import (
    ExclusionUnknown,
    Profile,
    Research,
    Unknown,
    exclusion_id,
    qualify,
)


class Judgment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assessment_id: str = Field(min_length=3, max_length=100)
    verdict: Literal["entailed", "unsupported", "uncertain"]
    reason: str = Field(min_length=3, max_length=1000)


class Verification(BaseModel):
    model_config = ConfigDict(extra="forbid")
    judgments: list[Judgment] = Field(max_length=27)


def assessments(profile: Profile, record: Research) -> list[dict]:
    criteria = {c.id: c.description for c in profile.criteria}
    exclusions = {exclusion_id(i): text for i, text in enumerate(profile.exclusions)}
    result = []
    for finding in (*record.findings, *record.exclusion_findings):
        if finding.status == "unknown":
            continue
        is_exclusion = hasattr(finding, "exclusion_id")
        identity = finding.exclusion_id if is_exclusion else finding.criterion_id
        result.append({"assessment_id": ("exclusion:" if is_exclusion else "criterion:") + identity,
                       "condition": (exclusions if is_exclusion else criteria)[identity],
                       "proposed": finding.model_dump(mode="json")})
    conditions = {"description": "This company's own offering, described accurately with no invented capability",
                  "location": "This company's explicitly stated base or headquarters, preserving geographic scope",
                  "team_size": "This company's explicitly stated employee count or range, preserving scope and date"}
    for fact in record.company_facts:
        result.append({"assessment_id": "company:" + fact.kind, "condition": conditions[fact.kind],
                       "proposed": fact.model_dump(mode="json")})
    return result


def apply_verification(profile: Profile, record: Research, audit: Verification) -> Research:
    expected = {a["assessment_id"] for a in assessments(profile, record)}
    judgments = {}
    for judgment in audit.judgments:
        if judgment.assessment_id not in expected or judgment.assessment_id in judgments:
            raise ValueError("Verifier returned unknown or duplicate assessment IDs")
        judgments[judgment.assessment_id] = judgment

    def gate(finding, prefix, identity, unknown_type):
        if finding.status == "unknown":
            return finding
        judgment = judgments.get(prefix + identity)
        if judgment is not None and judgment.verdict == "entailed":
            return finding
        reason = ("Semantic verification missing" if judgment is None else
                  f"Semantic verification {judgment.verdict}: {judgment.reason}")
        return unknown_type(**{("exclusion_id" if prefix == "exclusion:" else "criterion_id"): identity},
                            reason=reason[:1000])

    findings = tuple(gate(f, "criterion:", f.criterion_id, Unknown) for f in record.findings)
    exclusions = tuple(gate(f, "exclusion:", f.exclusion_id, ExclusionUnknown) for f in record.exclusion_findings)
    unknowns = tuple(f.reason for f in (*findings, *exclusions) if f.status == "unknown")
    facts = tuple(fact for fact in record.company_facts
                  if (judgment := judgments.get("company:" + fact.kind)) is not None and judgment.verdict == "entailed")
    return record.model_copy(update={"findings": findings, "exclusion_findings": exclusions,
                                    "company_facts": facts,
                                    "qualification": qualify(profile, findings, exclusions),
                                    "status": "partial" if unknowns else "complete", "unknowns": unknowns})


def unavailable(profile: Profile, record: Research, reason: str) -> Research:
    audit = Verification(judgments=[Judgment(assessment_id=a["assessment_id"], verdict="uncertain",
                                            reason=reason[:1000]) for a in assessments(profile, record)])
    return apply_verification(profile, record, audit)
