"""Optional corrections re-evaluate saved evidence without re-researching, over the SYNTHETIC world."""
from shortlist.agent.assumptions import merge
from shortlist.agent.models import CriterionOverride, Overrides
from shortlist.agent.pipeline import AgentRunner


def verdicts(result):
    return {c.domain: c.verdict.kind for c in result.companies}


def investigate_calls(result):
    return sum(c.operation.startswith("investigate") for c in result.telemetry.calls)


def test_removing_the_competitor_unblocks_the_rejected_company(providers, run_result):
    before = investigate_calls(run_result)
    after = AgentRunner(providers).reevaluate(run_result, Overrides(remove_competitors=["rival-desk.example"]))
    assert verdicts(after)["brightkettle.example"] == "needs_look"  # No dated need; no longer rejected.
    assert all(not e.criterion_id.startswith("uses_direct_competitor") for c in after.companies for e in c.evidence)
    assert investigate_calls(after) == before  # No new research.
    assert after.overrides.remove_competitors == ["rival-desk.example"]


def test_adding_a_competitor_rescans_saved_page_code(providers, run_result):
    run_result.competitors = [c for c in run_result.competitors if c.domain != "rival-desk.example"]
    from shortlist.agent.competitors import disqualifier_rules
    run_result.disqualifiers = disqualifier_rules(run_result.profile, run_result.competitors)
    for company in run_result.companies:
        company.evidence = [e for e in company.evidence if not e.criterion_id.startswith("uses_direct")]
    skeptic_calls = sum(c.operation == "skeptic" for c in run_result.telemetry.calls)
    after = AgentRunner(providers).reevaluate(run_result, Overrides(add_competitors=["rival-desk.example"]))
    kettle = next(c for c in after.companies if c.domain == "brightkettle.example")
    assert kettle.verdict.kind == "rejected"
    assert kettle.verdict.disqualifier.found_by == "scan"
    assert any("rescanned for" in place for place in kettle.checked_places)
    assert sum(c.operation == "skeptic" for c in after.telemetry.calls) > skeptic_calls


def test_disabling_a_criterion_and_excluding_a_company(providers, run_result):
    after = AgentRunner(providers).reevaluate(run_result, Overrides(
        criteria=[CriterionOverride(id="fit-2", enabled=False)], exclusions=["trailgear.example"]))
    assert verdicts(after)["trailgear.example"] == "rejected"
    assert next(c for c in after.companies if c.domain == "trailgear.example").verdict.summary.startswith("Excluded by you")
    assert next(c for c in after.profile.fit_criteria if c.id == "fit-2").enabled is False


def test_editing_criterion_text_rejudges_only_those_quotes(providers, run_result):
    before = len(run_result.telemetry.calls)
    after = AgentRunner(providers).reevaluate(run_result, Overrides(
        criteria=[CriterionOverride(id="fit-1", text="Sells its own products through an online store")]))
    assert next(c for c in after.profile.fit_criteria if c.id == "fit-1").text.startswith("Sells its own")
    new_calls = after.telemetry.calls[before:]
    assert new_calls and {c.operation for c in new_calls} == {"skeptic"}


def test_adding_a_criterion_researches_again(providers, run_result):
    before = investigate_calls(run_result)
    after = AgentRunner(providers).reevaluate(run_result, Overrides(
        criteria=[CriterionOverride(id="fit-9", text="Has a returns policy page", required=False)]))
    assert investigate_calls(after) > before
    assert any(c.id == "fit-9" and c.origin == "user" for c in after.profile.fit_criteria)


def test_raising_the_count_uses_saved_candidates_only(providers, run_result):
    discovery = sum(c.operation == "discovery" for c in run_result.telemetry.calls)
    after = AgentRunner(providers).reevaluate(run_result, Overrides(company_count=12))
    assert after.company_count == 12
    assert sum(c.operation == "discovery" for c in after.telemetry.calls) == discovery


def test_merge_keeps_latest_choice():
    first = Overrides(add_competitors=["a.example"], criteria=[CriterionOverride(id="fit-1", required=False)])
    second = Overrides(remove_competitors=["a.example"], criteria=[CriterionOverride(id="fit-1", text="New wording")])
    merged = merge(first, second)
    assert merged.add_competitors == [] and merged.remove_competitors == ["a.example"]
    assert merged.criteria[0].required is False and merged.criteria[0].text == "New wording"
