"""End to end over the LABELLED SYNTHETIC world: website in, three verdicts out, every quote checked."""
from datetime import date

from shortlist.agent.models import RunResult
from shortlist.agent.pipeline import AgentRunner
from shortlist.agent.synthetic import SELLER, VAGUE, build_pages
from shortlist.relevance import quoted_in


def company(result, domain):
    return next(c for c in result.companies if c.domain == domain)


def test_website_only_run_gives_all_three_verdicts(run_result):
    assert run_result.status == "complete" and run_result.synthetic
    verdicts = {c.domain: c.verdict.kind for c in run_result.companies}
    assert verdicts == {"trailgear.example": "shortlisted", "oakandpine.example": "needs_look",
                        "brightkettle.example": "rejected"}


def test_seller_profile_is_inferred_with_quotes(run_result):
    profile = run_result.profile
    assert profile.offer.value == "Help desk software for online stores"
    assert profile.buyer.quotes[0].text == "Built for customer support teams at online retailers."
    assert [c.id for c in profile.fit_criteria] == ["fit-1", "fit-2", "fit-3"]
    assert [c.required for c in profile.fit_criteria] == [True, True, False]
    assert [s.id for s in profile.need_signals] == ["need-1", "need-2"]
    assert profile.existing_customers[0].domain == "acme-outdoor.example"
    assert profile.stated_limits[0].kind == "region"
    # Homepage plus four kinds of page and the seller's own comparison page.
    assert len(profile.pages) == 6 and any("/vs/" in page.url for page in profile.pages)
    for item in [profile.offer, profile.buyer, *profile.fit_criteria, *profile.need_signals]:
        assert item.quotes and all(q.source_type == "own_site" for q in item.quotes)


def test_every_shown_quote_is_verbatim_in_its_fetched_page(run_result):
    pages = build_pages(date(2026, 10, 29))
    for item in (e for c in run_result.companies for e in c.evidence):
        html = pages[item.quote.url].decode()
        if item.quote.location == "html":
            assert item.quote.text in html
        else:
            assert quoted_in(item.quote.text, html), item.quote.text


def test_unfound_quotes_are_dropped_and_logged(run_result):
    reasons = {(d.stage, d.claim_type) for d in run_result.dropped}
    assert ("seller", "need signal") in reasons
    assert ("competitors", "same buyer") in reasons
    assert ("investigation", "fit") in reasons
    shown = [e.quote.text for c in run_result.companies for e in c.evidence]
    assert "We ship to 40 countries worldwide." not in shown
    assert all("80 percent" not in q.text for s in run_result.profile.need_signals for q in s.quotes)


def test_competitors_need_same_job_and_same_buyer_quotes(run_result):
    kinds = {c.domain: c.classification for c in run_result.competitors}
    # ChatWidget was claimed direct, but its buyer quote is not on its page: downgraded.
    assert kinds == {"rival-desk.example": "direct", "chatwidget.example": "adjacent",
                     "metricsboard.example": "not_competitor"}
    rival = run_result.competitors[0]
    assert rival.same_job and rival.same_buyer
    rules = {r.id for r in run_result.disqualifiers}
    assert rules == {"uses_direct_competitor:rival-desk.example", "is_competitor", "is_existing_customer",
                     "outside_stated_size_or_region", "inactive"}


def test_discovery_sets_aside_lists_directories_self_competitors_and_customers(run_result):
    aside = {s.domain: s.reason for s in run_result.set_aside}
    assert set(aside) == {"acme-outdoor.example", "rival-desk.example", "seller.example",
                          "best-helpdesk-list.example", "g2.com"}
    assert "customer" in aside["acme-outdoor.example"]
    assert len({c.domain for c in run_result.companies}) == len(run_result.companies)


