"""Fixes for problems the first live run exposed (docs/PROGRESS.md, 30 October), over the SYNTHETIC providers."""
import json
from datetime import UTC, date, datetime, timedelta
from urllib.parse import urlsplit

import pytest

from shortlist.agent import synthetic
from shortlist.agent.discovery import DISCOVERY_INSTRUCTIONS, SEARCH_RESULT_PAGE, admit
from shortlist.agent.investigation import INSTRUCTIONS as INVESTIGATE_INSTRUCTIONS
from shortlist.agent.llm import extract_json
from shortlist.agent.models import EvidenceItem, Overrides, Quote
from shortlist.agent.pages import Page, open_posting
from shortlist.agent.pipeline import AgentRunner
from shortlist.agent.seller import private_signal
from shortlist.agent.service import AgentService
from shortlist.agent.settings import AgentSettings
from shortlist.agent.storage import SQLiteAgentRuns
from shortlist.agent.synthetic import SELLER, synthetic_providers
from shortlist.agent.verdict import fresh
from shortlist.domain import Source, utcnow
from shortlist.fetch import FetchError

# Need and timing signals the live seller profile produced: internal states no public quote can show.
LIVE_PRIVATE = [
    "Company is hiring SDRs to add outreach capacity before its outbound motion is proven",
    "Company is spending on growth but does not know what is actually working",
    "Company is changing ICP, offer, message or channel at the same time without isolating variables",
    "Company lacks a repeatable playbook and decision on which customer, message, offer and channel to scale",
    "Company wants to scale acquisition but is not confident the system is ready",
]
OBSERVABLE = [
    "Hiring SDRs or outbound sales reps",
    "Hiring customer support agents",
    "Answers support from a shared email inbox or spreadsheets",
    "Announced plans to expand into Europe",
    "Recently opened a new store or product line",
    "Raised a new funding round",
]


def test_private_states_are_told_apart_from_observable_signals():
    assert all(private_signal(text) for text in LIVE_PRIVATE)
    assert not any(private_signal(text) for text in OBSERVABLE)


def test_a_private_need_signal_is_dropped_and_logged(providers, monkeypatch):
    needs = synthetic.SELLER_ANSWER["need_signals"] + [{
        "id": "need-3", "text": "Company does not know which support channel actually works",
        "quotes": [synthetic._quote("Built for customer support teams at online retailers.", SELLER)]}]
    monkeypatch.setitem(synthetic.SELLER_ANSWER, "need_signals", needs)
    result = AgentRunner(providers).run(SELLER)
    assert [signal.id for signal in result.profile.need_signals] == ["need-1", "need-2"]
    dropped = [item for item in result.dropped if item.claim_type == "need signal" and "internal state" in item.reason]
    assert [item.quote for item in dropped] == ["Company does not know which support channel actually works"]


def test_search_results_must_be_a_companys_own_page():
    excluded = {"seller.example": "This is your own website"}
    # A dated news path passes the page-type checks on its own, which is how publishers became candidates live.
    article = "https://business-news.example/2026/10/acme-expands-outbound-team"
    assert admit(article, "Acme expands outbound team", 'search "acme"', excluded, "seller.example")[0] is not None
    ref, aside = admit(article, "Acme expands outbound team", 'search "acme"', excluded, "seller.example", own_page=True)
    assert ref is None and aside.domain == "business-news.example" and aside.reason == SEARCH_RESULT_PAGE
    for url in ("https://acme.example/", "https://acme.example/pricing", "https://acme.example/en/about"):
        ref, aside = admit(url, "Acme", 'search "acme"', excluded, "seller.example", own_page=True)
        assert ref is not None and ref.url == "https://acme.example/" and aside is None
    # A company the model named is still admitted from any page of its own site; research starts at the homepage.
    ref, _ = admit("https://acme.example/customers/stories/2026-launch", "Acme", "named", excluded, "seller.example")
    assert ref is not None and ref.url == "https://acme.example/"


