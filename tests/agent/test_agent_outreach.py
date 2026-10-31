"""Why now and an opening line for Shortlisted companies, over the LABELLED SYNTHETIC providers."""
import json

from shortlist.agent.llm import Calls
from shortlist.agent.models import Telemetry
from shortlist.agent.outreach import CHECK, write_pitch
from shortlist.agent.providers import ChatTurn
from shortlist.agent.telemetry import Meter


def shortlisted(run_result):
    return [c for c in run_result.companies if c.verdict.kind == "shortlisted"]


def test_only_shortlisted_companies_get_a_checked_pitch_built_from_supported_quotes(run_result):
    assert shortlisted(run_result)
    for company in run_result.companies:
        if company.verdict.kind != "shortlisted":
            assert company.pitch is None
            continue
        pitch = company.pitch
        assert pitch.checked and pitch.why_now and pitch.opener
        supported = {d.evidence_id for d in company.decisions if d.decision == "supports"}
        assert set(pitch.evidence_ids) <= supported
        used = [e for e in company.evidence if e.id in pitch.evidence_ids]
        assert any(e.claim_type in ("need", "timing") for e in used)
        assert any(e.quote.text[:40] in pitch.why_now for e in used)


class Doubter:
    """A skeptic that finds the note claims more than its quotes. SYNTHETIC."""
    provider, model = "synthetic-baseten", "synthetic-doubter"

    def __init__(self, inner):
        self.inner = inner
        self.pricing = inner.pricing

    def chat(self, messages, *, max_tokens=2000):
        if messages[0]["content"] == CHECK:
            return ChatTurn(text=json.dumps({"decision": "unsupported", "reason": "Adds a funding round."}),
                            input_tokens=10, output_tokens=10, latency_ms=1)
        return self.inner.chat(messages, max_tokens=max_tokens)


def test_a_pitch_the_skeptic_cannot_support_is_dropped_and_logged(providers, run_result):
    company = shortlisted(run_result)[0].model_copy(update={"pitch": None})
    calls = Calls(Meter(Telemetry(budget_usd=1.0)), providers.investigator, Doubter(providers.skeptic))
    dropped = []
    assert write_pitch(company, run_result.profile, calls, use_skeptic=True, dropped=dropped) is None
    assert dropped and dropped[0].stage == "pitch" and "funding round" in dropped[0].reason


def test_no_current_need_means_no_pitch(providers, run_result):
    company = shortlisted(run_result)[0]
    fit_only = company.model_copy(update={"evidence": [e for e in company.evidence if e.claim_type == "fit"]})
    calls = Calls(Meter(Telemetry(budget_usd=1.0)), providers.investigator, providers.skeptic)
    assert write_pitch(fit_only, run_result.profile, calls, use_skeptic=True, dropped=[]) is None
    assert calls.meter.telemetry.model_calls == 0  # nothing to say, nothing spent
