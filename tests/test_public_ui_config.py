import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import shortlist.api as api_module
from shortlist.config import Settings


@pytest.mark.parametrize("public_id", ["", "synthetic-public-id"])
def test_runtime_public_id_only_reaches_ui_not_secrets(tmp_path, monkeypatch, public_id):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text('<html><head></head><body>Fixture UI</body></html>', encoding="utf-8")
    (dist / "asset.js").write_text('console.log("fixture")', encoding="utf-8")
    monkeypatch.setattr(api_module, "__file__", str(tmp_path / "src" / "shortlist" / "api.py"))
    settings = Settings(db_path=tmp_path / "ui.sqlite3", brandfetch_client_id=public_id, gemma_key="private-test-secret")
    with TestClient(api_module.create_app(settings)) as client:
        for path in ("/", "/index.html"):
            response = client.get(path)
            assert response.status_code == 200
            assert response.headers["cache-control"] == "no-cache"
            assert 'Fixture UI' in response.text
            assert "private-test-secret" not in response.text
            assert ('name="shortlist-company-suggestions-client-id"' in response.text) == bool(public_id)
            if public_id:
                assert f'content="{public_id}"' in response.text
        assert client.get("/asset.js").status_code == 200
        assert client.get("/api/runs").json() == []


@pytest.mark.parametrize("value", ['bad"/><script>', "has spaces", "x" * 201])
def test_public_id_rejects_invalid_configuration(value):
    with pytest.raises(ValidationError):
        Settings(brandfetch_client_id=value)


def test_public_id_loads_from_runtime_environment(monkeypatch):
    monkeypatch.setenv("SHORTLIST_BRANDFETCH_CLIENT_ID", "synthetic-public-id")
    assert Settings.load().brandfetch_client_id == "synthetic-public-id"
