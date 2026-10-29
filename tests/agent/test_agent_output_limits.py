"""Reasoning effort and answers cut off at the output limit. Found in the first live run: Muse Spark's reasoning
tokens count toward max_output_tokens, so a long JSON answer stopped at exactly 4000 tokens and could not be repaired
from its own text. Response bodies here are SYNTHETIC, shaped like the documented Responses usage fields."""
import json

import httpx
import pytest
from pydantic import ValidationError

from shortlist.agent.llm import MAX_OUTPUT_TOKENS, Calls
from shortlist.agent.models import Telemetry
from shortlist.agent.providers import FunctionCall, MetaInvestigator, ModelTurn
from shortlist.agent.settings import AgentSettings
from shortlist.agent.telemetry import Meter, Pricing

KEY = "labelled-test-key-not-real"
BODY = {"id": "resp_synthetic", "status": "completed",
        "output": [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "{}"}]}],
        "usage": {"input_tokens": 10, "output_tokens": 50, "output_tokens_details": {"reasoning_tokens": 40}}}


class Scripted:
    """A LABELLED SYNTHETIC investigator that returns fixed turns and remembers each output limit it was given."""
    provider, model, continuation = "meta", "muse-spark-1.3", "replay"
    pricing = Pricing(1.25, 4.25, 0.0025)

    def __init__(self, *turns: ModelTurn):
        self.turns, self.limits = list(turns), []

    def respond(self, *, instructions, input, tools, previous_response_id=None, max_output_tokens=4000):
        self.limits.append(max_output_tokens)
        return self.turns.pop(0)


def calls(model):
    meter = Meter(Telemetry(budget_usd=1.0))
    return Calls(meter, model), meter


def test_reasoning_effort_is_sent_and_reasoning_tokens_are_read(monkeypatch):
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=BODY)

    transport = httpx.MockTransport(handler)
    turn = MetaInvestigator(AgentSettings(meta_api_key=KEY), transport=transport).respond(
        instructions="x", input=[], tools=[])
    assert seen[0]["reasoning"] == {"effort": "low"} and turn.reasoning_tokens == 40 and turn.output_tokens == 50
    MetaInvestigator(AgentSettings(meta_api_key=KEY, meta_reasoning_effort=None), transport=transport).respond(
        instructions="x", input=[], tools=[])
    assert "reasoning" not in seen[1]

    monkeypatch.setattr("shortlist.agent.settings.load_dotenv", lambda: None)
    monkeypatch.delenv("META_REASONING_EFFORT", raising=False)
    assert AgentSettings.load().meta_reasoning_effort == "low"
    monkeypatch.setenv("META_REASONING_EFFORT", "default")
    assert AgentSettings.load().meta_reasoning_effort is None
    monkeypatch.setenv("META_REASONING_EFFORT", " High ")
    assert AgentSettings.load().meta_reasoning_effort == "high"
    monkeypatch.setenv("META_REASONING_EFFORT", "none")  # Muse Spark answers HTTP 400 to "none"
    with pytest.raises(ValidationError):
        AgentSettings.load()


def test_a_cut_off_answer_is_asked_again_with_twice_the_room():
    model = Scripted(ModelTurn(text='{"offer": {"value": "Outb', output_tokens=4000),
                     ModelTurn(text='{"offer": {"value": "Outbound"}}', output_tokens=1800))
    runner, meter = calls(model)
    turn = runner.respond("seller_profile", instructions="x", input=[], max_output_tokens=4000)
    assert turn.text == '{"offer": {"value": "Outbound"}}' and model.limits == [4000, 8000]
    assert [call.operation for call in meter.telemetry.calls] == ["seller_profile", "seller_profile:longer"]

    incomplete = Scripted(ModelTurn(text="{", output_tokens=900, incomplete=True), ModelTurn(text="{}", output_tokens=20))
    calls(incomplete)[0].respond("discovery", instructions="x", input=[], max_output_tokens=3000)
    assert incomplete.limits == [3000, 6000]


def test_tool_calls_complete_answers_and_the_ceiling_are_not_retried():
    tool_turn = Scripted(ModelTurn(output_tokens=4000, function_calls=(FunctionCall("call_1", "fetch_page", "{}"),)))
    calls(tool_turn)[0].respond("investigate", instructions="x", input=[], max_output_tokens=4000)
    complete = Scripted(ModelTurn(text="{}", output_tokens=3999))
    calls(complete)[0].respond("seller_profile", instructions="x", input=[], max_output_tokens=4000)
    ceiling = Scripted(ModelTurn(text="{", output_tokens=MAX_OUTPUT_TOKENS, incomplete=True))
    calls(ceiling)[0].respond("seller_profile", instructions="x", input=[], max_output_tokens=MAX_OUTPUT_TOKENS)
    assert tool_turn.limits == [4000] and complete.limits == [4000] and ceiling.limits == [MAX_OUTPUT_TOKENS]
