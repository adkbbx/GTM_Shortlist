"""Fixes for problems the first live run exposed (docs/PROGRESS.md, 30 October), over the SYNTHETIC providers."""
import json
from datetime import UTC, date, datetime
from urllib.parse import urlsplit

from shortlist.agent import synthetic
from shortlist.agent.discovery import DISCOVERY_INSTRUCTIONS, SEARCH_RESULT_PAGE, admit
from shortlist.agent.investigation import INSTRUCTIONS as INVESTIGATE_INSTRUCTIONS
from shortlist.agent.models import EvidenceItem, Overrides, Quote
from shortlist.agent.pages import Page, open_posting
from shortlist.agent.pipeline import AgentRunner
from shortlist.agent.seller import private_signal
from shortlist.agent.synthetic import SELLER
from shortlist.agent.verdict import fresh
from shortlist.domain import Source
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


def test_budget_reached_during_discovery_keeps_the_companies_already_found(providers):
    result = AgentRunner(providers, budget_usd=0.012, concurrency=1).run(SELLER)
    assert result.telemetry.budget_reached and {c.domain for c in result.companies} >= {"trailgear.example"}
    assert all(c.status == "budget_reached" for c in result.companies)
