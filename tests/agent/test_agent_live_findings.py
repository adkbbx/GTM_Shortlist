"""Fixes for problems the first live run exposed (docs/PROGRESS.md, 30 October), over the SYNTHETIC providers."""
from shortlist.agent import synthetic
from shortlist.agent.discovery import SEARCH_RESULT_PAGE, admit
from shortlist.agent.pipeline import AgentRunner
from shortlist.agent.seller import private_signal
from shortlist.agent.synthetic import SELLER

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


def test_budget_reached_during_discovery_keeps_the_companies_already_found(providers):
    result = AgentRunner(providers, budget_usd=0.012, concurrency=1).run(SELLER)
    assert result.telemetry.budget_reached and {c.domain for c in result.companies} >= {"trailgear.example"}
    assert all(c.status == "budget_reached" for c in result.companies)
