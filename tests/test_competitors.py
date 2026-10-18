"""Saved real labels plus explicitly synthetic boundary and worker fixtures. No providers."""
import json

import pytest

from scripts.check_competitors import CASES, check, inputs
from shortlist.competitors import PEER_REASON, competitor_issue
from shortlist.config import Settings
from shortlist.domain import Evidence, Observed, Research
from shortlist.fetch import FetchError
from shortlist.providers import validate_extraction
from shortlist.store import Store
from shortlist.verification import company_need_evidence, reader_need
from shortlist.worker import execute_run

CORPUS = json.loads(CASES.read_text(encoding="utf-8"))


def test_labelled_comparison():
    report = check()
    assert report["before"] == {"peers_set_aside": 1, "peers": 3, "buyers_kept": 4, "buyers": 4, "buyers_lost": []}
    assert report["after"] == {"peers_set_aside": 3, "peers": 3, "buyers_kept": 4, "buyers": 4, "buyers_lost": []}
    assert report["need_evidence"] == {"reader_needs_before": 1, "reader_needs_after": 0,
                                       "company_passages": 3, "company_passages_kept": 3}
    assert next(c for c in CORPUS["cases"] if c["domain"] == "mikesonders.com")["provenance"] == "reported_ui"


@pytest.mark.parametrize("case", CORPUS["cases"], ids=lambda c: c["domain"])
def test_category_filter_and_old_policy(case):
    profile, candidate, source = inputs(case)
    assert competitor_issue(profile, candidate.domain, source, policy=4) is None
    assert competitor_issue(profile, candidate.domain, source) == (PEER_REASON if case["label"] == "competitor/peer" else None)


@pytest.mark.parametrize("url,title,text", [
    ("https://channeltivity.com/partners/program", "Partner Management Software", "Partner management software"),
    ("https://channeltivity.com/", "Partner programme", "Partner management software"),
    ("https://elsewhere.example/", "Partner Management Software", "Partner management software"),
    ("https://channeltivity.com/", "Labelled software company", "Software for partner management teams"),
    ("https://channeltivity.com/", "Labelled software company", "We use partner management software"),
    ("https://channeltivity.com/", "Labelled software company", "Your partner management software"),
    ("https://channeltivity.com/", "Labelled software company", "Opening\n" * 12 + "Partner management software"),
    ("https://channeltivity.com/", "Labelled AI software platform", "AI platform for business growth"),
    ("https://channeltivity.com/", "Labelled company", "We do not sell partner management software"),
    ("https://channeltivity.com/", "Labelled company", "Our customers sell partner management software"),
])
def test_other_pages_customers_navigation_and_generic_terms_are_not_offers(url, title, text):
    profile, candidate, source = inputs(next(c for c in CORPUS["cases"] if c["domain"] == "channeltivity.com"))
    source = source.model_copy(update={"url": url, "title": title, "text": text})
    assert competitor_issue(profile, candidate.domain, source) is None


class FixtureModel:
    name = "labelled_fixture"

    def __init__(self):
        self.domains = []

    def research(self, profile, candidate, sources):
        self.domains.append(candidate.domain)
        return validate_extraction({"name": candidate.name, "findings": []}, profile, candidate.domain, sources)


@pytest.mark.parametrize("policy", [4, 5])
@pytest.mark.parametrize("selection", [None, 3])
@pytest.mark.parametrize("saved", [False, True])
def test_worker_skips_peer_before_model_and_followups_but_keeps_buyers(tmp_path, policy, selection, saved):
    cases = [c for c in CORPUS["cases"] if c["seller"]["domain"] == "unifyr.com"]
    rows = [inputs(c) for c in cases]
    profile = rows[0][0]
    store = Store(tmp_path / "labelled.sqlite3")
    run_id = store.create_run(profile, "labelled-peer-worker")
    fence = store.claim(run_id)
    sources = {c.domain: s for _, c, s in rows}
    checkpoint = {"discovery_policy": policy, "company_limit": 6, "selection_policy": selection,
                  "candidates": [c.model_dump(mode="json") for _, c, _ in rows]}
    if saved:
        checkpoint["sources"] = {d: [s.model_dump(mode="json")] for d, s in sources.items()}
    store.checkpoint(run_id, fence, "research", checkpoint, "queued")
    fetched = []
    def fetch(url, expected_domain=None):
        fetched.append(expected_domain)
        return sources[expected_domain]
    model = FixtureModel()
    execute_run(store, Settings(db_path=store.path), run_id, model=model, fetch=fetch)
    run = store.get_run(run_id)
    peers = {"channeltivity.com", "channelinstitute.com"}
    assert set(model.domains) == set(sources) - (peers if policy == 5 else set())
    if policy == 5:
        assert {d: f["reason"] for d, f in run["checkpoint"]["candidate_failures"].items()} == dict.fromkeys(peers, PEER_REASON)
        assert all(e["detail"] == PEER_REASON for e in run["events"] if e["label"].startswith("Set aside company:"))
    assert not saved or not fetched
    assert not any(a["kind"] == "search" for a in run["attempts"])
    assert {r["research"]["domain"] for r in run["records"]} == set(model.domains)


