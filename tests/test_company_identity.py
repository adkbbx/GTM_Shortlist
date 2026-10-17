"""Recorded Clay failure shapes and labelled offline company admission checks."""
import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from shortlist.api import create_app
from shortlist.config import Settings
from shortlist.domain import Candidate, CompanyIdentity, Criterion, Profile, Source
from shortlist.export import export_run
from shortlist.market import Campaign, CampaignPlan, competitor_query, market_candidates, read_campaign_plan
from shortlist.providers import Gemma, validate_extraction
from shortlist.relevance import CompanyPageError, primary_source_issue, record_issue
from shortlist.store import Conflict, Store
from shortlist.verification import Judgment, Verification, apply_verification


def page(url, title, text):
    from shortlist.fetch import domain_of
    return Source(url=url, company_domain=domain_of(url), title=title, text=text,
                  content_hash=hashlib.sha256(text.encode()).hexdigest())


def profile():
    return Profile(seller_url="https://seller.example/", offer="GTM data enrichment and revenue automation",
                   target="B2B software companies with sales teams",
                   criteria=(Criterion(id="sales", description="Has a sales team serving business customers"),))


@pytest.mark.parametrize("url,title,text", [
    ("https://www.builtinla.com/job/revenue-operations-lead-go-market-gtm/7371274", "Revenue Operations Lead", "GrayMatter Robotics is hiring."),
    ("https://startupik.com/defaultcom-the-gtm-platform-for-revenue-teams/", "Default.com: The GTM Platform", "Default.com provides GTM software. Startupik publishes articles."),
    ("https://hirevector.liveblog365.com/cgi-sys/suspendedpage.cgi", "Account Suspended", "This account has been suspended."),
    ("https://unknown.example/", "Account Suspended", "This account has been suspended."),
    ("https://unknown.example/", "Website", "Account Suspended. Contact your hosting provider."),
    ("https://jobs.obvious.com/", "Jobs", "Job openings"),
])
def test_bad_pages_cannot_be_delivered_or_charged(tmp_path, url, title, text):
    source = page(url, title, text)
    assert primary_source_issue(source, strict=True)
    store = Store(tmp_path / "fixture.sqlite3")
    run_id = store.create_run(profile(), "bad-company-page")
    fence = store.claim(run_id)
    record = validate_extraction({"name": "Default.com", "findings": []}, profile(), source.company_domain, (source,))
    before = store.get_run(run_id)
    with pytest.raises(Conflict, match="Company record withheld"):
        store.save_record(run_id, fence, record)
    assert store.get_run(run_id) == before


@pytest.mark.parametrize("compact", [False, True])
@pytest.mark.parametrize("identity_kind", ["valid", "missing", "other-domain", "invented-passage", "other-name"])
def test_model_identity_requires_grounded_website_owner(monkeypatch, compact, identity_kind):
    source = page("https://acme.example/", "Acme", "Acme provides business software. We sell to business sales teams.")
    identity = {"name": "Acme", "domain": "acme.example", "source_id": source.id,
                "passage": "Acme provides business software."}
    if identity_kind == "other-domain":
        identity["domain"] = "default.com"
    if identity_kind == "invented-passage":
        identity["passage"] = "Acme is the largest company in the world."
    if identity_kind == "other-name":
        identity["name"] = "Default.com"
    calls = []
    model = Gemma(Settings())
    from shortlist.prompting import Runtime
    model._runtime = Runtime(profile="compact" if compact else "full", ollama=False)

    def complete(instruction, payload, schema, **kwargs):
        calls.append(payload)
        assert "company_identity" in schema["required"]
        assert "ALL" in instruction and "confirmed target" in instruction
        return {"name": "Wrong initial search title", "findings": [],
                "company_identity": None if identity_kind == "missing" else identity}

    monkeypatch.setattr(model, "complete", complete)
    candidate = Candidate(domain="acme.example", name="Search title", url=source.url, query="fixture", provider="fixture")
    if identity_kind != "valid":
        with pytest.raises(CompanyPageError):
            model.research(profile(), candidate, (source,), require_identity=True)
    else:
        record = model.research(profile(), candidate, (source,), require_identity=True)
        assert record.name == "Acme" and record.company_identity == CompanyIdentity(**identity)
        assert record.findings[0].status == "unknown"  # Identity does not establish the ICP criterion.
        with pytest.raises(CompanyPageError):
            apply_verification(profile(), record, Verification(judgments=[]))
        audit = Verification(judgments=[Judgment(assessment_id="company:identity", verdict="entailed", reason="Fixture owner proof")])
        assert apply_verification(profile(), record, audit).company_identity == record.company_identity
    assert len(calls) == 1  # No automatic inference repair for failed company admission.


