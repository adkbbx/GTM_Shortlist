"""Shortlist order follows evidence: in the saved Private AI B2B SaaS runs, Prismatic (three of four required checks
supported) was listed after companies with none, because every record shared the same Needs-verification label."""
import csv
import hashlib
import io
import json

from fastapi.testclient import TestClient

from shortlist.api import create_app
from shortlist.config import Settings
from shortlist.domain import Criterion, Profile, Source
from shortlist.export import export_run
from shortlist.providers import validate_extraction
from shortlist.ranking import by_evidence
from shortlist.store import Store

CRITERIA = (Criterion(id="ai", description="Offers software with artificial intelligence as a core capability"),
            Criterion(id="b2b", description="Sells software to businesses"),
            Criterion(id="saas", description="Offers software as a subscription or hosted service"),
            Criterion(id="private", description="Privately held startup, with explicit current evidence of ownership"),
            Criterion(id="team", description="Lists a customer success team", required=False))
TEXT = "Labelled fixture page. We sell AI software to businesses as a hosted subscription. Our customer success team helps."
PASSAGES = {"ai": "We sell AI software to businesses as a hosted subscription.", "b2b": "We sell AI software to businesses as a hosted subscription.",
            "saas": "We sell AI software to businesses as a hosted subscription.", "team": "Our customer success team helps."}


def record(profile, domain, supported, contradicted=()):
    source = Source(url=f"https://{domain}/", company_domain=domain, title="Labelled fixture", text=TEXT,
                    content_hash=hashlib.sha256(TEXT.encode()).hexdigest())
    findings = []
    for criterion in profile.criteria:
        if criterion.id in supported or criterion.id in contradicted:
            findings.append({"criterion_id": criterion.id, "status": "contradicted" if criterion.id in contradicted else "supported",
                             "evidence": [{"source_id": source.id, "passage": PASSAGES.get(criterion.id, PASSAGES["ai"]), "claim": "Labelled claim"}]})
        else:
            findings.append({"criterion_id": criterion.id, "status": "unknown", "reason": "Labelled: not stated on the saved page"})
    return validate_extraction({"name": domain, "findings": findings}, profile, domain, (source,))


def test_more_supported_required_checks_come_first_within_each_assessment():
    profile = Profile(seller_url="https://seller.example/", offer="Customer acquisition research", target="Private AI B2B SaaS startups",
                      criteria=CRITERIA)
    researched = [record(profile, "none.example", ()), record(profile, "three.example", ("ai", "b2b", "saas")),
                  record(profile, "mismatch.example", ("ai", "b2b"), contradicted=("saas",)),
                  record(profile, "fits.example", ("ai", "b2b", "saas", "private")), record(profile, "two.example", ("ai", "b2b", "team")),
                  record(profile, "also-none.example", ())]
    assert [r.qualification for r in researched] == ["needs_verification", "needs_verification", "does_not_fit", "fits",
                                                      "needs_verification", "needs_verification"]
    ordered = by_evidence(profile.model_dump(mode="json"), [{"research": r.model_dump(mode="json")} for r in researched])
    assert [item["research"]["domain"] for item in ordered] == [
        "fits.example", "three.example", "two.example", "none.example", "also-none.example", "mismatch.example"]


def test_api_and_every_export_list_companies_by_evidence(tmp_path):
    settings = Settings(db_path=tmp_path / "ranking.sqlite3")
    store = Store(settings.db_path)
    profile = Profile(seller_url="https://seller.example/", offer="Customer acquisition research", target="Private AI B2B SaaS startups",
                      criteria=CRITERIA)
    run_id = store.create_run(profile, "ranking-order")
    fence = store.claim(run_id)
    saved_profile = Profile.model_validate(store.get_run(run_id)["profile"])
    for researched in (record(saved_profile, "none.example", ()), record(saved_profile, "three.example", ("ai", "b2b", "saas"))):
        store.save_record(run_id, fence, researched)
    store.checkpoint(run_id, fence, "review", {}, "partial")
    view = TestClient(create_app(settings)).get(f"/api/runs/{run_id}").json()
    assert [r["research"]["domain"] for r in view["records"]] == ["three.example", "none.example"]
    run = store.get_run(run_id)
    assert [r["research"]["domain"] for r in json.loads(export_run(run, "json"))["records"]] == ["three.example", "none.example"]
    rows = list(csv.reader(io.StringIO(export_run(run, "csv").lstrip("﻿"))))
    assert [row[1] for row in rows[1:]] == ["https://three.example", "https://none.example"]
