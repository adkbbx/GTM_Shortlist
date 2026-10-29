"""Skeptic rules, deterministic verdicts and the run budget, over SYNTHETIC evidence."""
import json
from datetime import UTC, date, datetime, timedelta

import pytest

from shortlist.agent.llm import AgentOutputError, Calls, extract_json
from shortlist.agent.models import (
    BUDGET_REACHED,
    CompanyResult,
    DisqualifierRule,
    EvidenceItem,
    FitCriterion,
    Quote,
    SellerProfile,
    SkepticDecision,
    Telemetry,
)
from shortlist.agent.pipeline import AgentRunner
from shortlist.agent.providers import ChatTurn
from shortlist.agent.skeptic import OWN_SITE_NEED, SkepticAnswer, judge
from shortlist.agent.synthetic import SELLER
from shortlist.agent.telemetry import BudgetReached, Meter, Pricing
from shortlist.agent.verdict import decide

TODAY = date(2026, 10, 29)
FETCHED = datetime(2026, 10, 29, 9, tzinfo=UTC)
PROFILE = SellerProfile(website="https://seller.example/", domain="seller.example", fit_criteria=[
    FitCriterion(id="fit-1", text="Sells online", required=True),
    FitCriterion(id="fit-2", text="Ships abroad", required=False)])
RULES = [DisqualifierRule(id="uses_direct_competitor:rival.example", rule="uses_direct_competitor",
                          text="Currently uses Rival", competitor_domain="rival.example"),
         DisqualifierRule(id="inactive", rule="inactive", text="No longer operating")]


def item(claim_type, criterion, text="SYNTHETIC quote text for a check", source="own_site", published=None, **extra):
    return EvidenceItem(claim_type=claim_type, criterion_id=criterion, claim="SYNTHETIC claim",
                        quote=Quote(text=text, url="https://shop.example/", source_type=source,
                                    published_date=published, fetched_at=FETCHED), **extra)


def company(evidence, decisions=None, **extra):
    values = {"domain": "shop.example", "url": "https://shop.example/", "status": "done", "evidence": evidence,
              "checked_places": ["homepage code", 'search "Shop Rival"'], "disqualifier_check_completed": True}
    values.update(extra)
    result = CompanyResult(**values)
    result.decisions = decisions if decisions is not None else [
        SkepticDecision(evidence_id=e.id, decision="supports", decided_by="skeptic") for e in evidence]
    return result


def test_shortlisted_needs_fit_fresh_signal_and_completed_check():
    fit = item("fit", "fit-1")
    need = item("need", "need-1", source="job_post", published=TODAY - timedelta(days=30))
    assert decide(company([fit, need]), PROFILE, RULES, TODAY).kind == "shortlisted"
    stale = item("need", "need-1", source="job_post", published=TODAY - timedelta(days=181))
    verdict = decide(company([fit, stale]), PROFILE, RULES, TODAY)
    assert verdict.kind == "needs_look"
    assert verdict.missing == ["Need or timing evidence found, but none current (dated within 180 days or an open job post)"]
    undone = decide(company([fit, need], disqualifier_check_completed=False), PROFILE, RULES, TODAY)
    assert undone.missing == ["Competitor check incomplete: no search for current competitor use was run"]
    unchecked = decide(company([fit, need], checked_places=[], disqualifier_check_completed=False), PROFILE, RULES, TODAY)
    assert unchecked.missing == ["Competitor check not run"]


def test_missing_required_fit_and_blocked_pages_are_listed():
    need = item("need", "need-1", source="news", published=TODAY)
    verdict = decide(company([need], blocked=["https://shop.example/careers: Website returned HTTP 403"]),
                     PROFILE, RULES, TODAY)
    assert verdict.kind == "needs_look"
    assert verdict.missing == ["Fit not shown: Sells online",
                               "Could not read https://shop.example/careers: Website returned HTTP 403"]


def test_supported_disqualifier_rejects_with_its_quote():
    fit = item("fit", "fit-1")
    need = item("need", "need-1", source="job_post", published=TODAY)
    uses = item("disqualifier", "uses_direct_competitor:rival.example", text="Support powered by Rival", found_by="scan")
    verdict = decide(company([fit, need, uses]), PROFILE, RULES, TODAY)
    assert verdict.kind == "rejected" and verdict.rule == "uses_direct_competitor"
    assert verdict.disqualifier.quote.text == "Support powered by Rival"
    doubted = company([fit, need, uses], decisions=[
        SkepticDecision(evidence_id=fit.id, decision="supports", decided_by="skeptic"),
        SkepticDecision(evidence_id=need.id, decision="supports", decided_by="skeptic"),
        SkepticDecision(evidence_id=uses.id, decision="insufficient", decided_by="skeptic")])
    assert decide(doubted, PROFILE, RULES, TODAY).kind == "shortlisted"
    disabled = [rule.model_copy(update={"enabled": False}) for rule in RULES]
    assert decide(company([fit, need, uses]), PROFILE, disabled, TODAY).kind == "shortlisted"


