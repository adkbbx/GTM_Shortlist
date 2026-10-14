import hashlib
import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from shortlist.api import create_app
from shortlist.config import Settings
from shortlist.domain import (
    Criterion,
    Evidence,
    ExclusionObserved,
    ExclusionUnknown,
    Observed,
    Profile,
    Research,
    Review,
    Source,
    qualify,
)
from shortlist.export import export_run
from shortlist.providers import ProviderError, validate_extraction
from shortlist.store import Store


@pytest.fixture
def setup():
    profile = Profile(seller_url="https://seller.example", offer="Acquisition research service",
                      target="AI software businesses", criteria=(Criterion(id="ai", description="AI software"),),
                      exclusions=("Publicly listed companies", "Companies headquartered in Canada"))
    text = "Labelled fixture: We offer AI software. Example is a publicly listed business headquartered in Canada."
    source = Source(id="fixture-source", url="https://company.example", title="Labelled fixture",
                    company_domain="company.example", text=text, content_hash=hashlib.sha256(text.encode()).hexdigest())
    evidence = Evidence(source_id=source.id, passage=source.text, claim="Labelled source assessment")
    finding = Observed(status="supported", criterion_id="ai", evidence=(evidence,))
    return profile, source, evidence, finding


def test_any_matched_exclusion_overrides_fit_and_other_unknowns(setup):
    profile, _, evidence, finding = setup
    checks = (ExclusionObserved(status="matched", exclusion_id="exclude-1", evidence=(evidence,)),)
    assert qualify(profile, (finding,), checks) == "does_not_fit"


def test_missing_or_unknown_exclusion_never_becomes_fit(setup):
    profile, _, evidence, finding = setup
    cleared = ExclusionObserved(status="cleared", exclusion_id="exclude-1", evidence=(evidence,))
    assert qualify(profile, (finding,), (cleared,)) == "needs_verification"
    assert qualify(profile, (finding,), (cleared, ExclusionUnknown(exclusion_id="exclude-2", reason="No evidence"))) == "needs_verification"


def test_all_exclusions_need_evidence_to_be_cleared(setup):
    profile, _, evidence, finding = setup
    checks = tuple(ExclusionObserved(status="cleared", exclusion_id=f"exclude-{i}", evidence=(evidence,)) for i in (1, 2))
    assert qualify(profile, (finding,), checks) == "fits"
    with pytest.raises(ValidationError):
        ExclusionObserved(status="cleared", exclusion_id="exclude-1", evidence=())


@pytest.mark.parametrize("problem", ("fabricated", "wrong_source", "wrong_company"))
def test_bad_exclusion_citations_become_unknown(setup, problem):
    profile, source, evidence, finding = setup
    raw_evidence = evidence.model_dump(mode="json")
    if problem == "fabricated":
        raw_evidence["passage"] = "This fabricated passage never appeared in the source."
    if problem == "wrong_source":
        raw_evidence["source_id"] = "another-company-source"
    if problem == "wrong_company":
        source = source.model_copy(update={"company_domain": "other.example"})
    record = validate_extraction({"name": "Labelled fixture", "findings": [finding.model_dump(mode="json")],
                                 "exclusion_findings": [{"status": "matched", "exclusion_id": "exclude-1",
                                                         "evidence": [raw_evidence]}]}, profile, "company.example", (source,))
    assert all(f.status == "unknown" for f in record.exclusion_findings)
    assert record.qualification == "needs_verification"
    assert record.status == "partial"


@pytest.mark.parametrize("ids", (("unknown-id",), ("exclude-1", "exclude-1")))
def test_invalid_or_duplicate_exclusion_identity_rejected(setup, ids):
    profile, source, _, _ = setup
    raw = {"name": "Labelled fixture", "findings": [], "exclusion_findings": [
        {"status": "unknown", "exclusion_id": key, "reason": "No source evidence"} for key in ids]}
    with pytest.raises(ProviderError, match="exclusion IDs"):
        validate_extraction(raw, profile, "company.example", (source,))


def test_matched_exclusion_passage_persists_in_both_exports(setup, tmp_path):
    profile, source, evidence, finding = setup
    raw = {"name": "Labelled fixture", "findings": [finding.model_dump(mode="json")], "exclusion_findings": [
        {"status": "matched", "exclusion_id": "exclude-1", "evidence": [evidence.model_dump(mode="json")]}]}
    record = validate_extraction(raw, profile, "company.example", (source,))
    store = Store(tmp_path / "exclude.sqlite3")
    run_id = store.create_run(profile, "exclusion-export")
    store.save_record(run_id, store.claim(run_id), record)
    reopened = Store(store.path).get_run(run_id)
    assert reopened["records"][0]["research"]["qualification"] == "does_not_fit"
    exported = json.loads(export_run(reopened, "json"))
    assert exported["records"][0]["research"]["exclusion_findings"][0]["evidence"][0]["passage"] == source.text
    csv = export_run(reopened, "csv")
    assert "What needs checking" in csv and "Does not meet criteria" in csv
    assert profile.exclusions[0] in csv


def test_old_record_gets_unknown_exclusion_without_rewriting_snapshot_or_review(setup, tmp_path):
    profile, source, _, finding = setup
    record = Research(domain="company.example", name="Labelled old fixture", profile_id=profile.id,
                      findings=(finding,), sources=(source,), qualification="fits", status="complete")
    store = Store(tmp_path / "legacy.sqlite3")
    run_id = store.create_run(profile, "legacy-exclusions")
    store.save_record(run_id, store.claim(run_id), record)
    old = record.model_dump(mode="json", exclude={"exclusion_findings"})
    with store.connection() as db:
        db.execute("UPDATE records SET research=? WHERE id=?", (json.dumps(old), record.id))
    store.review(run_id, record.id, Review(decision="accepted", reason="Prior human review"))
    result = Store(store.path).get_run(run_id)["records"][0]
    assert result["research"]["qualification"] == "needs_verification"
    assert result["research"]["status"] == "partial"
    assert len(result["research"]["exclusion_findings"]) == 2
    assert result["review"]["decision"] == "accepted"
    assert result["research"]["sources"][0] == source.model_dump(mode="json")
    with store.connection() as db:
        assert json.loads(db.execute("SELECT research FROM records WHERE id=?", (record.id,)).fetchone()[0]) == old


@pytest.mark.parametrize("exclusions", (["aa"], ["X" * 501], ["same", " Same "], [f"condition-{i}" for i in range(13)]))
def test_invalid_exclusions_rejected_at_api_boundary(setup, tmp_path, exclusions):
    profile, _, _, _ = setup
    client = TestClient(create_app(Settings(db_path=tmp_path / "api.sqlite3")))
    payload = profile.model_dump(mode="json", exclude={"id", "seller_url", "confirmed_at"})
    response = client.post("/api/runs/missing/confirm", json={**payload, "exclusions": exclusions})
    assert response.status_code == 422
