from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError

from shortlist.auth import AuthenticationError, AuthUnavailable, verify_user
from shortlist.config import Settings


def hosted_settings(**overrides):
    return Settings(mode="hosted", supabase_url="https://auth.example", app_url="https://app.example",
                    supabase_publishable_key="sb_publishable_fixture", database_url="postgresql://fixture",
                    **overrides)


def test_configuration_errors_do_not_print_raw_secret_inputs():
    secret = "labelled-secret-must-not-appear-in-startup-logs"
    with pytest.raises(ValidationError) as failed:
        Settings(mode="hosted", app_url="http://invalid.example", supabase_url="https://auth.example",
                 supabase_publishable_key="sb_publishable_fixture", database_url=secret, gemma_key=secret)
    assert secret not in str(failed.value)
    assert secret not in repr(failed.value)


@pytest.mark.parametrize("field,variable", [("supabase_url", "SUPABASE_URL"), ("app_url", "SHORTLIST_APP_URL")])
@pytest.mark.parametrize("invalid", ["", "http://app.example", "https://app.example/path",
                                    "[https://app.example](https://app.example)", "https://app.example:bad"])
def test_hosted_origin_error_names_the_setting_without_echoing_values(field, variable, invalid):
    values = {"mode": "hosted", "supabase_url": "https://auth.example", "app_url": "https://app.example",
              "database_url": "private-database-value", "supabase_publishable_key": "sb_publishable_fixture"}
    values[field] = invalid
    with pytest.raises(ValidationError) as failure:
        Settings(**values)
    message = str(failure.value)
    assert variable in message and "plain HTTPS origin" in message
    assert "private-database-value" not in message
    if invalid:
        assert invalid not in message


@pytest.mark.parametrize("variable", ["SUPABASE_URL", "SHORTLIST_APP_URL"])
def test_actual_container_startup_reports_missing_setting_privately(variable):
    import os
    import subprocess
    import sys

    environment = dict(os.environ, SHORTLIST_MODE="hosted", SUPABASE_URL="https://auth.example",
                       SHORTLIST_APP_URL="https://app.example", SUPABASE_PUBLISHABLE_KEY="sb_publishable_fixture",
                       SHORTLIST_DATABASE_URL="private-startup-database-value")
    environment[variable] = ""
    process = subprocess.run([sys.executable, "-m", "shortlist.container_entrypoint", "api"],
                             env=environment, capture_output=True, text=True, timeout=10, check=False)
    assert process.returncode != 0
    assert variable in process.stderr and "plain HTTPS origin" in process.stderr
    assert "private-startup-database-value" not in process.stderr + process.stdout


def test_verified_identity_comes_from_trusted_user_endpoint():
    identity = uuid4()

    def endpoint(request):
        assert request.url == "https://auth.example/auth/v1/user"
        assert request.headers["authorization"] == "Bearer labelled-token"
        assert request.headers["apikey"] == "sb_publishable_fixture"
        return httpx.Response(200, json={"id": str(identity), "role": "authenticated",
                                        "email_confirmed_at": "2026-10-14T00:00:00Z"})

    user = verify_user(hosted_settings(), "labelled-token", transport=httpx.MockTransport(endpoint))
    assert user.id == identity


@pytest.mark.parametrize("change", [
    {"role": "service_role"}, {"email_confirmed_at": None}, {"is_anonymous": True},
    {"deleted_at": "2026-10-14T00:00:00Z"}, {"banned_until": "2099-01-01T00:00:00Z"},
])
def test_unconfirmed_anonymous_deleted_banned_and_privileged_users_rejected(change):
    data = {"id": str(uuid4()), "role": "authenticated", "email_confirmed_at": "2026-10-14T00:00:00Z", **change}
    with pytest.raises(AuthenticationError):
        verify_user(hosted_settings(), "fixture", transport=httpx.MockTransport(lambda _: httpx.Response(200, json=data)))


@pytest.mark.parametrize("status", [401, 403, 302, 429, 500])
def test_invalid_and_unavailable_provider_responses_are_distinguished(status):
    error = AuthenticationError if status in (401, 403) else AuthUnavailable
    with pytest.raises(error):
        verify_user(hosted_settings(), "fixture", transport=httpx.MockTransport(lambda _: httpx.Response(status)))


def test_timeout_malformed_and_oversized_bodies_never_authorize():
    def timed_out(request):
        raise httpx.ReadTimeout("Labelled timeout", request=request)

    for endpoint in (timed_out, lambda _: httpx.Response(200, json={"id": "invented"}),
                     lambda _: httpx.Response(200, content=b"x" * 65537)):
        with pytest.raises(AuthUnavailable):
            verify_user(hosted_settings(), "fixture", transport=httpx.MockTransport(endpoint))


@pytest.mark.parametrize("token", ["", "two words", "x" * 8193])
def test_invalid_bearers_do_not_dispatch(token):
    def forbidden(request):
        raise AssertionError("Invalid bearer must not dispatch")
    with pytest.raises(AuthenticationError):
        verify_user(hosted_settings(), token, transport=httpx.MockTransport(forbidden))


@pytest.mark.parametrize("origin", ["http://auth.example", "https://user:password@auth.example", "https://auth.example/path",
                                    "https://auth.example?redirect=elsewhere"])
def test_hosted_configuration_rejects_unsafe_or_ambiguous_origins(origin):
    with pytest.raises(ValidationError):
        Settings(mode="hosted", supabase_url=origin, app_url="https://app.example",
                 supabase_publishable_key="fixture", database_url="fixture")


@pytest.mark.parametrize("key", ["sb_secret_do_not_expose", "legacy-service-role-token"])
def test_secret_keys_cannot_be_exposed_in_auth_setup(key):
    with pytest.raises(ValidationError, match="publishable key"):
        Settings(mode="hosted", supabase_url="https://auth.example", app_url="https://app.example",
                 supabase_publishable_key=key, database_url="fixture")


def test_public_auth_setup_exposes_only_public_configuration(tmp_path):
    from fastapi.testclient import TestClient

    from shortlist.api import create_app
    local = TestClient(create_app(Settings(db_path=tmp_path / "local.sqlite3")))
    assert local.get("/api/auth/setup").json() == {"mode": "local"}
    hosted = TestClient(create_app(hosted_settings()), base_url="https://app.example")
    assert hosted.get("/api/auth/setup").json() == {
        "mode": "hosted", "supabase_url": "https://auth.example",
        "publishable_key": "sb_publishable_fixture", "redirect_url": "https://app.example/",
    }