def test_user_exclusions_and_budget():
    fit = item("fit", "fit-1")
    assert decide(company([fit]), PROFILE, RULES, TODAY, ["shop.example"]).summary == "Excluded by you (shop.example)"
    verdict = decide(company([], status="budget_reached", checked_places=[]), PROFILE, RULES, TODAY)
    assert verdict.kind == "needs_look" and verdict.missing[0] == BUDGET_REACHED == "Needs a look: budget reached"


class ScriptedSkeptic:
    provider, model = "scripted-test", "scripted-test"
    pricing = Pricing(1.25, 4.25)

    def __init__(self, answers):
        self.answers = list(answers)
        self.messages = []

    def chat(self, messages, *, max_tokens=2000):
        self.messages.append(messages)
        return ChatTurn(text=self.answers.pop(0), input_tokens=10, output_tokens=5)


def calls_with(skeptic, budget=1.0):
    return Calls(Meter(Telemetry(budget_usd=budget)), investigator=None, skeptic=skeptic)


def test_skeptic_sees_only_quote_check_source_and_dates():
    need = item("need", "need-1", source="job_post", published=TODAY)
    target = company([need])
    skeptic = ScriptedSkeptic([json.dumps({"decisions": [{"id": need.id, "decision": "supports", "reason": "ok"}]})])
    judge(target, PROFILE, RULES, calls_with(skeptic), use_skeptic=True)
    sent = json.loads(skeptic.messages[0][1]["content"].split("<data>\n")[1].split("\n</data>")[0])["items"][0]
    assert set(sent) == {"id", "claim_type", "check", "quote", "quote_location", "source_type", "published_date",
                         "fetched_at"}
    assert "shop.example" not in json.dumps(sent)


def test_own_site_never_supports_need_even_if_the_skeptic_says_so():
    need = item("need", "need-1", source="own_site")
    skeptic = ScriptedSkeptic([json.dumps({"decisions": [{"id": need.id, "decision": "supports", "reason": "x"}]})])
    decision = judge(company([need]), PROFILE, RULES, calls_with(skeptic), use_skeptic=True)[0]
    assert decision.decision == "insufficient" and decision.reason == OWN_SITE_NEED and decision.decided_by == "rule"
    # The rule also holds in the no-skeptic ablation.
    assert judge(company([need]), PROFILE, RULES, None, use_skeptic=False)[0].decision == "insufficient"


def test_skeptic_json_is_strict_with_one_repair():
    fit = item("fit", "fit-1")
    good = json.dumps({"decisions": [{"id": fit.id, "decision": "supports", "reason": "ok"}]})
    extra = json.dumps({"decisions": [{"id": fit.id, "decision": "supports", "reason": "ok", "confidence": 0.9}]})
    skeptic = ScriptedSkeptic([extra, good])
    calls = calls_with(skeptic)
    assert judge(company([fit]), PROFILE, RULES, calls, use_skeptic=True)[0].decision == "supports"
    assert len(skeptic.messages) == 2 and "confidence" in skeptic.messages[1][-1]["content"]
    assert [c.operation for c in calls.meter.telemetry.calls] == ["skeptic", "skeptic:repair"]
    with pytest.raises(AgentOutputError):
        calls_with(ScriptedSkeptic(["not json", "still not json"])).skeptic_json("skeptic", SkepticAnswer, [])
    failed = judge(company([fit]), PROFILE, RULES, calls_with(ScriptedSkeptic(["nope", "nope"])), use_skeptic=True)
    assert failed[0].decision == "insufficient" and failed[0].reason.startswith("Skeptic unavailable")


def test_missing_decision_is_insufficient_and_ablation_accepts():
    fit = item("fit", "fit-1")
    skeptic = ScriptedSkeptic([json.dumps({"decisions": []})])
    assert judge(company([fit]), PROFILE, RULES, calls_with(skeptic), use_skeptic=True)[0].decision == "insufficient"
    ablated = judge(company([fit]), PROFILE, RULES, None, use_skeptic=False)[0]
    assert (ablated.decision, ablated.decided_by) == ("supports", "no_skeptic")


def test_extract_json_handles_fences_and_prose():
    assert extract_json('Here:\n```json\n{"a": {"b": "}"}}\n```') == {"a": {"b": "}"}}
    assert extract_json('noise {"a": 1} trailing') == {"a": 1}
    with pytest.raises(ValueError):
        extract_json("no object")


def test_meter_blocks_calls_once_the_budget_is_spent():
    meter = Meter(Telemetry(budget_usd=0.01))
    meter.check()
    from shortlist.agent.models import ModelCall
    meter.record(ModelCall(provider="p", model="m", operation="o", usd=0.02))
    with pytest.raises(BudgetReached):
        meter.check()
    assert meter.telemetry.budget_reached


def test_budget_stops_new_calls_and_marks_remaining_companies(providers):
    result = AgentRunner(providers, budget_usd=0.012, concurrency=1).run(SELLER)
    t = result.telemetry
    assert t.budget_reached and result.status == "complete"
    # The call that crossed the line finished; none started after it.
    crossed = next(i for i, _ in enumerate(t.calls) if sum(c.usd for c in t.calls[:i + 1]) >= 0.012)
    assert len(t.calls) == crossed + 1
    stopped = [c for c in result.companies if c.status == "budget_reached"]
    assert stopped and all(c.verdict.kind == "needs_look" and BUDGET_REACHED in c.verdict.missing for c in stopped)
