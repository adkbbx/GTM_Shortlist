"""Sourced overview gate mechanics, not a claim about live model accuracy."""
import hashlib

import pytest
from pydantic import ValidationError

from shortlist.domain import Criterion, Profile, Research, Source
from shortlist.providers import ProviderError, validate_extraction
from shortlist.verification import Judgment, Verification, apply_verification, assessments, unavailable


@pytest.fixture
def overview():
    profile = Profile(seller_url="https://seller.example/", offer="Acquisition experiments for software teams",
                      target="Business software companies", criteria=(Criterion(id="software", description="Sells software"),))
    text = "We build workflow software. Our headquarters are in Toronto. We had 24 employees in June 2025."
    source = Source(url="https://company.example/about", company_domain="company.example", title="Labelled fixture",
                    text=text, content_hash=hashlib.sha256(text.encode()).hexdigest())
    facts = [{"kind": kind, "evidence": {"source_id": source.id, "passage": passage, "claim": claim}}
             for kind, passage, claim in [
                 ("description", "We build workflow software.", "Workflow software."),
                 ("location", "Our headquarters are in Toronto.", "Headquarters in Toronto."),
                 ("team_size", "We had 24 employees in June 2025.", "24 employees in June 2025.")]]
    raw = {"name": "Labelled company", "findings": [], "company_facts": facts}
    return profile, source, raw


def test_overview_is_separate_from_fit_and_keeps_source_dates(overview):
    profile, source, raw = overview
    record = validate_extraction(raw, profile, source.company_domain, (source,))
    assert len(record.company_facts) == 3
    assert record.qualification == "needs_verification"
    audit = Verification(judgments=[Judgment(assessment_id=item["assessment_id"], verdict="entailed",
                                            reason="Labelled fixture, preserves scope and date")
                                    for item in assessments(profile, record)])
    final = apply_verification(profile, record, audit)
    assert final.company_facts == record.company_facts
    assert final.company_facts[2].evidence.claim == "24 employees in June 2025."
    assert final.sources == (source,)
    assert final.qualification == "needs_verification"
    assert final.id == record.id


@pytest.mark.parametrize("defect", ["unknown_source", "wrong_company", "wrong_url", "invented_passage"])
def test_bad_fact_provenance_is_not_published(overview, defect):
    profile, source, raw = overview
    raw["company_facts"] = raw["company_facts"][:1]
    if defect == "unknown_source":
        raw["company_facts"][0]["evidence"]["source_id"] = "missing"
    elif defect == "wrong_company":
        source = source.model_copy(update={"company_domain": "someone-else.example"})
    elif defect == "wrong_url":
        source = source.model_copy(update={"url": "https://someone-else.example/about"})
    else:
        raw["company_facts"][0]["evidence"]["passage"] = "We run a spacecraft company."
    record = validate_extraction(raw, profile, "company.example", (source,))
    assert record.company_facts == ()


@pytest.mark.parametrize("verdict", ["unsupported", "uncertain", None])
def test_unverified_facts_are_removed_even_with_exact_quotes(overview, verdict):
    profile, source, raw = overview
    # A genuine customer count does not establish employee count. Quote matching alone cannot catch this.
    source = source.model_copy(update={"text": "We serve 24 customers in Toronto."})
    raw["company_facts"] = [{"kind": "team_size", "evidence": {"source_id": source.id,
        "passage": source.text, "claim": "24 employees."}}]
    record = validate_extraction(raw, profile, "company.example", (source,))
    assert len(record.company_facts) == 1
    audit = Verification(judgments=[] if verdict is None else [Judgment(assessment_id="company:team_size",
        verdict=verdict, reason="Customer count cannot establish employee count")])
    assert apply_verification(profile, record, audit).company_facts == ()
    assert unavailable(profile, record, "Labelled outage").company_facts == ()


def test_duplicate_facts_rejected_and_legacy_research_defaults_empty(overview):
    profile, source, raw = overview
    raw["company_facts"] = [raw["company_facts"][0]] * 2
    with pytest.raises(ProviderError, match="duplicate company fact"):
        validate_extraction(raw, profile, "company.example", (source,))
    raw.pop("company_facts")
    record = validate_extraction(raw, profile, "company.example", (source,))
    saved = record.model_dump(mode="json", exclude={"company_facts"})
    assert Research.model_validate(saved).company_facts == ()
    saved["company_facts"] = [{"kind": "invented_metric", "evidence": {}}]
    with pytest.raises(ValidationError):
        Research.model_validate(saved)