def test_discovery_searches_by_signal_and_research_follows_the_lead(providers, monkeypatch):
    """Third live run: category searches returned the largest brands. Discovery now gets the need and timing signals,
    and each company's research brief carries how it was found."""
    seen = []
    respond = providers.investigator.respond

    def recording(**kwargs):
        seen.append((kwargs["instructions"], json.dumps(kwargs["input"])))
        return respond(**kwargs)

    monkeypatch.setattr(providers.investigator, "respond", recording)
    AgentRunner(providers).run(SELLER)
    discovery = next(text for instructions, text in seen if instructions == DISCOVERY_INSTRUCTIONS)
    assert "Hiring customer support agents" in discovery and "household-name" in DISCOVERY_INSTRUCTIONS
    brief = next(text for instructions, text in seen if instructions == INVESTIGATE_INSTRUCTIONS and "trailgear" in text)
    assert "found_via" in brief and "online stores with email and chat support" in brief


def posting(url: str, text: str, published=None, fetched=datetime(2026, 10, 30, 1, tzinfo=UTC)) -> tuple[Page, EvidenceItem]:
    page = Page(source=Source(url=url, company_domain=url.split("/")[2], title="Job", text=text,
                              content_hash="synthetic", retrieved_at=fetched), html="<html></html>", full_text=text)
    quote = Quote(text=text[:40], url=url, source_type="job_post", published_date=published, fetched_at=fetched,
                  open_posting=open_posting(page))
    return page, EvidenceItem(claim_type="need", criterion_id="need-1", claim="Hiring SDRs", quote=quote)


def test_an_open_ats_job_post_counts_as_current_without_a_stated_date():
    """Fourth live run: SciLeads' SDR posting on Greenhouse had no date, so a strong prospect stayed at Needs a look."""
    today = date(2026, 10, 30)
    _, live = posting("https://job-boards.eu.greenhouse.io/scileads/jobs/4988676101",
                      "Job Application for Sales Development Representative at SciLeads")
    assert live.quote.open_posting and fresh(live, today)
    _, closed = posting("https://jobs.lever.co/acme/123", "This job is no longer accepting applications. SDR at Acme")
    assert not closed.quote.open_posting and not fresh(closed, today)
    _, aggregator = posting("https://www.indeed.com/viewjob?jk=1", "Sales Development Representative at Acme")
    assert not aggregator.quote.open_posting and not fresh(aggregator, today)
    _, stale_read = posting("https://boards.greenhouse.io/acme/jobs/1", "SDR at Acme",
                            fetched=datetime(2026, 10, 20, tzinfo=UTC))
    assert not fresh(stale_read, today)  # open when read 10 days ago says nothing about today
    _, dated = posting("https://acme.example/careers/sdr", "SDR at Acme", published=date(2026, 9, 1))
    assert not dated.quote.open_posting and fresh(dated, today)
    # Fifth live run: Greenhouse sends a closed posting's link to the company board with ?error=true.
    _, board = posting("https://job-boards.greenhouse.io/acme?error=true", "Sales Development Representative")
    _, root = posting("https://job-boards.greenhouse.io/acme", "Sales Development Representative")
    assert not board.quote.open_posting and not root.quote.open_posting


def test_at_most_two_fit_checks_are_required(providers, monkeypatch):
    """Fifth live run: "sells via meetings, demos or sales conversations" was required and held back a company with
    a dated SDR job post. Only the first two required checks stay required; the rest become nice to have."""
    fits = [dict(item, required=True) for item in synthetic.SELLER_ANSWER["fit_criteria"]]
    monkeypatch.setitem(synthetic.SELLER_ANSWER, "fit_criteria", fits)
    profile = AgentRunner(providers).run(SELLER).profile
    assert [c.required for c in profile.fit_criteria] == [True, True, False]


def test_an_unreadable_homepage_is_set_aside_and_the_next_candidate_researched(providers):
    """Sixth live run: two of three homepages redirected to another domain, so two slots held nothing."""
    fetch = providers.fetcher

    def fetcher(url, expected_domain=None):
        if url.startswith("https://trailgear.example/") and urlsplit(url).path in ("", "/"):
            raise FetchError("Redirect changed company identity; manual verification required")
        return fetch(url, expected_domain)

    providers.fetcher = fetcher
    result = AgentRunner(providers).run(SELLER, Overrides(company_count=2))
    assert [c.domain for c in result.companies] == ["oakandpine.example", "brightkettle.example"]
    aside = next(a for a in result.set_aside if a.domain == "trailgear.example")
    assert aside.reason == "Website could not be read: Redirect changed company identity; manual verification required"
    assert all(c.error is None for c in result.companies)


