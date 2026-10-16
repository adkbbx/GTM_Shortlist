"""Preflight must fail closed and keep connection credentials out of diagnostics."""

import json

import httpx
import psycopg

from scripts import audit_hosted


def test_failed_connections_are_redacted_and_never_count_as_success(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(audit_hosted, "PRIVATE", tmp_path)
    monkeypatch.setattr(audit_hosted, "dotenv_values", lambda path: {})

    def http_failure(public):
        raise httpx.ConnectError("secret-http-token-in-url")

    def database_failure():
        raise psycopg.OperationalError("secret-database-password-in-dsn")

    monkeypatch.setattr(audit_hosted, "http_audit", http_failure)
    monkeypatch.setattr(audit_hosted, "database_audit", database_failure)
    report = audit_hosted.main()
    assert report["preflight_passed"] is False
    assert report["http"] == {"error_type": "ConnectError", "incomplete": True}
    assert report["database"] == {"error_type": "OperationalError", "incomplete": True}
    output = capsys.readouterr().out
    saved = (tmp_path / "evaluations" / "hosted-preflight.json").read_text()
    assert "secret-" not in output + saved
    assert json.loads(saved) == report


def test_incomplete_report_does_not_pass():
    assert audit_hosted.preflight_passed({"http": {"health": {"status": 200}}}) is False


def test_auth_setup_mismatch_and_public_access_fail_preflight(monkeypatch):
    # Exercise actual response parsing, including an auth-project mismatch and a
    # reachable but mistakenly public runs endpoint. Neither is a healthy gate.
    def response(request):
        if request.url.path == "/api/auth/setup":
            return httpx.Response(200, json={"supabase_url": "https://wrong.example",
                                             "publishable_key": "wrong-key", "redirect_url": "http://localhost/"})
        if request.url.path == "/auth/v1/settings":
            return httpx.Response(200, json={"disable_signup": False, "mailer_autoconfirm": False,
                                             "external": {"email": True}})
        return httpx.Response(200, json={"mode": "hosted"})

    client = httpx.Client
    monkeypatch.setattr(audit_hosted.httpx, "Client", lambda **kwargs: client(
        transport=httpx.MockTransport(response), **kwargs))
    report = {"http": audit_hosted.http_audit({"SHORTLIST_APP_URL": "https://app.example",
                "SUPABASE_URL": "https://project.example", "SUPABASE_PUBLISHABLE_KEY": "fixture-key"})}
    assert report["http"]["auth_setup"]["project_matches_local"] is False
    assert report["http"]["auth_setup"]["redirect_matches_app"] is False
    assert report["http"]["unauthenticated_runs"]["status"] == 200
    assert audit_hosted.preflight_passed(report) is False