@pytest.mark.parametrize("policy", [4, 5])
@pytest.mark.parametrize("stage", ["discovery", "research"])
def test_saved_market_domains_alone_never_set_a_company_aside(tmp_path, policy, stage):
    # The saved competitor search for Unifyr returned unrelated domains (paloaltonetworks.com, iqvia.com, a county site),
    # so the worker never passes them: a buyer found by both searches must still be researched.
    profile, candidate, _ = inputs(next(c for c in CORPUS["cases"] if c["domain"] == "channeltivity.com"))
    candidate = candidate.model_copy(update={"name": "Labelled plain company name", "excerpt": ""})
    assert competitor_issue(profile, candidate.domain, policy=policy) is None
    if policy == 4:
        return
    store = Store(tmp_path / "labelled-market.sqlite3")
    run_id = store.create_run(profile, "labelled-market")
    fence = store.claim(run_id)
    store.checkpoint(run_id, fence, stage, {"discovery_policy": policy, "use_saved_discovery": True,
        ("discovered" if stage == "discovery" else "candidates"): [candidate.model_dump(mode="json")], "market": {"competitors": [{"domain": candidate.domain}]}}, "queued")
    def fetch(url, expected_domain=None):
        raise FetchError("Labelled fixture: page unavailable")
    execute_run(store, Settings(db_path=store.path), run_id, model=FixtureModel(), fetch=fetch)
    failure = store.get_run(run_id)["checkpoint"].get("candidate_failures", {}).get(candidate.domain, {})
    assert failure.get("reason") != PEER_REASON


@pytest.mark.parametrize("passage,blocked", [
    ("You're building a network and need structured onboarding.", True),
    ("You are building a network and need structured onboarding.", True),
    ("Your team needs structured training.", True),
    ("You need structured onboarding.", True),
    ("Help your team hit the ground running with e-learning programs and ongoing training.", False),
    ("We need structured onboarding for our own partner network.", False),
    ("Our partners receive training and tools.", False),
    ("We provide the tools you need to train your partners.", False),
])
def test_narrow_reader_need_rule(passage, blocked):
    assert reader_need(passage) is blocked


@pytest.mark.parametrize("case", CORPUS["need_cases"], ids=lambda c: c["domain"])
def test_saved_need_passages_are_gated_only_under_policy_five(case):
    profile, candidate, source = inputs(next(c for c in CORPUS["cases"] if c["domain"] == case["domain"]))
    finding = Observed(criterion_id="need", status="supported", evidence=(Evidence(
        source_id=source.id, passage=case["passage"], claim="Labelled proposed need"),))
    record = Research(domain=candidate.domain, name=candidate.name, profile_id=profile.id, findings=(finding,),
                      sources=(source,), qualification="fits", status="complete")
    assert company_need_evidence(profile, record, policy=4) is record
    result = company_need_evidence(profile, record)
    blocked = case["label"] == "reader_need"
    assert result.findings[0].status == ("unknown" if blocked else "supported")
    assert result.qualification == ("needs_verification" if blocked else "fits")
    if blocked:
        own = finding.evidence[0].model_copy(update={"passage": "We need structured onboarding for our own partners."})
        mixed = record.model_copy(update={"findings": (finding.model_copy(update={"evidence": (*finding.evidence, own)}),)})
        assert company_need_evidence(profile, mixed).findings[0].evidence == (own,)


def test_new_drafts_confirm_with_policy_five(tmp_path):
    from shortlist.providers import SellerDraft
    profile, _, _ = inputs(CORPUS["cases"][0])
    store = Store(tmp_path / "labelled-confirm.sqlite3")
    run_id = store.create_draft(profile.seller_url, "labelled-confirm")
    fence = store.claim(run_id)
    checkpoint = store.get_run(run_id)["checkpoint"]
    checkpoint["draft"] = SellerDraft(offer=profile.offer, target=profile.target, criteria=list(profile.criteria), unknowns=[]).model_dump(mode="json")
    store.checkpoint(run_id, fence, "confirmation", checkpoint, "awaiting_confirmation")
    store.confirm_draft(run_id, profile)
    assert store.get_run(run_id)["checkpoint"]["discovery_policy"] == 5
