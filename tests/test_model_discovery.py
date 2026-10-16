import httpx
import pytest
from fastapi.testclient import TestClient

from scripts.landing_demo_preview import create_preview_app
from shortlist.api import create_app
from shortlist.config import Settings
from shortlist.local_credentials import LocalModelConnection, LocalModelCredentials
from shortlist.model_setup import ModelSetupError, available_models


def transport(monkeypatch, handler):
    original = httpx.Client
    monkeypatch.setattr("shortlist.model_setup.httpx.Client", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))


def test_model_listing_only_gets_metadata_and_filters_untrusted_ids(tmp_path, monkeypatch):
    requests = []
    key = "labelled-private-token"
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"data": [{"id": "other-model"}, {"id": "fixture/gemma"},
            {"id": "fixture/gemma"}, {"id": "<script>"}, {"id": key}, {"id": "x" * 201}, {"id": 4}]})
    transport(monkeypatch, handler)
    result = available_models(LocalModelConnection(base_url="http://localhost:1234/v1", key=key))
    assert result.models == ["fixture/gemma", "other-model"]
    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert str(requests[0].url) == "http://localhost:1234/v1/models"
    assert requests[0].headers["Authorization"] == "Bearer " + key
    assert key not in result.model_dump_json()


@pytest.mark.parametrize("response", [
    httpx.Response(401, text="labelled-private-token"),
    httpx.Response(302, headers={"Location": "https://other.example/steal-key"}),
    httpx.Response(200, text="not JSON labelled-private-token"),
    httpx.Response(200, json={"wrong": []}),
    httpx.Response(200, content=b" " * (4 * 1024 * 1024 + 1)),
])
def test_bad_catalogs_and_redirects_fail_without_echo_or_retry(response, monkeypatch):
    requests = []
    def handler(request):
        requests.append(request)
        return response
    transport(monkeypatch, handler)
    with pytest.raises(ModelSetupError) as error:
        available_models(LocalModelConnection(base_url="https://models.example/v1", key="labelled-private-token"))
    assert "labelled-private-token" not in str(error.value)
    assert len(requests) == 1


def test_discovery_boundary_does_not_save_credentials_start_jobs_or_probe_on_rejection(tmp_path, monkeypatch):
    settings = Settings(db_path=tmp_path / "discovery.sqlite3")
    client = TestClient(create_app(settings), base_url="http://127.0.0.1:8014")
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"data": [{"id": "labelled-gemma"}]})
    transport(monkeypatch, handler)
    route = "/api/local/model/models"
    command = {"base_url": "http://localhost:1234/v1", "key": "labelled-private-token"}
    headers = {"Origin": "http://127.0.0.1:8014"}
    response = client.post(route, headers=headers, json=command)
    assert response.status_code == 200
    assert response.json() == {"models": ["labelled-gemma"]}
    assert not LocalModelCredentials(settings.db_path).path.exists()
    assert client.get("/api/runs").json() == []
    assert client.get("/api/health").json()["gemma_ready"] is False
    for response, status in (
        (client.post(route, json=command), 403),
        (client.post(route, headers={"Origin": "https://attacker.example"}, json=command), 403),
        (client.post(route, headers=headers, json={**command, "base_url": "https://user:secret@model.example/v1"}), 422),
        (client.post(route, headers=headers, json={**command, "base_url": "http://remote.example/v1"}), 422),
        (client.post(route, headers=headers, json={**command, "key": "x" * 3000}), 413),
    ):
        assert response.status_code == status
        assert command["key"] not in response.text
    assert len(requests) == 1
    preview = TestClient(create_preview_app(tmp_path / "preview.sqlite3"))
    assert preview.post(route, json=command).status_code == 409
    hosted = settings.model_copy(update={"mode": "hosted", "app_url": "https://app.example"})
    assert TestClient(create_app(hosted), base_url="https://app.example").post(route, json=command).status_code == 404
    assert len(requests) == 1
