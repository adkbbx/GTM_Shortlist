"""Seller response contracts and paid-step replay, using labelled HTTP fixtures."""
import hashlib
import json

import httpx
import pytest

from shortlist.config import Settings
from shortlist.domain import Source
from shortlist.providers import Gemma, ModelOutputError, SellerDraft
from shortlist.store import Store
from shortlist.worker import execute_run

BUYER_SUMMARY = {"seller_offer": "Labelled fixture payroll software", "target_customer": "Business payroll teams",
                 "customer_criteria": [{"id": "business", "subject": "target_customer",
                                        "customer_characteristic": "Sells to businesses", "required": True}],
                 "unknowns": ["Private ownership is not established by this page"]}

SUMMARY = {"offer": "Labelled fixture payroll software", "target": "Business payroll teams",
           "criteria": [{"id": "business", "description": "Sells to businesses", "required": True}],
           "unknowns": ["Private ownership is not established by this page"]}


def tool_message(arguments=None, name="submit_seller_summary"):
    return {"content": None, "tool_calls": [{"type": "function", "function": {
        "name": name, "arguments": json.dumps(SUMMARY) if arguments is None else arguments}}]}


@pytest.fixture
def source():
    text = "Labelled fixture payroll software for business payroll teams."
    return Source(id="fixture-seller", url="https://seller.example/", company_domain="seller.example",
                  title="Labelled seller fixture", text=text, content_hash=hashlib.sha256(text.encode()).hexdigest())


def transport(monkeypatch, message, *, finish_reason="tool_calls", status=200):
    requests = []
    original = httpx.Client
    def reply(request):
        requests.append(json.loads(request.content))
        return httpx.Response(status, json={"choices": [{"message": message, "finish_reason": finish_reason}]})
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: original(transport=httpx.MockTransport(reply), **kwargs))
    return requests


def settings(tmp_path):
    return Settings(db_path=tmp_path / "seller.sqlite3", gemma_base_url="https://model.example/v1",
                    gemma_model="labelled-fixture")


def test_seller_uses_named_function_schema_and_reads_values(tmp_path, source, monkeypatch):
    requests = transport(monkeypatch, tool_message())
    draft = Gemma(settings(tmp_path)).seller(source, output_protocol=2)
    assert draft.model_dump() == SUMMARY
    assert len(requests) == 1
    request = requests[0]
    assert "response_format" not in request
    assert request["tool_choice"] == {"type": "function", "function": {"name": "submit_seller_summary"}}
    parameters = request["tools"][0]["function"]["parameters"]
    original = SellerDraft.model_json_schema()
    assert parameters["properties"]["criteria"]["items"] == original["$defs"]["Criterion"]
    assert "$ref" not in json.dumps(parameters) and "$defs" not in parameters
    assert json.loads(request["messages"][1]["content"])["text"] == source.text
    assert "untrusted data" in request["messages"][0]["content"]


def test_plain_text_criteria_preserve_descriptions_and_get_stable_ids(tmp_path, source, monkeypatch):
    descriptions = ["Sells software to businesses", "Offers a hosted payroll product"]
    payload = {**SUMMARY, "criteria": descriptions}
    requests = transport(monkeypatch, tool_message(json.dumps(payload)))
    draft = Gemma(settings(tmp_path)).seller(source, output_protocol=2)
    assert [item.description for item in draft.criteria] == descriptions
    assert [item.id for item in draft.criteria] == ["criterion-1", "criterion-2"]
    assert all(item.required for item in draft.criteria)
    assert draft.offer == SUMMARY["offer"] and draft.target == SUMMARY["target"]
    assert len(requests) == 1


@pytest.mark.parametrize("criteria", [["x"], ["x" * 501], ["Valid description"] * 13,
                                     ["Valid description", {"description": "Missing id"}], [123]])
def test_text_criteria_do_not_bypass_domain_validation(criteria):
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        SellerDraft.model_validate({**SUMMARY, "criteria": criteria})


@pytest.mark.parametrize("message,finish_reason", [
    ({"content": '{">$defs": {}}'}, "stop"),  # Shape of the captured production failure.
    (tool_message('{">$defs": {}}'), "tool_calls"),
    (tool_message("not JSON"), "tool_calls"),
    (tool_message("[]"), "tool_calls"),
    (tool_message("{}"), "tool_calls"),
    (tool_message(name="untrusted_action"), "tool_calls"),
    ({"tool_calls": [*tool_message()["tool_calls"], *tool_message()["tool_calls"]]}, "tool_calls"),
    (tool_message({"offer": "not a JSON string"}), "tool_calls"),
    (tool_message(), "length"),
])
def test_invalid_response_fails_once_without_fallback_or_retry(tmp_path, source, monkeypatch, message, finish_reason):
    requests = transport(monkeypatch, message, finish_reason=finish_reason)
    with pytest.raises(ModelOutputError) as caught:
        Gemma(settings(tmp_path)).seller(source, output_protocol=2)
    assert len(requests) == 1
    assert caught.value.issues
    assert "Labelled fixture payroll" not in str(caught.value)


