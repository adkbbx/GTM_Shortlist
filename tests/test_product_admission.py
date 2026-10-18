"""Labelled synthetic targets/drafts plus the recorded discovery corpus. No providers."""
import json
import sqlite3
from copy import deepcopy

import pytest

from scripts.measure_product_admission import labelled, saved
from shortlist.domain import Candidate, Evidence, Observed, Profile, Unknown, qualify
from shortlist.providers import recover_customer_draft
from shortlist.relevance import candidate_issue


@pytest.mark.parametrize("title,opening", [
    ("Mike Sonders | Digital Marketing Consultant", ""),
    ("Labelled | SaaS marketing agency", ""),
    ("Labelled consultancy", ""),
    ("Labelled freelancer", ""),
    ("Labelled business coach", ""),
    ("Labelled services firm", ""),
    ("Labelled", "Labelled is a consultancy for SaaS teams."),
])
def test_service_identity_is_set_aside_only_for_product_targets(title, opening):
    candidate = Candidate(domain="labelled.example", url="https://labelled.example/", name=title,
                          excerpt=opening, query="B2B SaaS software company official website", provider="fixture")
    assert candidate_issue(candidate) == "Sells services to this market rather than being in it"
    assert candidate_issue(candidate, policy=3) is None
    for target in ("Agencies for SaaS companies", "Freelancers and consultants", "Consultancies selling to software companies",
                   "Business coaches", "Service providers for startups"):
        assert candidate_issue(candidate, target=target) is None


@pytest.mark.parametrize("title,opening", [
    ("Labelled | Software for agencies and consultants", ""),
    ("Labelled | Agency management software", ""),
    ("Labelled | B2B software", "Our customers include consultants and agencies."),
    ("Labelled | SaaS platform", "Labelled is a software platform for consultants."),
])
def test_customers_are_not_mistaken_for_the_business(title, opening):
    candidate = Candidate(domain="labelled.example", url="https://labelled.example/", name=title,
                          excerpt=opening, query="B2B SaaS companies", provider="fixture")
    assert candidate_issue(candidate) is None


DRAFT = {"seller_offer": "Labelled customer-acquisition experiments", "target_customer": "B2B and SaaS companies seeking predictable acquisition",
         "customer_criteria": [
             {"id": "b2b", "subject": "target_customer", "customer_characteristic": "Operates in the B2B sector", "required": True},
             {"id": "saas", "subject": "target_customer", "customer_characteristic": "Provides SaaS or specialized business software", "required": False},
             {"id": "funding", "subject": "target_customer", "customer_characteristic": "Seed or Series A funding stage", "required": True}]}


def test_defining_product_check_is_required_and_private_checks_remain_optional():
    raw = deepcopy(DRAFT)
    draft = recover_customer_draft(raw)
    assert {c.id: c.required for c in draft.criteria} == {"b2b": True, "saas": True, "funding": False}
    profile = Profile(seller_url="https://seller.example/", offer=draft.offer, target=draft.target, criteria=tuple(draft.criteria))
    b2b = Observed(status="supported", criterion_id="b2b", evidence=(Evidence(
        source_id="labelled-source", passage="Labelled company serves businesses.", claim="Operates in B2B"),))
    unknown = Unknown(criterion_id="saas", reason="Own product unestablished")
    assert qualify(profile, (b2b, unknown)) == "needs_verification"
    legacy = profile.model_copy(update={"criteria": tuple(recover_customer_draft(raw, policy=3).criteria)})
    assert qualify(legacy, (b2b, unknown)) == "fits"
    assert raw == DRAFT
    assert not recover_customer_draft(raw, policy=3).criteria[1].required


@pytest.mark.parametrize("description", [None, "Works with SaaS companies", "Provides consulting services to SaaS companies",
                                         "Sells software to SaaS companies with Series A funding"])
def test_missing_or_customer_facing_product_check_gets_an_observable_category_proposal(description):
    raw = {**DRAFT, "customer_criteria": DRAFT["customer_criteria"][:1]}
    if description:
        raw["customer_criteria"] = [*raw["customer_criteria"], {"id": "target-product", "subject": "target_customer",
                                                           "customer_characteristic": description, "required": False}]
    draft = recover_customer_draft(raw)
    assert any(c.description == "Provides SaaS or business software as its own product" and c.required for c in draft.criteria)
    assert len({c.id for c in draft.criteria}) == len(draft.criteria)


