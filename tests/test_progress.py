import time

import pytest
from fastapi.testclient import TestClient

from shortlist.api import create_app
from shortlist.config import Settings
from shortlist.fetch import FetchError
from shortlist.progress import ProgressUpdate
from shortlist.store import Conflict, Store
from shortlist.worker import execute_run


def test_failed_fetch_records_actual_step_and_confirmation_in_api(tmp_path):
    settings = Settings(db_path=tmp_path / "progress.sqlite3")
    store = Store(settings.db_path)
    run_id = store.create_draft("https://company.example/", "progress-test")

    def fetch(*args, **kwargs):
        raise FetchError("Labelled website failure")

    execute_run(store, settings, run_id, fetch=fetch)
    client = TestClient(create_app(settings))
    run = client.get(f"/api/runs/{run_id}").json()
    assert run["status"] == "awaiting_confirmation"
    events = run["progress"]["events"]
    page = [e for e in events if e["label"] == "Reading your company website"]
    assert [e["state"] for e in page] == ["started", "failed"]
    assert page[-1]["detail"] == "Labelled website failure"
    assert events[-1]["state"] == "waiting"
    assert events[-1]["phase"] == "confirmation"
    assert run["progress"]["sources"] == 0
    assert not run["progress"]["worker_online"]
    assert [e["id"] for e in events] == sorted(e["id"] for e in events)
    assert client.get(f"/api/runs/{run_id}").json()["progress"]["events"] == events


def test_stale_worker_and_replaced_worker_event_are_not_reported_active(tmp_path):
    store = Store(tmp_path / "worker.sqlite3")
    assert not store.worker_online()
    store.worker_heartbeat("labelled-worker")
    assert store.worker_online()
    with store.connection() as db:
        db.execute("UPDATE worker_heartbeats SET expires_at=?", (time.time() - 1,))
    assert not store.worker_online()
    store.worker_heartbeat("labelled-worker")
    store.remove_worker("labelled-worker")
    assert not store.worker_online()
    run_id = store.create_draft("https://company.example/", "fenced-progress")
    fence = store.claim(run_id)
    with store.connection() as db:
        db.execute("UPDATE runs SET lease_until=0 WHERE id=?", (run_id,))
    replacement = store.claim(run_id)
    with pytest.raises(Conflict):
        store.event(run_id, fence, ProgressUpdate(phase="seller", label="Old worker started", state="started"))
    store.event(run_id, replacement, ProgressUpdate(phase="seller", label="New worker started", state="started"))
    assert len(store.get_run(run_id)["events"]) == 1


def test_event_history_is_bounded_without_deleting_saved_observations(tmp_path):
    store = Store(tmp_path / "bounded.sqlite3")
    run_id = store.create_draft("https://company.example/", "bounded-progress")
    fence = store.claim(run_id)
    for index in range(105):
        store.event(run_id, fence, ProgressUpdate(phase="seller", label=f"Labelled saved checkpoint {index}", state="succeeded"))
    events = store.get_run(run_id)["events"]
    assert len(events) == 100
    assert events[0]["label"].endswith("5")
    assert events[-1]["label"].endswith("104")
    with store.connection() as db:
        assert db.execute("SELECT count(*) FROM run_events").fetchone()[0] == 105
