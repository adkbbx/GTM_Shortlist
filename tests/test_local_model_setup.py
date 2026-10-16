import os

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from shortlist.api import create_app
from shortlist.config import Settings
from shortlist.local_credentials import (
    LocalCredentials,
    LocalModelCredentials,
    LocalModelInput,
    apply_local_credentials,
)


def test_model_and_search_persist_independently_and_next_run_reads_replacement(tmp_path):
    settings = Settings(db_path=tmp_path / "model.sqlite3")
    search = LocalCredentials(settings.db_path)
    model = LocalModelCredentials(settings.db_path)
    key = SecretStr("tvly-labelled-search-fixture")
    search.save(key)
    first = LocalModelInput(base_url="http://localhost:8000/v1", model="fixture/gemma", key="labelled-model-secret")
    model.save(first)
    loaded = apply_local_credentials(settings)
    assert loaded.gemma_base_url == first.base_url
    assert loaded.gemma_model == first.model
    assert loaded.gemma_key == first.key
    assert loaded.tavily_key == key
    assert settings.gemma_base_url == ""
    assert model.read() == first
    if os.name == "nt":
        assert b"labelled-model-secret" not in model.path.read_bytes()
    replacement = LocalModelInput(base_url="https://model.example/v1", model="replacement")
    model.save(replacement)
    search.save(SecretStr("tvly-labelled-new-search-fixture"))
    assert model.read() == replacement
    assert apply_local_credentials(settings).gemma_key.get_secret_value() == ""
    assert apply_local_credentials(settings.model_copy(update={"mode": "hosted"})).gemma_base_url == ""


def test_model_api_is_local_bounded_never_echoes_and_makes_no_network_request(tmp_path, monkeypatch):
    import httpx
    settings = Settings(db_path=tmp_path / "model.sqlite3")
    client = TestClient(create_app(settings), base_url="http://127.0.0.1:8014")
    def forbidden(*args, **kwargs):
        raise AssertionError("Model setup must not contact any provider")
    monkeypatch.setattr(httpx.Client, "post", forbidden)
    # TestClient.post delegates to request rather than httpx.Client.post.
    command = {"base_url": "http://localhost:8000/v1", "model": "fixture/gemma", "key": "labelled-private-model-key"}
    headers = {"Origin": "http://127.0.0.1:8014"}
    route = "/api/local/model"
    def post(**kwargs):
        return client.request("POST", route, **kwargs)
    saved = post(headers=headers, json=command)
    assert saved.status_code == 200
    assert saved.json()["gemma_ready"] is True
    assert saved.json()["worker_online"] is False
    for path in ("/api/health", "/api/runs", "/openapi.json"):
        assert command["key"] not in client.get(path).text
    assert command["key"] not in saved.text
    for response, status in (
        (post(json=command), 403),
        (post(headers={"Origin": "https://attacker.example"}, json=command), 403),
        (post(headers={**headers, "Host": "attacker.example"}, json=command), 403),
        (post(headers=headers, content="not-json"), 415),
        (post(headers=headers, json={**command, "extra": command["key"]}), 422),
        (post(headers=headers, json={**command, "base_url": "https://user:secret@model.example/v1"}), 422),
        (post(headers=headers, json={**command, "base_url": "http://remote.example/v1"}), 422),
        (post(headers=headers, json={**command, "key": command["key"] * 300}), 413),
    ):
        assert response.status_code == status
        assert command["key"] not in response.text
        assert LocalModelCredentials(settings.db_path).read().model == "fixture/gemma"
    assert client.get("/api/runs").json() == []


@pytest.mark.parametrize("endpoint", ["file:///model", "https://model.example/v1?key=secret", "https://model.example/#secret", "http://localhost:bad/v1"])
def test_model_endpoint_validation(endpoint):
    with pytest.raises(ValueError):
        LocalModelInput(base_url=endpoint, model="fixture")


def test_hosted_and_preview_reject_local_model_changes(tmp_path):
    from scripts.landing_demo_preview import create_preview_app
    preview = TestClient(create_preview_app(tmp_path / "preview.sqlite3"), base_url="http://127.0.0.1:8018")
    command = {"base_url": "http://localhost:8000/v1", "model": "fixture"}
    assert preview.post("/api/local/model", headers={"Origin": "http://127.0.0.1:8018"}, json=command).status_code == 409
    settings = Settings(db_path=tmp_path / "hosted.sqlite3", mode="hosted", supabase_url="https://auth.example",
                        app_url="https://app.example", supabase_publishable_key="sb_publishable_fixture", database_url="postgresql://unused")
    hosted = TestClient(create_app(settings), base_url="https://app.example")
    assert hosted.post("/api/local/model", json=command).status_code == 404
    assert not LocalModelCredentials(settings.db_path).path.exists()


def test_next_worker_uses_saved_model_and_failed_replacement_keeps_previous(tmp_path, monkeypatch):
    import sqlite3

    from shortlist.domain import Criterion, Profile
    from shortlist.local_credentials import CredentialUnavailable
    from shortlist.store import Store
    from shortlist.worker import work

    settings = Settings(db_path=tmp_path / "research.sqlite3")
    store = Store(settings.db_path)
    identity = store.create_run(Profile(seller_url="https://seller.example/", offer="Labelled offer",
        target="Labelled target", criteria=(Criterion(id="ai", description="AI software"),)), "dynamic-model")
    config = LocalModelInput(base_url="http://localhost:8000/v1", model="fixture", key="labelled-secret")
    credentials = LocalModelCredentials(settings.db_path)
    credentials.save(config)
    received = []
    def execute(scoped, configuration, run_id):
        received.append((run_id, configuration.gemma_base_url, configuration.gemma_model, configuration.gemma_key))
    monkeypatch.setattr("shortlist.worker.execute_run", execute)
    work(settings, once=True)
    assert received == [(identity, config.base_url, config.model, config.key)]
    assert not store.worker_online()
    connect = sqlite3.connect
    class FailedCommit(sqlite3.Connection):
        def commit(self):
            raise sqlite3.OperationalError("Labelled commit failure")
    monkeypatch.setattr(sqlite3, "connect", lambda *args, **kwargs: connect(*args, **kwargs, factory=FailedCommit))
    with pytest.raises(CredentialUnavailable):
        credentials.save(LocalModelInput(base_url="https://replacement.example/v1", model="replacement"))
    assert credentials.read() == config
