"""Meta Responses and Baseten Chat Completions clients against recorded-shape fakes (httpx.MockTransport).
These response bodies are SYNTHETIC and follow the documented field names; a live smoke test is still required."""
import json

import httpx
import pytest
from pydantic import ValidationError

from shortlist.agent.providers import (
    FETCH_TOOL,
    WEB_SEARCH_TOOL,
    AgentProviderError,
    BasetenSkeptic,
    MetaInvestigator,
    parse_response,
)
from shortlist.agent.settings import BASETEN_MODEL, AgentSettings

KEY = "labelled-test-key-not-real"
RESPONSE = {
    "id": "resp_synthetic_1", "status": "completed",
    "output": [
        {"type": "web_search_call", "id": "ws_1", "status": "completed",
         "action": {"type": "search", "query": "acme help desk"},
         "results": [{"title": "Acme", "url": "https://acme.example/", "snippet": "SYNTHETIC result"}]},
        {"type": "function_call", "id": "fc_1", "call_id": "call_1", "name": "fetch_page",
         "arguments": "{\"url\": \"https://acme.example/careers\"}"},
        {"type": "message", "role": "assistant", "content": [{
            "type": "output_text", "text": "{\"ok\": true}",
            "annotations": [{"type": "url_citation", "url": "https://acme.example/", "title": "Acme",
                             "start_index": 0, "end_index": 4}]}]},
    ],
    "usage": {"input_tokens": 1200, "output_tokens": 300, "total_tokens": 1500},
}


def settings(**changes):
    return AgentSettings(meta_api_key=KEY, baseten_api_key=KEY, **changes)


def test_responses_request_shape_and_parsing():
    seen = {}

    def handler(request: httpx.Request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=RESPONSE)

    investigator = MetaInvestigator(settings(), transport=httpx.MockTransport(handler))
    turn = investigator.respond(instructions="Investigate", input=[{"role": "user", "content": "hi"}],
                                tools=[WEB_SEARCH_TOOL, FETCH_TOOL], previous_response_id="resp_0")
    assert seen["url"] == "https://api.meta.ai/v1/responses"
    assert seen["auth"] == f"Bearer {KEY}"
    body = seen["body"]
    assert body["model"] == "muse-spark-1.3"
    # Search context defaults to low (META_SEARCH_CONTEXT); no stage limit was given, so no max_tool_calls.
    assert body["tools"][0] == {"type": "web_search", "search_context_size": "low"} and "max_tool_calls" not in body
    assert body["tools"][1]["type"] == "function" and body["tools"][1]["name"] == "fetch_page"
    assert "function" not in body["tools"][1]  # Flat Responses format, not the Chat Completions nesting.
    assert body["include"] == ["web_search_call.results"] and body["parallel_tool_calls"] is True
    assert body["previous_response_id"] == "resp_0"
    assert turn.text == '{"ok": true}' and turn.response_id == "resp_synthetic_1"
    assert turn.searches[0].query == "acme help desk" and turn.searches[0].results[0].url == "https://acme.example/"
    assert turn.function_calls[0].call_id == "call_1" and turn.function_calls[0].name == "fetch_page"
    assert turn.citations[0].url == "https://acme.example/"
    assert (turn.input_tokens, turn.output_tokens, turn.search_count) == (1200, 300, 1)


def test_search_results_under_action_sources_are_read():
    body = {"output": [{"type": "web_search_call", "action": {"query": "q", "sources": [
        {"url": "https://a.example/", "title": "A", "content": "snippet"}]}}]}
    assert parse_response(body).searches[0].results[0].snippet == "snippet"


def test_page_actions_are_not_searches_and_query_lists_are_read():
    """The first live run had web_search_call items without a query, priced and logged as searches. SYNTHETIC body."""
    body = {"output": [
        {"type": "web_search_call", "action": {"type": "open_page", "url": "https://a.example/pricing"}},
        {"type": "web_search_call", "action": {"type": "find", "pattern": "SOC 2", "url": "https://a.example/"}},
        {"type": "web_search_call", "action": {"type": "search", "queries": ["acme pricing", "acme plans"]}},
        {"type": "web_search_call", "action": {"type": "search"}}]}
    turn = parse_response(body)
    assert [search.query for search in turn.searches] == ["acme pricing", ""] and turn.search_count == 2
    assert len(turn.output_items) == 4  # every item is still replayed to the model


