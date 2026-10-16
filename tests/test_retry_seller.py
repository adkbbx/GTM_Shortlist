"""Only a never-dispatched seller setup can recover once under the same run ID."""

import pytest
from fastapi.testclient import TestClient

from shortlist.api import create_app
from shortlist.config import Settings
from shortlist.store import Conflict, Store, seller_retry_available


def failed_setup(store, *, attempt_state=None):
    identity = store.create_draft("https://seller.example/", "labelled-unstarted-seller")
    fence = store.claim(identity)
    checkpoint = store.get_run(identity)["checkpoint"]
    if attempt_state:
        store.reserve(identity, fence, "labelled", "model", "seller:model")
        with store.connection() as db:
            db.execute("UPDATE attempts SET state=? WHERE run_id=?", (attempt_state, identity))
    store.checkpoint(identity, fence, "seller", checkpoint, "partial", "Labelled setup failure")
    return identity, fence, checkpoint


def test_retry_api_is_once_only_and_fences_old_worker_without_new_attempts(tmp_path):
    settings = Settings(db_path=tmp_path / "retry.sqlite3")
    store = Store(settings.db_path)
    identity, fence, checkpoint = failed_setup(store)
    client = TestClient(create_app(settings))
    path = f"/api/runs/{identity}"
    assert client.get(path).json()["can_retry_seller"] is True
    assert client.post(path + "/retry-seller", json={"confirmation": "wrong"}).status_code == 422
    command = {"confirmation": "retry_unstarted_seller"}
    first = client.post(path + "/retry-seller", json=command)
    assert first.status_code == 200
    assert first.json()["id"] == identity
    assert first.json()["status"] == "queued"
    assert first.json()["can_retry_seller"] is False
    saved = store.get_run(identity)
    assert saved["attempts"] == []
    assert saved["checkpoint"] == {**checkpoint, "seller_retry_requested": True}
    assert client.post(path + "/retry-seller", json=command).json() == first.json()
    assert store.get_run(identity) == saved
    with pytest.raises(Conflict):
        store.checkpoint(identity, fence, "seller", checkpoint)
    # A delayed duplicate cannot restart a stopped run or clear its stop marker.
    store.stop_run(identity)
    stopped = store.get_run(identity)
    store.retry_seller(identity)
    assert store.get_run(identity) == stopped


@pytest.mark.parametrize("attempt_state", ["failed", "outcome_unknown", "succeeded"])
def test_any_prior_provider_dispatch_disables_recovery(tmp_path, attempt_state):
    store = Store(tmp_path / "used.sqlite3")
    identity, _, _ = failed_setup(store, attempt_state=attempt_state)
    saved = store.get_run(identity)
    assert seller_retry_available(saved) is False
    with pytest.raises(Conflict, match="before any provider request"):
        store.retry_seller(identity)
    assert store.get_run(identity) == saved


def test_completed_draft_or_stopped_run_is_not_requeued(tmp_path):
    store = Store(tmp_path / "finished.sqlite3")
    identity, _, checkpoint = failed_setup(store)
    with store.connection() as db:
        db.execute("UPDATE runs SET status='queued' WHERE id=?", (identity,))
    store.stop_run(identity)
    assert seller_retry_available(store.get_run(identity)) is False
    with pytest.raises(Conflict):
        store.retry_seller(identity)
    with pytest.raises(KeyError):
        store.retry_seller("missing-run")
    assert store.get_run(identity)["checkpoint"]["seller_url"] == checkpoint["seller_url"]