def test_shortlisted_company_has_fit_fresh_need_and_checked_places(run_result):
    trail = company(run_result, "trailgear.example")
    decisions = {d.evidence_id: d.decision for d in trail.decisions}
    need = next(e for e in trail.evidence if e.claim_type == "need")
    assert need.quote.source_type == "job_post" and need.quote.published_date == date(2026, 10, 8)
    assert decisions[need.id] == "supports"
    assert trail.disqualifier_check_completed
    assert trail.checked_places == ["homepage code", 'search "Trailgear Outfitters RivalDesk"', "job post"]


def test_rejected_company_shows_disqualifier_quote(run_result):
    kettle = company(run_result, "brightkettle.example")
    assert kettle.verdict.rule == "uses_direct_competitor"
    assert kettle.verdict.disqualifier.quote.text == "Customer support powered by RivalDesk"
    scanned = {e.quote.text for e in kettle.evidence if e.found_by == "scan"}
    assert "https://widget.rival-desk.example/embed.js" in scanned
    competitor_page = [e for e in kettle.evidence if e.quote.source_type == "competitor_site"]
    assert competitor_page and competitor_page[0].quote.url == "https://rival-desk.example/customers"


def test_needs_a_look_lists_what_is_missing(run_result):
    oak = company(run_result, "oakandpine.example")
    assert oak.verdict.missing == ["No supported need or timing evidence dated within 180 days"]
    decisions = {d.evidence_id: d for d in oak.decisions}
    integration = next(e for e in oak.evidence if e.claim_type == "disqualifier")
    assert decisions[integration.id].decision == "insufficient"
    own_need = next(e for e in oak.evidence if e.claim_type == "need")
    assert decisions[own_need.id].decision == "insufficient"


def test_telemetry_records_every_call(run_result):
    t = run_result.telemetry
    assert t.model_calls == len(t.calls) == 14
    assert {c.provider for c in t.calls} == {"synthetic-meta", "synthetic-baseten"}
    assert {c.operation for c in t.calls} >= {"seller_profile", "competitor_search", "competitor_classify", "discovery",
                                              "investigate", "skeptic"}
    assert all(c.input_tokens > 0 and c.output_tokens > 0 and c.latency_ms >= 0 for c in t.calls)
    assert t.searches == sum(c.searches for c in t.calls) > 0
    assert abs(t.cost_usd - sum(c.usd for c in t.calls)) < 1e-6
    assert t.pages_fetched > 0 and not t.budget_reached


def test_progress_events_cover_each_stage(run_result, events):
    assert {e.stage for e in events} >= {"run", "seller", "competitors", "discovery", "investigation", "skeptic", "verdict"}
    assert [e.seq for e in events] == list(range(1, len(events) + 1))


def test_result_round_trips_as_json(run_result):
    assert RunResult.model_validate_json(run_result.model_dump_json()) == run_result


def test_no_people_fields_anywhere():
    names = set()

    def walk(schema):
        if isinstance(schema, dict):
            names.update(schema.get("properties", {}))
            for value in schema.values():
                walk(value)
        elif isinstance(schema, list):
            for value in schema:
                walk(value)
    walk(RunResult.model_json_schema())
    assert not names & {"person", "people", "persons", "contact", "contacts", "email", "role", "linkedin"}


def test_vague_site_offers_clickable_readings_then_continues(providers):
    runner = AgentRunner(providers)
    first = runner.run(VAGUE)
    assert first.status == "needs_choice"
    readings = first.profile.interpretations
    # The third reading's quote is not on the page, so only two remain, each with a quote.
    assert [r.id for r in readings] == ["reading-1", "reading-2"] and all(r.quotes for r in readings)
    second = AgentRunner(providers).run(VAGUE, run_id=first.id, reading=readings[0])
    assert second.profile.offer.value == "Workflow automation software"
    assert second.profile.offer.origin == "interpretation" and second.profile.fit_criteria
    assert second.status == "complete"


def test_explicit_domains_skip_discovery(providers):
    result = AgentRunner(providers).run(SELLER, domains=["brightkettle.example", "trailgear.example"])
    assert [c.domain for c in result.companies] == ["brightkettle.example", "trailgear.example"]
    assert not any(c.operation == "discovery" for c in result.telemetry.calls)
