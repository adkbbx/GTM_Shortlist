"""Persisted stop boundaries, including a provider returning after lease revocation."""
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from fastapi.testclient import TestClient

from shortlist.api import create_app
from shortlist.config import Settings
from shortlist.domain import Candidate, Criterion, Profile, Review, Source
from shortlist.export import export_run
from shortlist.providers import validate_extraction
from shortlist.store import Conflict, Store
from shortlist.worker import execute_run


def profile_fixture():
    return Profile(seller_url="https://seller.example/", offer="Labelled acquisition research service",
                   target="AI business software", criteria=(Criterion(id="ai", description="AI software"),))


def assert_held_worker_stops(store, settings, run_id):
    candidates = [Candidate(domain=f"held-{index}.example", url=f"https://held-{index}.example/",
                            name=f"Labelled held fixture {index}", query="fixture", provider="fixture") for index in range(3)]
    fence = store.claim(run_id)
    checkpoint = store.get_run(run_id)["checkpoint"]
    checkpoint["candidates"] = [candidate.model_dump(mode="json") for candidate in candidates]
    store.checkpoint(run_id, fence, "research", checkpoint, "queued")
    entered, release = Event(), Event()
    calls = []

    def fetch(url, expected_domain=None):
        calls.append(expected_domain)
        if expected_domain == candidates[1].domain:
            entered.set()
            assert release.wait(15), "Fixture provider was never released"
        text = "Labelled software fixture."
        return Source(url=url, company_domain=expected_domain, title="Fixture", text=text,
                      content_hash=hashlib.sha256(text.encode()).hexdigest())

    class Model:
        name = "labelled-stop-fixture"

        def research(self, profile, candidate, sources):
            return validate_extraction({"name": candidate.name, "findings": []}, profile, candidate.domain, sources)

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(execute_run, store, settings, run_id, model=Model(), fetch=fetch)
        try:
            assert entered.wait(15)
            before = store.get_run(run_id)
            assert len(before["records"]) == 1
            first = before["records"][0]["research"]
            store.review(run_id, first["id"], Review(decision="accepted", reason="Labelled customer review"))
            store.stop_run(run_id)
            stopped = store.get_run(run_id)
            assert stopped["status"] == "partial"
            assert stopped["checkpoint"]["termination"] == "user_stopped"
        finally:
            release.set()
        assert future.result(timeout=15) is True
    after = store.get_run(run_id)
    assert after == stopped  # No outcome/event/checkpoint/record mutation after acknowledgement.
    assert calls == [candidate.domain for candidate in candidates[:2]]
    assert len(after["attempts"]) == 3  # Two fetches and the first company's model request.
    assert after["attempts"][-1]["state"] == "outcome_unknown"
    assert after["records"][0]["review"]["decision"] == "accepted"
    assert execute_run(store, settings, run_id, model=Model(), fetch=fetch) is False
    assert json.loads(export_run(after, "json"))["termination"] == "user_stopped"
    assert "user_stopped" not in export_run(after, "csv")
    assert "Accepted" in export_run(after, "csv")
    return after


def test_real_sqlite_worker_held_across_stop(tmp_path):
    store = Store(tmp_path / "stop.sqlite3")
    run_id = store.create_run(profile_fixture(), "held-stop")
    assert_held_worker_stops(store, Settings(db_path=store.path), run_id)


def test_stop_is_idempotent_and_rejects_stale_worker_or_completed_run(tmp_path):
    store = Store(tmp_path / "stop.sqlite3")
    profile = profile_fixture()
    run_id = store.create_run(profile, "stop")
    fence = store.claim(run_id)
    attempt = store.reserve(run_id, fence, "fixture", "search", "held-search")
    store.stop_run(run_id)
    stopped = store.get_run(run_id)
    Store(store.path).stop_run(run_id)
    assert store.get_run(run_id) == stopped
    assert store.claim(run_id) is None
    assert run_id not in store.pending_runs()
    for mutate in (
        lambda: store.reserve(run_id, fence, "fixture", "search", "later-search"),
        lambda: store.outcome(attempt, "succeeded", run_id=run_id, fence=fence, payload=[]),
        lambda: store.checkpoint(run_id, fence, "review", {}, "ready"),
        lambda: store.save_record(run_id, fence, validate_extraction({"name": "Late fixture", "findings": []}, profile, "late.example", ())),
    ):
        with pytest.raises(Conflict):
            mutate()
    complete = store.create_run(profile, "complete")
    store.checkpoint(complete, store.claim(complete), "review", {}, "ready")
    with pytest.raises(Conflict, match="finished"):
        store.stop_run(complete)
    store.delete_run(run_id)
    with pytest.raises(KeyError):
        store.stop_run(run_id)


def test_stop_api_requires_confirmation_and_preserves_seller_inputs(tmp_path):
    settings = Settings(db_path=tmp_path / "api.sqlite3")
    client = TestClient(create_app(settings))
    run = client.post("/api/sellers", json={"seller_url": "https://seller.example/", "request_key": "stop-api"}).json()
    endpoint = f"/api/runs/{run['id']}/stop"
    for payload in ({}, {"confirmation": "yes"}, {"confirmation": "stop", "extra": True}):
        assert client.post(endpoint, json=payload).status_code == 422
    stopped = client.post(endpoint, json={"confirmation": "stop"})
    assert stopped.status_code == 200
    assert stopped.json()["termination"] == "user_stopped"
    assert stopped.json()["profile"] is None
    assert stopped.json()["seller_url"] == "https://seller.example/"
    assert client.post(endpoint, json={"confirmation": "stop"}).json() == stopped.json()
    assert client.post("/api/runs/missing/stop", json={"confirmation": "stop"}).status_code == 404
