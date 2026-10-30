"""The deployed demo answered "Investigator returned HTTP 404" where a laptop worked: Meta's model_not_found, which
depends on the host's region. Errors now carry the provider's error code, and the demo's health says whether Meta
offers the model to that server. Bodies are SYNTHETIC, shaped like the Meta Model API's documented errors."""
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from shortlist.agent.providers import (
    AgentProviderError,
    MetaInvestigator,
    ModelCheck,
    error_code,
    meta_model_check,
)
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


TRACE = "fl=1f1\nh=www.cloudflare.com\nip=203.0.113.9\nloc=DE\ncolo=FRA\nhttp=http/1.1\n"


def meta_and_cloudflare(models_status, models_body, trace=TRACE):
    def handle(request):
        if request.url.host == "www.cloudflare.com":
            return httpx.Response(200, text=trace)
        return httpx.Response(models_status, json=models_body)
    return httpx.MockTransport(handle)


def test_model_check_says_what_meta_offers_this_server_and_where_it_is():
    listing = {"data": [{"id": "muse-spark-1.3"}, {"id": "muse-wonder-1.0"}, {"id": "<script>"}, {"name": "no id"}]}
    settings = AgentSettings(meta_api_key=KEY)
    check = meta_model_check(settings, transport=meta_and_cloudflare(200, listing))
    assert check == ModelCheck(available=True, offered=("muse-spark-1.3", "muse-wonder-1.0"), location="DE/FRA")
    other = settings.model_copy(update={"meta_model": "muse-spark-9"})
    assert meta_model_check(other, transport=meta_and_cloudflare(200, listing)).available is False
    down = meta_model_check(settings, transport=meta_and_cloudflare(503, {"error": "down"}, trace="loc=<b>\ncolo=FRA"))
    assert down == ModelCheck()  # unknown, and a trace that is not plain codes is dropped
    assert meta_model_check(AgentSettings(), transport=meta_and_cloudflare(200, listing)) == ModelCheck()  # no key


def test_demo_health_reports_model_availability_at_most_every_ten_minutes(tmp_path, monkeypatch):
    calls = []

    def check(settings):
        calls.append(settings.meta_model)
        return ModelCheck(available=False, offered=("muse-wonder-1.0",), location="DE/FRA")

    settings = PublicSettings(app_url="https://demo.example", secret="public-demo-test-secret-0123456789abcdef",
                              data_dir=tmp_path / "runs", dist_dir=tmp_path / "missing")
    app = create_public_app(settings, agent_settings=lambda: AgentSettings(meta_api_key=KEY),
                            providers=lambda agent: synthetic_providers(), model_check=check)
    with TestClient(app, base_url="https://demo.example") as client:
        health = client.get("/api/health").json()
        assert (health["investigator_model_available"], health["investigator_models_offered"],
                health["server_location"]) == (False, ["muse-wonder-1.0"], "DE/FRA")
        assert client.get("/api/health").json()["investigator_model_available"] is False
        assert calls == ["muse-spark-1.3"]
        later = time.monotonic() + 601
        monkeypatch.setattr("shortlist.agent.public.time.monotonic", lambda: later)
        client.get("/api/health")
        assert len(calls) == 2
