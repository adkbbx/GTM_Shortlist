import pytest
from fastapi.testclient import TestClient

from shortlist.api import create_app
from shortlist.config import Settings
from shortlist.store import Store
from shortlist.worker import execute_run


@pytest.mark.parametrize("website", ["eygentic.com", "https://eygentic.com", " Eygentic.com ", "eygentic.com:443", "//eygentic.com"])
def test_bare_and_explicit_seller_urls_share_one_canonical_command(tmp_path, website):
    client = TestClient(create_app(Settings(db_path=tmp_path / "website.sqlite3")))
    first = client.post("/api/sellers", json={"seller_url": website, "request_key": "website-input"})
    assert first.status_code == 201
    assert first.json()["seller_url"] == "https://eygentic.com/"
    second = client.post("/api/sellers", json={"seller_url": "https://eygentic.com/", "request_key": "website-input"})
    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]


@pytest.mark.parametrize("website", ["127.0.0.1", "127.1", "localhost", "host.internal", "ftp://example.com", "javascript:alert(1)", "user:password@example.com", "example.com:8080", "<bad company>"])
def test_seller_convenience_preserves_unsafe_url_rejection(tmp_path, website):
    client = TestClient(create_app(Settings(db_path=tmp_path / "website.sqlite3")))
    assert client.post("/api/sellers", json={"seller_url": website, "request_key": "unsafe-input"}).status_code == 422
    assert client.get("/api/runs").json() == []


def test_failed_offer_summary_explains_recovery_in_saved_and_listed_runs(tmp_path):
    import hashlib

    from shortlist.domain import Source
    from shortlist.providers import ModelOutputError
    settings = Settings(db_path=tmp_path / "copy.sqlite3")
    store = Store(settings.db_path)
    identity = store.create_draft("https://seller.example/", "bad-seller-summary")
    text = "Labelled fixture page; no valid model summary."
    source = Source(url="https://seller.example/", company_domain="seller.example", title="Labelled fixture",
                    text=text, content_hash=hashlib.sha256(text.encode()).hexdigest())
    class Model:
        name = "labelled-invalid-draft"
        def seller(self, source):
            raise ModelOutputError("{}", [{"type": "missing", "loc": ["offer"]}])
    execute_run(store, settings, identity, model=Model(), fetch=lambda *args: source)
    before = store.get_run(identity)
    client = TestClient(create_app(settings))
    response = client.get(f"/api/runs/{identity}").json()
    assert response["status"] == "awaiting_confirmation"
    assert "usable offer summary" in response["error"]
    assert "Company search hasn't started" in response["error"]
    assert "Enter what you sell" in response["error"]
    assert "New shortlist" in response["error"]
    assert "product or services page" in response["error"]
    assert "Gemma" not in response["error"]
    assert "validation" not in response["error"]
    assert client.get("/api/runs").json()[0]["error"] == response["error"]
    assert store.get_run(identity) == before  # Presentation changes no source/journal/diagnostic.


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
    assert client.get("/api/health").json() == {"mode": "local", "search_ready": False, "gemma_ready": False, "worker_online": False, "local_search_error": None}
