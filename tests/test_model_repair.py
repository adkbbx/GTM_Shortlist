"""Labelled provider fixtures prove bounded repairs through the real worker/store."""
import hashlib
import json

import httpx
import pytest

from shortlist.config import Settings
from shortlist.domain import Candidate, Criterion, Profile, Source
from shortlist.providers import ModelOutputError
from shortlist.store import Store
from shortlist.worker import execute_run


@pytest.fixture
def flow(tmp_path):
    settings = Settings(db_path=tmp_path / "repair.sqlite3", gemma_base_url="https://model.example",
                        gemma_model="labelled-fixture")
    profile = Profile(seller_url="https://seller.example", offer="Acquisition research service",
                      target="AI business software", criteria=(Criterion(id="ai", description="AI software"),))
    text = "We supply AI software for business operations."
    source = Source(id="fixture-source", url="https://company.example", company_domain="company.example",
                    title="Labelled fixture", text=text, content_hash=hashlib.sha256(text.encode()).hexdigest())
    candidate = Candidate(domain=source.company_domain, name="Labelled fixture", url=source.url,
                          provider="fixture", query="fixture")
    store = Store(settings.db_path)
    run_id = store.create_run(profile, "repair-fixture")
    fence = store.claim(run_id)
    checkpoint = {"candidates": [candidate.model_dump(mode="json")],
                  "sources": {candidate.domain: [source.model_dump(mode="json")]}}
    store.checkpoint(run_id, fence, "research", checkpoint, "queued")
    good = {"name": "Labelled fixture", "findings": [{"status": "supported", "criterion_id": "ai",
            "evidence": [{"source_id": source.id, "passage": text, "claim": "AI software"}]}]}
    return settings, store, run_id, source, good


def provider(monkeypatch, contents):
    requests = []
    def reply(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": contents[len(requests) - 1]}}]})
    original = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: original(transport=httpx.MockTransport(reply), **kwargs))
    return requests


def test_schema_error_retained_and_repaired_once(flow, monkeypatch):
    settings, store, run_id, source, good = flow
    bad = json.dumps({"name": "Fixture", "findings": [{"status": "unknown", "criterion_id": "ai"}]})
    requests = provider(monkeypatch, [bad, json.dumps(good)])
    execute_run(store, settings, run_id)
    saved = Store(store.path).get_run(run_id)
    assert saved["status"] == "ready"
    assert [a["state"] for a in saved["attempts"]] == ["failed", "succeeded"]
    diagnostic = saved["checkpoint"]["model_outputs"][source.company_domain]
    assert json.loads(diagnostic["content"]) == json.loads(bad)
    assert diagnostic["issues"][0]["type"] == "missing"
    repair_payload = json.loads(requests[1]["messages"][1]["content"])
    assert repair_payload["previous_invalid_output"] == diagnostic
    assert saved["records"][0]["research"]["findings"][0]["status"] == "supported"


def test_second_invalid_output_stops_without_third_dispatch(flow, monkeypatch):
    settings, store, run_id, source, _ = flow
    requests = provider(monkeypatch, ["broken JSON", "[]"])
    execute_run(store, settings, run_id)
    run = store.get_run(run_id)
    assert len(requests) == 2
    assert run["status"] == "partial"
    assert run["records"][0]["research"]["findings"][0]["status"] == "unknown"
    assert "repair_failure" in run["checkpoint"]["model_outputs"][source.company_domain]
    assert "broken JSON" not in run["records"][0]["research"]["unknowns"][0]


def test_repair_uses_shared_cap(flow, monkeypatch):
    settings, store, run_id, source, _ = flow
    fence = store.claim(run_id)
    for i in range(7):
        attempt = store.reserve(run_id, fence, "fixture", "model", f"prior:{i}")
        store.outcome(attempt, "failed")
    checkpoint = store.get_run(run_id)["checkpoint"]
    store.checkpoint(run_id, fence, "research", checkpoint, "queued")
    requests = provider(monkeypatch, ["broken JSON"])
    execute_run(store, settings, run_id)
    run = store.get_run(run_id)
    assert len(requests) == 1
    assert len(run["attempts"]) == 8
    assert run["error"] == "Run model attempt cap reached"
    assert run["checkpoint"]["model_outputs"][source.company_domain]["content"] == "broken JSON"


def test_restart_after_diagnostic_skips_original_dispatch(flow, monkeypatch):
    settings, store, run_id, _source, good = flow
    original_checkpoint = store.checkpoint
    class SimulatedCrash(BaseException):
        pass
    def crash_after_save(*args, **kwargs):
        original_checkpoint(*args, **kwargs)
        if "model_outputs" in args[3] and args[3]["model_outputs"]:
            raise SimulatedCrash()
    monkeypatch.setattr(store, "checkpoint", crash_after_save)
    requests = provider(monkeypatch, ["broken JSON", json.dumps(good)])
    with pytest.raises(SimulatedCrash):
        execute_run(store, settings, run_id)
    with store.connection() as db:
        db.execute("UPDATE runs SET lease_until=0 WHERE id=?", (run_id,))
    execute_run(Store(store.path), settings, run_id)
    run = store.get_run(run_id)
    assert len(requests) == 2
    assert run["status"] == "ready"
    assert len(run["attempts"]) == 2


def test_diagnostics_bounded_and_not_in_exception_message():
    error = ModelOutputError("x" * 40000, [{"type": "fixture"}])
    assert len(error.diagnostic()["content"]) == 32000
    assert "xxxx" not in str(error)


def test_transport_failure_has_no_structured_repair(flow, monkeypatch):
    settings, store, run_id, _, _ = flow
    original = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: original(
        transport=httpx.MockTransport(lambda request: httpx.Response(401, text="private provider payload")), **kwargs))
    execute_run(store, settings, run_id)
    run = store.get_run(run_id)
    assert len(run["attempts"]) == 1
    assert run["status"] == "partial"
    assert "private provider payload" not in json.dumps(run)
    assert not run["checkpoint"]["model_outputs"]