def test_a_competitor_whose_site_cannot_be_read_stays_listed_as_unverified(providers):
    """Vanta run: drata.com answered HTTP 403 and disappeared from the competitor list."""
    fetch = providers.fetcher

    def fetcher(url, expected_domain=None):
        if url == "https://metricsboard.example/":
            raise FetchError("Website returned HTTP 403")
        return fetch(url, expected_domain)

    providers.fetcher = fetcher
    result = AgentRunner(providers).run(SELLER)
    blocked = next(c for c in result.competitors if c.domain == "metricsboard.example")
    assert blocked.classification == "adjacent" and blocked.same_job is None
    assert blocked.reason.startswith("Not verified: its site could not be read (Website returned HTTP 403)")
    assert all("metricsboard" not in rule.id for rule in result.disqualifiers)
    assert all(c.domain != "metricsboard.example" for c in result.companies)


def test_a_profile_without_signals_is_asked_once_more(providers, monkeypatch):
    """Crisp run: the seller profile came back with no need or timing signal, so nothing could be Shortlisted."""
    original = synthetic.SELLER_ANSWER["need_signals"]
    monkeypatch.setitem(synthetic.SELLER_ANSWER, "need_signals", [])
    monkeypatch.setitem(synthetic.SELLER_ANSWER, "timing_signals", [])
    respond = providers.investigator.respond

    def answering_on_retry(**kwargs):
        if "had no need_signals" in json.dumps(kwargs["input"]):
            synthetic.SELLER_ANSWER["need_signals"] = original  # restored by monkeypatch after the test
        return respond(**kwargs)

    monkeypatch.setattr(providers.investigator, "respond", answering_on_retry)
    result = AgentRunner(providers).run(SELLER)
    assert [s.id for s in result.profile.need_signals] == ["need-1", "need-2"]
    assert [c.operation for c in result.telemetry.calls].count("seller_profile:signals") == 1


def test_target_size_guides_discovery_and_rejects_clearly_bigger_companies(providers, monkeypatch):
    """30 Oct: for a startup agency the agent researched HubSpot and Salesforce. The profile now always carries a
    target size; discovery aims at it, and a size rule rejects a company only when a quote shows it is bigger."""
    seen = []
    respond = providers.investigator.respond

    def recording(**kwargs):
        seen.append((kwargs["instructions"], json.dumps(kwargs["input"])))
        return respond(**kwargs)

    monkeypatch.setattr(providers.investigator, "respond", recording)
    runner = AgentRunner(providers)
    result = runner.run(SELLER)
    assert result.profile.target_size.value == "Small and mid-sized online stores, about 5 to 200 people"
    rule = next(r for r in result.disqualifiers if r.id == "outside_target_size")
    assert rule.rule == "outside_stated_size_or_region" and "about 5 to 200 people" in rule.text
    discovery = next(text for instructions, text in seen if instructions == DISCOVERY_INSTRUCTIONS)
    assert "about 5 to 200 people" in discovery
    brief = next(text for instructions, text in seen if instructions == INVESTIGATE_INSTRUCTIONS)
    assert "outside_target_size" in brief  # the investigator looks for size evidence too

    # Your own size replaces the inferred one and re-judges only that rule's saved quotes.
    changed = runner.reevaluate(result, Overrides(target_size="Seed to Series A startups, 5 to 50 people"))
    assert changed.profile.target_size.origin == "user"
    assert "5 to 50 people" in next(r.text for r in changed.disqualifiers if r.id == "outside_target_size")