def test_stage_search_limit_and_context_reach_the_request():
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"output": [], "usage": {}})

    MetaInvestigator(settings(), transport=httpx.MockTransport(handler)).respond(
        instructions="x", input=[], tools=[WEB_SEARCH_TOOL, FETCH_TOOL], max_searches=2)
    MetaInvestigator(settings(meta_search_context=None), transport=httpx.MockTransport(handler)).respond(
        instructions="x", input=[], tools=[FETCH_TOOL], max_searches=2)
    assert seen[0]["max_tool_calls"] == 2 and seen[0]["tools"][0]["search_context_size"] == "low"
    assert "max_tool_calls" not in seen[1]  # without the search tool there is nothing for the cap to limit


def test_no_include_without_web_search():
    seen = {}

    def handler(request):
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"output": [], "usage": {}})

    MetaInvestigator(settings(), transport=httpx.MockTransport(handler)).respond(
        instructions="x", input=[], tools=[])
    assert "include" not in seen and "tools" not in seen


def test_provider_errors_never_include_key_or_body():
    def handler(request):
        return httpx.Response(401, text=f"bad key {KEY}")

    with pytest.raises(AgentProviderError) as raised:
        MetaInvestigator(settings(), transport=httpx.MockTransport(handler)).respond(instructions="x", input=[], tools=[])
    assert KEY not in str(raised.value) and "401" in str(raised.value)
    with pytest.raises(AgentProviderError) as raised:
        BasetenSkeptic(settings(), transport=httpx.MockTransport(handler)).chat([{"role": "user", "content": "x"}])
    assert KEY not in str(raised.value)


def test_missing_keys_are_explained():
    with pytest.raises(AgentProviderError, match="META_MODEL_API_KEY"):
        MetaInvestigator(AgentSettings())
    with pytest.raises(AgentProviderError, match="BASETEN_API_KEY"):
        BasetenSkeptic(AgentSettings())


def test_baseten_chat_request_and_usage():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "{\"decisions\": []}"}}],
                                         "usage": {"prompt_tokens": 50, "completion_tokens": 7}})

    turn = BasetenSkeptic(settings(), transport=httpx.MockTransport(handler)).chat([{"role": "user", "content": "x"}])
    assert seen["url"] == "https://inference.baseten.co/v1/chat/completions"
    assert seen["body"]["model"] == BASETEN_MODEL == "meta-models/muse-spark-open-1026"
    assert seen["body"]["response_format"] == {"type": "json_object"}
    assert (turn.input_tokens, turn.output_tokens) == (50, 7)
    BasetenSkeptic(settings(baseten_json_mode=False), transport=httpx.MockTransport(handler)).chat([])
    assert "response_format" not in seen["body"]


def test_settings_defaults_and_guards(monkeypatch):
    for name in ("META_MODEL_API_KEY", "META_MODEL", "BASETEN_MODEL", "BASETEN_BASE_URL", "AGENT_RUN_BUDGET_USD",
                 "META_MODEL_BASE_URL", "AGENT_SKEPTIC", "AGENT_CONCURRENCY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr("shortlist.agent.settings.load_dotenv", lambda: None)
    loaded = AgentSettings.load()
    assert loaded.meta_model == "muse-spark-1.3" and loaded.baseten_model == "meta-models/muse-spark-open-1026"
    assert loaded.run_budget_usd == 1.0 and loaded.concurrency == 5 and loaded.use_skeptic
    with pytest.raises(ValidationError, match="muse-spark-open-1026"):
        AgentSettings(baseten_model="meta-models/muse-spark-open")
    with pytest.raises(ValidationError):
        AgentSettings(meta_base_url="http://api.meta.ai/v1")
    monkeypatch.setenv("AGENT_RUN_BUDGET_USD", "0.25")
    monkeypatch.setenv("AGENT_SKEPTIC", "off")
    assert AgentSettings.load().run_budget_usd == 0.25 and not AgentSettings.load().use_skeptic
    assert KEY not in repr(settings())
