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
