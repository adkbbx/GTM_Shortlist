"""The deployed demo answered "Investigator returned HTTP 404" where a laptop worked: Meta's model_not_found, which
depends on the host's region. Errors now carry the provider's error code, and the demo's health says whether Meta
offers the model to that server. Bodies are SYNTHETIC, shaped like the Meta Model API's documented errors."""
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from shortlist.agent.providers import AgentProviderError, MetaInvestigator, error_code, meta_model_listed
from shortlist.agent.public import PublicSettings, create_public_app
from shortlist.agent.settings import AgentSettings
from shortlist.agent.synthetic import synthetic_providers

KEY = "labelled-test-key-not-real"
NOT_FOUND = {"error": {"type": "invalid_request_error", "code": "model_not_found",
                       "message": "The requested model was not found."}}


def reply(status, body=None, text=None):
    return httpx.MockTransport(lambda request: httpx.Response(status, json=body) if body is not None
                               else httpx.Response(status, text=text or ""))


def test_errors_carry_the_provider_code_and_nothing_else():
    investigator = MetaInvestigator(AgentSettings(meta_api_key=KEY), transport=reply(404, NOT_FOUND))
    with pytest.raises(AgentProviderError) as raised:
        investigator.respond(instructions="x", input=[], tools=[])
    assert str(raised.value) == "Investigator returned HTTP 404 (model_not_found)"
    assert error_code(httpx.Response(500, text="<html>upstream</html>")) == ""
    assert error_code(httpx.Response(401, json={"error": {"code": KEY}})) == ""  # never a key-like value
    assert error_code(httpx.Response(429, json={"error": {"type": "rate_limit_error"}})) == " (rate_limit_error)"


def test_model_listing_says_whether_this_server_can_use_the_model():
    listing = {"data": [{"id": "muse-spark-1.3"}, {"id": "muse-wonder-1.0"}]}
    settings = AgentSettings(meta_api_key=KEY)
    assert meta_model_listed(settings, transport=reply(200, listing)) is True
    assert meta_model_listed(settings.model_copy(update={"meta_model": "muse-spark-9"}), transport=reply(200, listing)) is False
    assert meta_model_listed(settings, transport=reply(503, text="down")) is None
    assert meta_model_listed(AgentSettings(), transport=reply(200, listing)) is None  # no key, nothing to ask


def test_demo_health_reports_model_availability_at_most_every_ten_minutes(tmp_path, monkeypatch):
    calls = []

    def check(settings):
        calls.append(settings.meta_model)
        return False

    settings = PublicSettings(app_url="https://demo.example", secret="public-demo-test-secret-0123456789abcdef",
                              data_dir=tmp_path / "runs", dist_dir=tmp_path / "missing")
    app = create_public_app(settings, agent_settings=lambda: AgentSettings(meta_api_key=KEY),
                            providers=lambda agent: synthetic_providers(), model_check=check)
    with TestClient(app, base_url="https://demo.example") as client:
        assert client.get("/api/health").json()["investigator_model_available"] is False
        assert client.get("/api/health").json()["investigator_model_available"] is False
        assert calls == ["muse-spark-1.3"]
        later = time.monotonic() + 601
        monkeypatch.setattr("shortlist.agent.public.time.monotonic", lambda: later)
        client.get("/api/health")
        assert len(calls) == 2
