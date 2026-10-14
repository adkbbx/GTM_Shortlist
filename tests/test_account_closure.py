import json
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from shortlist.account_closure import Closing, admin_user_request, close_account
from shortlist.api import create_app
from shortlist.auth import AuthUnavailable
from shortlist.config import Settings


@pytest.fixture
def settings():
    return Settings(mode="hosted", database_url="postgresql://labelled-unused", worker_database_url="postgresql://labelled-unused",
                    supabase_url="https://auth.example", supabase_publishable_key="sb_publishable_fixture",
                    supabase_admin_key="sb_secret_private_fixture", app_url="https://app.example")


@pytest.mark.parametrize("response", [httpx.Response(302, headers={"location": "https://elsewhere.example"}),
                                    httpx.Response(404, json={"error_code": "unknown_route"}),
                                    httpx.Response(500, json={"error": "private-provider-payload"}),
                                    httpx.Response(200, content=b"not json")])
def test_admin_preflight_fails_closed_without_provider_payload_leaks(settings, response):
    calls = []

    def provider(request):
        calls.append(request.url)
        return response

    with pytest.raises(AuthUnavailable) as error:
        admin_user_request(settings, uuid4(), "GET", transport=httpx.MockTransport(provider))
    assert str(error.value) == "Identity administration is unavailable"
    assert error.value.__cause__ is None
    assert len(calls) == 1


def test_delete_accepts_only_success_or_confirmed_user_absence(settings):
    identity = uuid4()
    for response in (httpx.Response(204), httpx.Response(404, json={"error_code": "user_not_found"})):
        assert admin_user_request(settings, identity, "DELETE", transport=httpx.MockTransport(lambda _, reply=response: reply)) is None
    for response in (httpx.Response(404, json={}), httpx.Response(403, json={"error_code": "user_not_found"}),
                     httpx.Response(429), httpx.Response(404, content=b"x" * 65537)):
        with pytest.raises(AuthUnavailable):
            admin_user_request(settings, identity, "DELETE", transport=httpx.MockTransport(lambda _, reply=response: reply))


def test_admin_secret_is_not_public_and_local_closure_is_unavailable(settings, tmp_path):
    client = TestClient(create_app(settings), base_url="https://app.example")
    assert "sb_secret" not in client.get("/api/auth/setup").text
    assert "sb_secret" not in client.get("/api/service").text
    assert "sb_secret" not in client.get("/openapi.json").text
    identity = uuid4()
    with pytest.raises(ValueError, match="Hosted closure"):
        close_account(Settings(db_path=tmp_path / "local.sqlite3"), identity, identity)
    with pytest.raises(ValidationError) as error:
        Settings(supabase_admin_key="sb_publishable_private-input-must-not-leak")
    assert "private-input-must-not-leak" not in str(error.value)


def test_operator_cli_reports_pending_state_with_nonzero_exit(settings, monkeypatch, capsys):
    from shortlist.cli import main

    identity = uuid4()
    monkeypatch.setattr("shortlist.cli.Settings.load", lambda: settings)
    monkeypatch.setattr("sys.argv", ["shortlist", "close-account", "--workspace", str(identity), "--confirm", str(identity)])

    def pending(cfg, workspace, confirmation):
        assert cfg is settings and workspace == confirmation == identity
        return Closing(erased_in_batch=100, remaining_runs=1, reason="research_remaining")

    monkeypatch.setattr("shortlist.account_closure.close_account", pending)
    with pytest.raises(SystemExit) as exit_code:
        main()
    assert exit_code.value.code == 2
    result = json.loads(capsys.readouterr().out)
    assert result["state"] == "closing" and result["identity_removal"] == "unconfirmed"