def test_an_any_size_target_makes_no_rule_and_the_cli_can_set_the_size(providers, monkeypatch, tmp_path, capsys):
    """Live run, 30 Oct: eygentic.com says it serves "B2B and SaaS companies of any size or stage"."""
    any_size = {"value": "Companies of any size or stage, from early startups to larger teams",
                "quotes": synthetic.SELLER_ANSWER["target_size"]["quotes"]}
    monkeypatch.setitem(synthetic.SELLER_ANSWER, "target_size", any_size)
    assert "outside_target_size" not in {r.id for r in AgentRunner(providers).run(SELLER).disqualifiers}

    from shortlist.agent import cli
    output = tmp_path / "run.json"
    assert cli.main(["run", "seller.example", "--synthetic", "--no-save", "--target-size",
                     "Seed to Series A startups, 5 to 50 people", "--output", str(output)]) == 0
    run = json.loads(output.read_text(encoding="utf-8"))
    assert run["profile"]["target_size"] == {"value": "Seed to Series A startups, 5 to 50 people", "quotes": [],
                                             "origin": "user"}
    assert any(r["id"] == "outside_target_size" and "5 to 50 people" in r["text"] for r in run["disqualifiers"])


def test_a_stated_size_replaces_the_inferred_size_rule(providers, monkeypatch):
    limits = synthetic.SELLER_ANSWER["stated_limits"] + [{"kind": "size", "value": "teams of 10 to 100 agents", "quotes": [
        synthetic._quote("Northwind Desk serves online retailers in North America and Europe.",
                         "https://seller.example/pricing")]}]
    monkeypatch.setitem(synthetic.SELLER_ANSWER, "stated_limits", limits)
    rules = {r.id for r in AgentRunner(providers).run(SELLER).disqualifiers}
    assert "outside_stated_size_or_region" in rules and "outside_target_size" not in rules


def test_a_company_researched_earlier_for_the_same_seller_is_set_aside(tmp_path):
    """Chili Piper and Kovai.co were researched and paid for in several runs on 30 Oct."""
    service = AgentService(SQLiteAgentRuns(tmp_path / "runs.sqlite3"), lambda: AgentSettings(),
                           lambda settings: synthetic_providers(date(2026, 10, 30)))
    first = service.start("seller.example")
    service.wait(first.id, 20)
    researched = {c.domain for c in service.store.get(first.id)["result"].companies}
    assert researched == {"trailgear.example", "oakandpine.example", "brightkettle.example"}

    second = service.start("seller.example")
    service.wait(second.id, 20)
    again = service.store.get(second.id)["result"]
    assert again.companies == []
    earlier = {a.domain: a for a in again.set_aside if a.previous_run}
    assert set(earlier) == researched and all(a.previous_run == first.id for a in earlier.values())
    assert earlier["trailgear.example"].reason.startswith("Already researched for you on ")
    assert earlier["trailgear.example"].reason.endswith(": Shortlisted")

    # Another seller has its own history, and the public demo keeps none at all.
    assert service.store.researched("other.example", utcnow() - timedelta(days=30)) == {}
    assert AgentService(service.store, history_days=None).history("https://seller.example/") == {}


def test_budget_reached_during_discovery_keeps_the_companies_already_found(providers):
    result = AgentRunner(providers, budget_usd=0.012, concurrency=1).run(SELLER)
    assert result.telemetry.budget_reached and {c.domain for c in result.companies} >= {"trailgear.example"}
    assert all(c.status == "budget_reached" for c in result.companies)


def test_unescaped_quotation_marks_inside_a_quote_still_parse():
    """31 October, deployed demo: the seller profile stopped at "Expecting ',' delimiter" twice. The answer below is
    SYNTHETIC, shaped like a verbatim quote that copied the page's own quotation marks."""
    answer = '{"offer": {"text": "We test "one variable at a time" for founders", "n": [1]}}'
    assert extract_json(answer) == {"offer": {"text": 'We test "one variable at a time" for founders', "n": [1]}}
    valid = {"a": 'say "hi"', "b": ["x", {"c": "}"}], "d": ""}
    assert extract_json("Here it is:\n" + json.dumps(valid) + "\ntrailing") == valid
    with pytest.raises(ValueError):  # a stray mark right before a delimiter still looks like the end: model repair
        extract_json('{"quote": "No "growth hacks", ever"}')
