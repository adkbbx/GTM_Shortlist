"""Public-role provenance and verification mechanics using labelled fixtures only."""
import hashlib

import pytest
from bs4 import BeautifulSoup
from pydantic import ValidationError

from shortlist.domain import Criterion, Profile, Research, Source
from shortlist.fetch import research_links
from shortlist.providers import ProviderError, validate_extraction
from shortlist.verification import Judgment, Verification, apply_verification, assessments, unavailable


@pytest.fixture
def observation():
    profile = Profile(seller_url="https://seller.example/", offer="Customer acquisition experiments",
                      target="Business software companies", criteria=(Criterion(id="product", description="Sells software"),))
    text = "Our leadership team: Jane Example is our Chief Executive Officer."
    source = Source(url="https://company.example/team", company_domain="company.example", title="Labelled fixture",
                    text=text, content_hash=hashlib.sha256(text.encode()).hexdigest())
    raw = {"name": "Company fixture", "findings": [], "people": [{"name": "Jane Example",
           "role": "Chief Executive Officer", "evidence": {"source_id": source.id, "passage": text,
           "claim": "Jane Example is Chief Executive Officer at this company."}}]}
    return profile, source, raw


def test_only_verified_current_role_survives_without_changing_fit(observation):
    profile, source, raw = observation
    record = validate_extraction(raw, profile, "company.example", (source,))
    item = assessments(profile, record)[0]
    assert item["assessment_id"] == "person:" + record.people[0].id
    final = apply_verification(profile, record, Verification(judgments=[Judgment(
        assessment_id=item["assessment_id"], verdict="entailed", reason="Explicit current team role in labelled fixture")]))
    assert final.people == record.people
    assert final.sources == record.sources
    assert final.qualification == "needs_verification"
    assert final.people[0].evidence.source_id == source.id


@pytest.mark.parametrize("defect", ["unknown_source", "foreign_domain", "foreign_url", "invented_passage",
                                   "missing_name", "missing_role", "substring_name"])
def test_people_need_owned_exact_passage_and_explicit_name_and_role(observation, defect):
    profile, source, raw = observation
    person = raw["people"][0]
    if defect == "unknown_source":
        person["evidence"]["source_id"] = "missing"
    elif defect == "foreign_domain":
        source = source.model_copy(update={"company_domain": "other.example"})
    elif defect == "foreign_url":
        source = source.model_copy(update={"url": "https://other.example/team"})
    elif defect == "invented_passage":
        person["evidence"]["passage"] = "Jane Example is our Chief Executive Officer and owns our purchasing budget."
    elif defect == "missing_name":
        person["name"] = "Someone Else"
    elif defect == "missing_role":
        person["role"] = "Chief Technology Officer"
    else:
        person["name"] = "Ane Example"
    people = validate_extraction(raw, profile, "company.example", (source,)).people
    if defect == "unknown_source":
        # The exact quote is on the company's own saved page, so it is re-attributed there rather than lost.
        assert [p.evidence.source_id for p in people] == [source.id]
    else:
        assert not people


@pytest.mark.parametrize("text", [
    'Customer testimonial: Jane Example, Chief Executive Officer at ClientCo, says "great service".',
    "Jane Example was our Chief Executive Officer until 2020 and has left the company.",
    "Jane Example is an independent advisor. We are hiring a Chief Executive Officer.",
    "Article by Jane Example about the Chief Executive Officer role at other companies.",
])
@pytest.mark.parametrize("verdict", ["unsupported", "uncertain", None])
def test_word_matches_do_not_bypass_employment_verification(observation, text, verdict):
    profile, source, raw = observation
    source = source.model_copy(update={"text": text})
    raw["people"][0]["evidence"]["passage"] = text
    proposed = validate_extraction(raw, profile, "company.example", (source,))
    assert len(proposed.people) == 1  # Structural validation cannot establish attribution or current employment.
    audit = Verification(judgments=[] if verdict is None else [Judgment(
        assessment_id="person:" + proposed.people[0].id, verdict=verdict, reason="Current employment not established")])
    assert not apply_verification(profile, proposed, audit).people
    assert not unavailable(profile, proposed, "Labelled outage").people


def test_duplicate_names_and_ids_rejected_and_old_records_still_load(observation):
    profile, source, raw = observation
    raw["people"] *= 2
    with pytest.raises(ProviderError, match="duplicate people"):
        validate_extraction(raw, profile, "company.example", (source,))
    raw["people"] = []
    record = validate_extraction(raw, profile, "company.example", (source,))
    saved = record.model_dump(mode="json", exclude={"people"})
    assert Research.model_validate(saved).people == ()
    saved["people"] = [{"name": "Jane Example", "role": "Chief Executive Officer", "evidence": {
        "source_id": source.id, "passage": source.text, "claim": "Jane Example is Chief Executive Officer."},
        "email": "invented@example.com"}]
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        Research.model_validate(saved)


def test_observed_team_page_is_bounded_and_preferred_to_product_pages():
    soup = BeautifulSoup('<a href="/products">Product</a><a href="/leadership">Team</a>'
                         '<a href="/about">About</a><a href="https://other.example/team">Other team</a>'
                         '<a href="https://linkedin.com/in/somebody">Person</a>', "html.parser")
    assert research_links("https://company.example/", soup) == (
        "https://company.example/about", "https://company.example/leadership")
