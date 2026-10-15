from fastapi.testclient import TestClient

from scripts.landing_demo_preview import create_preview_app
from shortlist.store import Store


def test_preview_is_labelled_and_cannot_create_runs_or_collect_provider_keys(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist/index.html").write_text("<html><head></head><body>Labelled fixture</body></html>", encoding="utf-8")
    database = tmp_path / "preview.sqlite3"
    store = Store(database)
    identity = store.create_draft("https://seller.example/", "existing-preview")
    client = TestClient(create_preview_app(database))
    html = client.get("/").text
    assert 'name="shortlist-preview-workspace"' in html
    assert "http://127.0.0.1:8019/" in html
    for path in ("/api/sellers", f"/api/runs/{identity}/confirm", "/api/local/tavily"):
        response = client.post(path, json={})
        assert response.status_code == 409
        assert "design preview without a research worker" in response.json()["detail"]
    assert len(store.list_runs()) == 1
    assert store.get_run(identity)["status"] == "queued"
    assert store.get_run(identity)["attempts"] == []


def test_preview_handoff_rejects_external_destinations(tmp_path):
    import pytest
    with pytest.raises(ValueError, match="loopback"):
        create_preview_app(tmp_path / "unused.sqlite3", "https://external.example/")
    assert not (tmp_path / "unused.sqlite3").exists()
