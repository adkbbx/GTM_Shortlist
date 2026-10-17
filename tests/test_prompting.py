"""Labelled Ollama fixtures prove prompt profiles without inference or provider credits."""
import hashlib
import json

import httpx
import pytest

from shortlist.config import Settings
from shortlist.domain import Candidate, Criterion, Profile, Source
from shortlist.progress import public_events, step_label
from shortlist.prompting import Runtime, detect, excerpts, pinned
from shortlist.providers import Extraction, Gemma, ModelOutputError, ProviderError
from shortlist.store import Store
from shortlist.worker import execute_run

LOCAL = "http://localhost:11434/v1"
EVIDENCE = "We supply AI software for business operations."
TEXT = "\n".join(["Labelled fixture company", "Menu", "Close", *[f"Navigation link {i}" for i in range(400)],
                  EVIDENCE, "Founded by labelled fixture people.", *[f"Footer link {i}" for i in range(400)]])


def source(text=TEXT, index=0):
    return Source(id=f"fixture-source-{index}", url=f"https://company.example/{index}", company_domain="company.example",
                  title="Labelled fixture", text=text, content_hash=hashlib.sha256(text.encode()).hexdigest())


PROFILE = Profile(seller_url="https://seller.example", offer="Acquisition research service", target="AI business software",
                  criteria=(Criterion(id="ai", description="Sells AI software for business operations"),))
CANDIDATE = Candidate(domain="company.example", name="Labelled fixture", url="https://company.example/0",
                      provider="fixture", query="fixture")
GOOD = {"name": "Labelled fixture", "findings": [{"status": "supported", "criterion_id": "ai", "evidence": [
    {"source_id": "fixture-source-0", "passage": EVIDENCE, "claim": "The company sells AI software"}]}]}
AUDIT = {"judgments": [{"assessment_id": "criterion:ai", "verdict": "entailed", "reason": "Explicit fixture statement"}]}


def fake_ollama(monkeypatch, replies, *, size="4.6B", context_length=131072, version_status=200,
                capabilities=("completion", "tools", "thinking")):
    """Labelled Ollama: metadata routes plus queued /api/chat replies. Records every request."""
    requests = []

    def reply(request):
        requests.append(request)
        if request.url.path == "/api/version":
            return httpx.Response(version_status, json={"version": "fixture"})
        if request.url.path == "/api/show":
            return httpx.Response(200, json={"details": {"parameter_size": size},
                                             "model_info": {"gemma4.context_length": context_length},
                                             "capabilities": list(capabilities)})
        if request.url.path == "/api/chat":
            content, done = replies.pop(0)
            return httpx.Response(200, json={"message": {"role": "assistant", "content": json.dumps(content)},
                                             "done_reason": done})
        return httpx.Response(404)

    original = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: original(transport=httpx.MockTransport(reply), **kwargs))
    return requests


def chats(requests):
    return [json.loads(r.content) for r in requests if r.url.path == "/api/chat"]


def test_hosted_endpoint_keeps_full_profile_without_probing(monkeypatch):
    def refuse(**kwargs):
        raise AssertionError("A hosted endpoint must not be probed")
    monkeypatch.setattr(httpx, "Client", refuse)
    runtime = detect(Settings(gemma_base_url="https://model.example/v1", gemma_model="labelled-fixture"))
    assert runtime == Runtime(profile="full", ollama=False)
    assert runtime.journal() == {}


@pytest.mark.parametrize(("size", "window", "profile", "context"), [
    ("4.6B", 131072, "compact", 8192), ("31B", 131072, "full", 32768), ("4.6B", 4096, "compact", 4096),
    ("270M", 131072, "compact", 8192)])
def test_ollama_profile_follows_model_size_and_window(monkeypatch, size, window, profile, context):
    fake_ollama(monkeypatch, [], size=size, context_length=window)
    runtime = detect(Settings(gemma_base_url=LOCAL, gemma_model="labelled-fixture"))
    assert (runtime.profile, runtime.ollama, runtime.context, runtime.thinking) == (profile, True, context, True)
    assert runtime.journal() == {"prompt_profile": profile, "transport": "ollama", "context": context}


def test_other_local_server_is_compact_without_native_transport(monkeypatch):
    fake_ollama(monkeypatch, [], version_status=404)
    runtime = detect(Settings(gemma_base_url="http://127.0.0.1:1234/v1", gemma_model="labelled-fixture"))
    assert runtime == Runtime(profile="compact", ollama=False)


def test_operator_override_wins(monkeypatch):
    fake_ollama(monkeypatch, [])
    runtime = detect(Settings(gemma_base_url=LOCAL, gemma_model="labelled-fixture", prompt_profile="full"))
    assert (runtime.profile, runtime.context) == ("full", 32768)


def test_excerpts_keep_verbatim_ranked_windows_within_budget():
    pages = (source(), source("Unrelated second page\n" + "\n".join(f"Filler {i}" for i in range(300)), 1))
    chosen = excerpts(pages, "AI software business operations", 1200)
    assert sum(len(page["text"]) for page in chosen) <= 1200
    text = chosen[0]["text"]
    assert text.startswith("Labelled fixture company") and EVIDENCE in text
    assert [page["id"] for page in chosen] == ["fixture-source-0"]
    normalized = " ".join(TEXT.split())
    assert all(" ".join(part.split()) in normalized for part in text.split("\n…\n"))


