import pytest
from fastapi.testclient import TestClient

from shortlist.api import create_app
from shortlist.config import Settings
from shortlist.domain import Criterion, Profile
from shortlist.store import Conflict, Store


def test_reusing_confirmed_offer_preserves_exclusions_and_requires_new_confirmation(tmp_path):
    store = Store(tmp_path / "reuse.sqlite3")
    profile = Profile(seller_url="https://seller.example/", offer="Confirmed research service",
                      target="AI software companies", criteria=(Criterion(id="ai", description="Offers AI software"),),
                      exclusions=("Publicly listed companies",))
    original = store.create_run(profile, "original-profile")
    with pytest.raises(Conflict):
        store.reuse_draft(original, "too-early")
    store.checkpoint(original, store.claim(original), "complete", {}, "partial")
    client = TestClient(create_app(Settings(db_path=store.path)))
    response = client.post(f"/api/runs/{original}/reuse", json={"request_key": "reuse-once"})
    assert response.status_code == 201
    draft = response.json()
    identity = draft["id"]
    assert identity != original
    assert draft["profile"] is None
    assert draft["status"] == "awaiting_confirmation"
    assert draft["reused_offer"] is True
    assert draft["draft_exclusions"] == list(profile.exclusions)
    assert draft["draft"]["offer"] == profile.offer
    assert draft["attempts"] == []
    assert store.pending_runs() == []
    assert client.post(f"/api/runs/{original}/reuse", json={"request_key": "reuse-once"}).json()["id"] == identity
    confirmed = client.post(f"/api/runs/{identity}/confirm", json={
        "offer": profile.offer, "target": "Edited new target", "criteria": [item.model_dump() for item in profile.criteria],
        "exclusions": list(profile.exclusions), "company_limit": 1,
    })
    assert confirmed.status_code == 200
    assert confirmed.json()["profile"]["target"] == "Edited new target"
    assert confirmed.json()["profile"]["id"] != profile.id
    assert store.get_run(original)["profile"]["id"] == profile.id
    assert store.get_run(original)["profile"]["target"] == profile.target
    store.checkpoint(identity, store.claim(identity), "complete", {}, "ready")
    store.delete_run(identity)
    assert client.post(f"/api/runs/{original}/reuse", json={"request_key": "reuse-once"}).status_code == 409
    store.delete_run(original)
    assert client.post(f"/api/runs/{original}/reuse", json={"request_key": "deleted-source"}).status_code == 404