def test_historical_article_is_quarantined_without_rewriting_database(tmp_path):
    settings = Settings(db_path=tmp_path / "historical.sqlite3")
    store = Store(settings.db_path)
    run_id = store.create_run(profile(), "historical-clay")
    source = page("https://startupik.com/defaultcom-the-gtm-platform-for-revenue-teams/", "Default.com", "Default.com provides GTM software.")
    record = validate_extraction({"name": "Default.com", "findings": []}, profile(), "startupik.com", (source,))
    # Reproduce an immutable historical row written before the admission gate.
    with store.connection() as db:
        db.execute("INSERT INTO records(id,run_id,domain,research) VALUES (?,?,?,?)", (record.id, run_id, record.domain, record.model_dump_json()))
    before = store.get_run(run_id)
    client = TestClient(create_app(settings))
    response = client.get(f"/api/runs/{run_id}")
    assert response.status_code == 200, response.text
    view = response.json()
    assert view["records"][0]["source_issue"] and view["progress"]["companies"] == 0
    payload = json.loads(export_run(before, "json"))
    assert payload["records"] == [] and len(payload["withheld_records"]) == 1
    assert "Default.com" not in export_run(before, "csv")
    assert store.get_run(run_id) == before
    assert record_issue(record, strict=True)


def test_market_requires_offer_context_and_distinct_customer_segments():
    offer = "Clay builds revenue systems using GTM data enrichment and sales automation"
    values = [Candidate(domain="acme.example", name="Acme data enrichment and GTM automation", url="https://acme.example/", query="fixture", provider="fixture"),
              Candidate(domain="school.example", name="Learn music with our teachers", url="https://school.example/", query="fixture", provider="fixture"),
              Candidate(domain="startdmv.org", name="GTM data enrichment", url="https://startdmv.org/events/", query="fixture", provider="fixture"),
              Candidate(domain="getonbrd.com", name="GTM data enrichment", url="https://getonbrd.com/jobs/feed", query="fixture", provider="fixture")]
    assert [c.domain for c in market_candidates(values, "https://clay.com/", offer=offer, strict=True)] == ["acme.example"]
    query = competitor_query(offer, "https://clay.com/")
    assert "clay builds" not in query and "enrichment" in query
    base = Campaign(name="Data enrichment", target="B2B software sales teams", rationale="The offer can support sales research workflows.",
                    criteria=(Criterion(id="b2b", description="Sells software to business customers"),))
    plan = read_campaign_plan(CampaignPlan(campaigns=(base, base.model_copy(update={"name": "Outbound automation"}))), distinct_targets=True)
    assert len(plan.campaigns) == 1 and any("Repeated customer" in issue for issue in plan.issues)
    assert read_campaign_plan(plan, distinct_targets=True) == plan


@pytest.mark.parametrize("verified", [True, False])
def test_new_worker_requires_identity_and_journals_rejection_without_delivery(tmp_path, monkeypatch, verified):
    from shortlist.prompting import Runtime
    from shortlist.worker import execute_run
    settings = Settings(db_path=tmp_path / "worker.sqlite3")
    store = Store(settings.db_path)
    target = profile()
    run_id = store.create_run(target, "new-identity-worker")
    fence = store.claim(run_id)
    source = page("https://acme.example/", "Acme", "Acme provides software to businesses.")
    candidate = Candidate(domain="acme.example", name="Acme", url=source.url, query="fixture", provider="fixture")
    checkpoint = store.get_run(run_id)["checkpoint"]
    checkpoint.update(candidates=[candidate.model_dump(mode="json")],
                      sources={candidate.domain: [source.model_dump(mode="json")]})
    store.checkpoint(run_id, fence, "research", checkpoint, "queued")
    model = Gemma(settings)
    model._runtime = Runtime(profile="compact", ollama=False)
    calls = []

    def complete(instruction, payload, schema, **kwargs):
        calls.append(payload)
        if "judgments" in schema["properties"]:
            assert payload["confirmed_target"] == target.target
            return {"judgments": [{"assessment_id": "company:identity", "verdict": "entailed" if verified else "unsupported",
                                    "reason": "Labelled fixture identity judgment"}]}
        return {"name": "Acme", "findings": [], "company_identity": {
            "name": "Acme", "domain": candidate.domain, "source_id": source.id, "passage": source.text}}

    monkeypatch.setattr(model, "complete", complete)
    assert execute_run(store, settings, run_id, model=model)
    saved = store.get_run(run_id)
    assert len(saved["records"]) == int(verified)
    assert len(calls) == 2
    assert len(saved["attempts"]) == 2
    if not verified:
        assert candidate.domain in saved["checkpoint"]["candidate_failures"]
    assert not execute_run(store, settings, run_id, model=model)
    assert len(calls) == 2


def test_identity_rejection_replays_without_second_model_call(tmp_path):
    from shortlist.journal import call_step
    store = Store(tmp_path / "rejected-journal.sqlite3")
    run_id = store.create_run(profile(), "rejected-journal")
    fence = store.claim(run_id)
    calls = []

    def reject():
        calls.append(1)
        raise CompanyPageError("Official owner identity missing")

    for _ in range(2):
        with pytest.raises(CompanyPageError, match="identity missing"):
            call_step(store, run_id, fence, 10, kind="model", provider="fixture", operation="identity",
                      inputs={"fixture": True}, function=reject, decode=lambda value: value)
    assert calls == [1]
    assert len(store.get_run(run_id)["attempts"]) == 1