def test_pinned_schema_limits_identifiers_in_nested_definitions():
    schema = pinned(Extraction.model_json_schema(), criterion_id=["ai"], exclusion_id=[])
    found = [node["properties"]["criterion_id"] for node in schema["$defs"].values() if "criterion_id" in node.get("properties", {})]
    assert found and all(item == {"type": "string", "enum": ["ai"]} for item in found)
    assert all(node["properties"]["exclusion_id"].get("enum") is None
               for node in schema["$defs"].values() if "exclusion_id" in node.get("properties", {}))


def test_compact_research_uses_native_window_schema_and_excerpts(monkeypatch):
    requests = fake_ollama(monkeypatch, [(GOOD, "stop")])
    record = Gemma(Settings(gemma_base_url=LOCAL, gemma_model="labelled-fixture")).research(PROFILE, CANDIDATE, (source(),))
    assert record.findings[0].status == "supported"
    body = chats(requests)[0]
    assert body["options"]["num_ctx"] == 8192 and body["think"] is False and body["stream"] is False
    schema = body["format"]
    assert set(schema["properties"]) == {"name", "findings", "exclusion_findings"}
    assert schema["properties"]["findings"]["maxItems"] == 1 and schema["properties"]["exclusion_findings"]["maxItems"] == 0
    user = body["messages"][1]["content"]
    assert user.endswith("quoting passages verbatim from the source excerpts.")
    payload = json.loads(user.split("\n\nTask: ")[0])
    assert "profile" not in payload and payload["criteria"][0]["id"] == "ai"
    assert EVIDENCE in payload["sources"][0]["text"] and len(payload["sources"][0]["text"]) <= 8000
    assert "Navigation link 200" not in payload["sources"][0]["text"]
    assert "Footer link 399" not in payload["sources"][0]["text"]


def test_compact_worker_run_saves_research_and_verification(tmp_path, monkeypatch):
    settings = Settings(db_path=tmp_path / "compact.sqlite3", gemma_base_url=LOCAL, gemma_model="labelled-fixture")
    store = Store(settings.db_path)
    run_id = store.create_run(PROFILE, "compact-fixture")
    fence = store.claim(run_id)
    store.checkpoint(run_id, fence, "research", {"candidates": [CANDIDATE.model_dump(mode="json")],
                     "sources": {CANDIDATE.domain: [source().model_dump(mode="json")]}}, "queued")
    requests = fake_ollama(monkeypatch, [(GOOD, "stop"), (AUDIT, "stop")])
    execute_run(store, settings, run_id)
    run = store.get_run(run_id)
    assert run["status"] == "ready"
    assert run["records"][0]["research"]["findings"][0]["status"] == "supported"
    verify = chats(requests)[1]
    assert verify["format"]["$defs"]["Judgment"]["properties"]["assessment_id"]["enum"] == ["criterion:ai"]


def test_truncated_native_reply_is_labelled_and_explained(monkeypatch):
    fake_ollama(monkeypatch, [({"name": "Labelled"}, "length")])
    with pytest.raises(ModelOutputError) as caught:
        Gemma(Settings(gemma_base_url=LOCAL, gemma_model="labelled-fixture")).research(PROFILE, CANDIDATE, (source(),))
    assert caught.value.issues == [{"type": "output_truncated"}]
    label = step_label("model", "model:company.example")
    events = public_events({"checkpoint": {"model_outputs": {"company.example": caught.value.diagnostic()}},
                            "events": [{"label": label, "state": "failed", "detail": "Gemma output failed validation"}]})
    assert "ran out of output space" in events[0]["detail"]


def test_window_too_small_fails_before_dispatch(monkeypatch):
    requests = fake_ollama(monkeypatch, [], context_length=2048)
    with pytest.raises(ProviderError, match="context window is too small"):
        Gemma(Settings(gemma_base_url=LOCAL, gemma_model="labelled-fixture")).research(PROFILE, CANDIDATE, (source(),))
    assert not chats(requests)


def test_hosted_json_reply_cut_at_length_is_labelled(monkeypatch):
    original = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: original(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"choices": [{"message": {"content": '{"name": "Lab'},
                                                               "finish_reason": "length"}]})), **kwargs))
    with pytest.raises(ModelOutputError) as caught:
        Gemma(Settings(gemma_base_url="https://model.example/v1", gemma_model="labelled-fixture")).research(
            PROFILE, CANDIDATE, (source(),))
    assert caught.value.issues == [{"type": "output_truncated"}]


def test_hosted_research_request_keeps_full_payload(monkeypatch):
    requests = []
    original = httpx.Client

    def reply(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(GOOD)}}]})
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: original(transport=httpx.MockTransport(reply), **kwargs))
    Gemma(Settings(gemma_base_url="https://model.example/v1", gemma_model="labelled-fixture")).research(
        PROFILE, CANDIDATE, (source(),))
    payload = json.loads(requests[0]["messages"][1]["content"])
    assert payload["sources"][0]["text"] == TEXT and payload["profile"]["id"] == PROFILE.id
    assert requests[0]["max_tokens"] == 3500 and requests[0]["response_format"] == {"type": "json_object"}
    assert '"enum": ["ai"]' in requests[0]["messages"][0]["content"]
