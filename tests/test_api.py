from fastapi.testclient import TestClient

from shortlist.api import create_app
from shortlist.config import Settings
from shortlist.store import Store
from shortlist.worker import execute_run


def test_guided_manual_confirmation_and_idempotency(tmp_path):
    settings = Settings(db_path=tmp_path / "api.sqlite3")
    client = TestClient(create_app(settings))
    response = client.post("/api/sellers", json={"seller_url": "https://eygentic.com", "request_key": "test-request"})
    assert response.status_code == 201
    run_id = response.json()["id"]
    def unavailable(*args, **kwargs):
        from shortlist.fetch import FetchError
        raise FetchError("Website unavailable")
    store = Store(settings.db_path)
    execute_run(store, settings, run_id, fetch=unavailable)
    draft = client.get(f"/api/runs/{run_id}").json()
    assert draft["status"] == "awaiting_confirmation"
    assert "manually" in draft["error"]
    assert draft["profile"] is None
    body = {"offer": "Customer acquisition experiments", "target": "Private AI software startups",
            "criteria": [{"id": "ai", "description": "AI software", "required": True}], "exclusions": []}
    response = client.post(f"/api/runs/{run_id}/confirm", json=body)
    assert response.status_code == 200
    profile_id = response.json()["profile"]["id"]
    assert client.post(f"/api/runs/{run_id}/confirm", json=body).json()["profile"]["id"] == profile_id
    assert client.post(f"/api/runs/{run_id}/confirm", json={**body, "target": "different target"}).status_code == 409
    assert client.get(f"/api/runs/{run_id}/export?format=json").status_code == 200


def test_api_host_origin_and_input_rejections(tmp_path):
    client = TestClient(create_app(Settings(db_path=tmp_path / "api.sqlite3")))
    assert client.get("/api/health", headers={"Host": "attacker.example"}).status_code == 400
    assert client.post("/api/sellers", headers={"Origin": "https://attacker.example"}, json={
        "seller_url": "https://example.com", "request_key": "valid-key"}).status_code == 403
    assert client.post("/api/sellers", json={"seller_url": "https://127.1", "request_key": "valid-key"}).status_code == 422
    assert client.get("/api/runs/missing").status_code == 404
    assert client.get("/api/health").json() == {"mode": "local", "search_ready": False, "gemma_ready": False}