def test_legacy_seller_protocol_retains_original_request(tmp_path, source, monkeypatch):
    requests = transport(monkeypatch, {"content": json.dumps(SUMMARY)}, finish_reason="stop")
    assert Gemma(settings(tmp_path)).seller(source, output_protocol=1).model_dump() == SUMMARY
    assert requests[0]["response_format"] == {"type": "json_object"}
    assert "tools" not in requests[0]


@pytest.mark.parametrize("protocol", [1, 2, 3])
def test_worker_restores_saved_seller_outcome_after_crash_without_second_call(tmp_path, source, monkeypatch, protocol):
    config = settings(tmp_path)
    store = Store(config.db_path)
    identity = store.create_draft(source.url, "labelled-seller")
    fence = store.claim(identity)
    checkpoint = store.get_run(identity)["checkpoint"]
    assert checkpoint["seller_output_protocol"] == 3
    legacy = protocol == 1
    if legacy:
        checkpoint.pop("seller_output_protocol")
    else:
        checkpoint["seller_output_protocol"] = protocol
    checkpoint["seller_source"] = source.model_dump(mode="json")
    store.checkpoint(identity, fence, "seller", checkpoint, "queued")
    requests = transport(monkeypatch, {"content": json.dumps(SUMMARY)} if legacy else tool_message(json.dumps(BUYER_SUMMARY if protocol == 3 else SUMMARY)))
    original = store.checkpoint
    class Crash(BaseException):
        pass
    def before_draft_checkpoint(*args, **kwargs):
        if "draft" in args[3]:
            raise Crash()
        return original(*args, **kwargs)
    monkeypatch.setattr(store, "checkpoint", before_draft_checkpoint)
    with pytest.raises(Crash):
        execute_run(store, config, identity)
    with store.connection() as db:
        db.execute("UPDATE runs SET lease_until=0 WHERE id=?", (identity,))
    execute_run(Store(store.path), config, identity)
    run = store.get_run(identity)
    assert run["status"] == "awaiting_confirmation"
    assert run["checkpoint"]["draft"] == SUMMARY
    assert run["checkpoint"]["seller_source"] == source.model_dump(mode="json")
    assert len(requests) == len(run["attempts"]) == 1
    assert ("tools" not in requests[0]) == legacy
    assert not run["records"]


def test_worker_saves_failed_response_and_waits_without_spending_again(tmp_path, source, monkeypatch):
    config = settings(tmp_path)
    store = Store(config.db_path)
    identity = store.create_draft(source.url, "labelled-failed-seller")
    fence = store.claim(identity)
    checkpoint = {**store.get_run(identity)["checkpoint"], "seller_source": source.model_dump(mode="json")}
    store.checkpoint(identity, fence, "seller", checkpoint, "queued")
    requests = transport(monkeypatch, {"content": '{">$defs": {}}'}, finish_reason="stop")
    execute_run(store, config, identity)
    assert not execute_run(store, config, identity)
    run = store.get_run(identity)
    assert run["status"] == "awaiting_confirmation"
    assert "draft" not in run["checkpoint"]
    assert json.loads(run["checkpoint"]["seller_model_output"]["content"])["content"] == '{">$defs": {}}'
    assert len(requests) == len(run["attempts"]) == 1


def test_evaluation_uses_one_model_call_and_refuses_context_drift(tmp_path, source, monkeypatch, capsys):
    from scripts.evaluate_seller import main
    source_file = tmp_path / "source.json"
    source_file.write_text(source.model_dump_json(), encoding="utf-8")
    private = tmp_path / "fixture.env"
    private.write_text("GEMMA_BASE_URL=https://model.example/v1\nGEMMA_MODEL=labelled-fixture\n", encoding="utf-8")
    output = tmp_path / "evaluation.sqlite3"
    args = ["--source-json", str(source_file), "--output-db", str(output),
            "--provider-env", str(private), "--allow-provider-calls"]
    requests = transport(monkeypatch, tool_message(json.dumps(BUYER_SUMMARY)))
    main(args)
    first = json.loads(capsys.readouterr().out)
    main(args)
    assert json.loads(capsys.readouterr().out) == first
    assert first["valid_summary"] is True
    assert first["model_attempts"] == len(requests) == 1
    assert source_file.read_text(encoding="utf-8") == source.model_dump_json()
    private.write_text("GEMMA_BASE_URL=https://model.example/v1\nGEMMA_MODEL=changed-fixture\n", encoding="utf-8")
    with pytest.raises(ValueError, match="context changed"):
        main(args)
    assert len(requests) == 1