def test_labelled_measurement_preserves_target_companies_and_removes_service_providers():
    report = labelled()
    assert report["3"]["admitted_labelled_service_providers"] == 2
    assert report["4"]["admitted_labelled_service_providers"] == 0
    assert report["3"]["admitted_labelled_target_companies"] == report["4"]["admitted_labelled_target_companies"] == 8
    assert not report["4"]["lost_labelled_target_companies"]


@pytest.mark.parametrize("journalled", [True, False])
def test_saved_measurement_is_read_only_and_deduplicates_databases(tmp_path, journalled):
    path = tmp_path / "labelled.sqlite3"
    db = sqlite3.connect(path)
    db.executescript("CREATE TABLE runs(id,profile,checkpoint,deleted_at); CREATE TABLE attempts(id,run_id,operation_key,kind); "
                     "CREATE TABLE attempt_results(attempt_id,payload);")
    candidate = Candidate(domain="labelled.example", url="https://labelled.example/", name="Labelled consultant",
                          query="B2B SaaS companies", provider="fixture")
    checkpoint = {} if journalled else {"discovered": [candidate.model_dump(mode="json"),
        candidate.model_copy(update={"query": "SaaS pricing"}).model_dump(mode="json")]}
    db.execute("INSERT INTO runs VALUES (?,?,?,NULL)", ("fixture-run",
        json.dumps({"seller_url": "https://eygentic.com/", "target": "SaaS companies"}), json.dumps(checkpoint)))
    if journalled:
        db.execute("INSERT INTO attempts VALUES ('a','fixture-run','search:0','search')")
        db.execute("INSERT INTO attempt_results VALUES ('a',?)", (json.dumps([candidate.model_dump(mode="json")]),))
    db.commit()
    db.close()
    before = path.read_bytes()
    report = saved([str(path), str(path)])
    expected = 1 if journalled else 2
    assert report["unique_saved_candidates"] == expected
    assert report["admitted_service_descriptions_before"] == expected and report["admitted_service_descriptions_after"] == 0
    assert len(report["queries"]) == expected
    assert {group["query"] for group in report["queries"]} == ({candidate.query} if journalled else {candidate.query, "SaaS pricing"})
    assert all(group["counts"]["admitted_after"] == 0 for group in report["queries"])
    assert path.read_bytes() == before


@pytest.mark.parametrize("policy", [3, 4])
def test_product_exclusion_is_proposed_only_for_new_drafts(tmp_path, policy):
    from scripts.ui_test_providers import FixtureModel, FixtureSearch, fixture_fetch
    from shortlist.config import Settings
    from shortlist.relevance import SERVICE_EXCLUSION
    from shortlist.store import Store
    from shortlist.worker import execute_run

    settings = Settings(db_path=tmp_path / "labelled-draft.sqlite3")
    store = Store(settings.db_path)
    identity = store.create_draft("https://seller.example/", "labelled-product-exclusion")
    fence = store.claim(identity)
    checkpoint = store.get_run(identity)["checkpoint"]
    checkpoint["seller_draft_policy"] = policy
    store.checkpoint(identity, fence, "seller", checkpoint, "queued")
    execute_run(store, settings, identity, model=FixtureModel(), search=FixtureSearch(), fetch=fixture_fetch)
    saved_draft = store.get_run(identity)["checkpoint"]
    assert saved_draft.get("draft_exclusions", []) == ([SERVICE_EXCLUSION] if policy == 4 else [])


def test_synthetic_product_exclusion_uses_its_own_saved_passage():
    from scripts.ui_test_providers import SOFTWARE_ONLY, FixtureModel, fixture_fetch
    from shortlist.domain import exclusion_id
    from shortlist.relevance import SERVICE_EXCLUSION

    draft = FixtureModel().seller(None)
    profile = Profile(seller_url="https://seller.example/", offer=draft.offer, target=draft.target,
                      criteria=tuple(draft.criteria), exclusions=(SERVICE_EXCLUSION,))
    source = fixture_fetch("https://example-1.com/", "example-1.com")
    candidate = Candidate(domain="example-1.com", url=source.url, name="Labelled synthetic software",
                          query=profile.target, provider="fixture")
    research = FixtureModel().research(profile, candidate, (source, source))
    finding = research.exclusion_findings[0]
    assert finding.exclusion_id == exclusion_id(0) and finding.status == "cleared"
    assert finding.evidence[0].passage == SOFTWARE_ONLY and SOFTWARE_ONLY in source.text
