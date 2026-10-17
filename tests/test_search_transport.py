"""Offline search failures remain safe, distinguishable and single-dispatch."""
import httpx
import pytest

from shortlist.config import Settings
from shortlist.providers import ProviderError, SearchProvider


@pytest.mark.parametrize(("failure", "message"), [
    ("timeout", "timed out"),
    ("connection", "connection failed"),
    ("status", "HTTP 429"),
    ("json", "Search request failed"),
    ("shape", "malformed results"),
])
def test_search_transport_errors_never_expose_secrets_or_retry(monkeypatch, failure, message):
    calls = []
    original = httpx.Client

    def reply(request):
        calls.append(request)
        if failure == "timeout":
            raise httpx.ReadTimeout("private-key private-body", request=request)
        if failure == "connection":
            raise httpx.ConnectError("private-key private-body", request=request)
        if failure == "status":
            return httpx.Response(429, text="private-key private-body")
        if failure == "json":
            return httpx.Response(200, text="private-key private-body")
        return httpx.Response(200, json=["private-body"])

    monkeypatch.setattr(httpx, "Client", lambda **kwargs: original(
        transport=httpx.MockTransport(reply), **kwargs))
    provider = SearchProvider(Settings(search_provider="serpapi", serpapi_key="private-key"))
    with pytest.raises(ProviderError, match=message) as error:
        provider.search("labelled fixture", None)
    assert len(calls) == 1
    assert "private-key" not in str(error.value)
    assert "private-body" not in str(error.value)


def test_serpapi_can_wait_for_one_slow_response(monkeypatch):
    original = httpx.Client
    observed = []

    def reply(request):
        observed.append(request.extensions["timeout"])
        return httpx.Response(200, json={"organic_results": [
            {"link": "https://company.example/", "title": "Labelled fixture company"}]})

    monkeypatch.setattr(httpx, "Client", lambda **kwargs: original(
        transport=httpx.MockTransport(reply), **kwargs))
    result = SearchProvider(Settings(search_provider="serpapi", serpapi_key="fixture")).search("fixture", None)
    assert [candidate.domain for candidate in result] == ["company.example"]
    assert observed == [{"connect": 25, "read": 60, "write": 25, "pool": 25}]
