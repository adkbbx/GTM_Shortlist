"""Grounding, source types, dates, page choice and the model-free competitor scan. Pages are SYNTHETIC."""
from datetime import UTC, date, datetime

from shortlist.agent.models import Competitor
from shortlist.agent.pages import (
    fetch_document,
    ground,
    page_from_document,
    seller_links,
    signature,
    source_type,
    verified_date,
)
from shortlist.agent.scan import scan
from shortlist.agent.seller import choose_pages

RIVAL = Competitor(name="RivalDesk", domain="rival-desk.example", classification="direct")


def page(url, body, domain=None):
    return page_from_document(url, f"<html><head><title>T</title></head><body>{body}</body></html>".encode(), domain)


def test_fetch_document_uses_the_safe_fetch_path(monkeypatch):
    calls = []

    def safe(url, expected_domain=None):
        calls.append((url, expected_domain))
        return url, b"<html><body><p>SYNTHETIC page text long enough to keep.</p></body></html>"
    monkeypatch.setattr("shortlist.agent.pages.fetch_html", safe)
    result = fetch_document("https://shop.example/", "shop.example")
    assert calls == [("https://shop.example/", "shop.example")]
    assert result.source.company_domain == "shop.example" and "SYNTHETIC" in result.source.text


def test_ground_returns_the_page_characters():
    p = page("https://shop.example/", "<p>We’re hiring a support lead\u200b today.</p>")
    assert ground("We're hiring a support lead today.", p) == ("We’re hiring a support lead\u200b today.", "text")
    assert ground("We are hiring a support lead", p) is None
    assert ground("hiring", p) is None  # Too short to check.


def test_footer_and_code_are_searchable_but_marked():
    p = page("https://shop.example/", '<p>SYNTHETIC main text of the shop page.</p>'
             '<script src="https://cdn.tool.example/a.js"></script>'
             "<footer>Support powered by RivalDesk</footer>")
    assert "powered by" not in p.source.text  # fetch_page's readable text drops the footer.
    assert ground("Support powered by RivalDesk", p) == ("Support powered by RivalDesk", "text")
    assert ground("https://cdn.tool.example/a.js", p) == ("https://cdn.tool.example/a.js", "html")


def test_source_type_is_decided_by_code():
    assert source_type("https://shop.example/about", "shop.example", hint="news") == "own_site"
    assert source_type("https://shop.example/careers/agent", "shop.example") == "job_post"
    assert source_type("https://jobs.lever.co/shop/1", "shop.example") == "job_post"
    assert source_type("https://rival-desk.example/customers", "shop.example", ["rival-desk.example"]) == "competitor_site"
    assert source_type("https://www.g2.com/products/x", "shop.example") == "review"
    assert source_type("https://paper.example/story", "shop.example", hint="news") == "news"
    assert source_type("https://paper.example/story", "shop.example", hint="own_site") == "other"


def test_dates_must_be_stated_by_the_page():
    ld = '<script type="application/ld+json">{"@type": "JobPosting", "datePosted": "2026-09-01T00:00:00Z"}</script>'
    p = page("https://shop.example/jobs/1", ld + "<p>Posted for a support role on the team.</p>")
    assert p.dates == (date(2026, 9, 1),)
    assert verified_date(date(2026, 9, 1), p) == date(2026, 9, 1)
    assert verified_date(None, p) == date(2026, 9, 1)
    assert verified_date(date(2026, 10, 1), p) is None
    text = page("https://shop.example/news", "<p>On October 3, 2026 we opened a second warehouse.</p>")
    assert verified_date(date(2026, 10, 3), text) == date(2026, 10, 3)


def test_seller_pages_are_chosen_from_observed_links():
    home = page("https://seller.example/", '<a href="/pricing">P</a><a href="/features">F</a><a href="/customers">C</a>'
                '<a href="/about">A</a><a href="/integrations">I</a><a href="/blog/post">B</a><a href="/vs/rival">V</a>'
                '<a href="https://other.example/pricing">X</a><p>SYNTHETIC seller homepage text.</p>')
    assert seller_links(home) == ["https://seller.example/pricing", "https://seller.example/features",
                                  "https://seller.example/customers", "https://seller.example/about",
                                  "https://seller.example/integrations"]
    assert choose_pages(home)[-1] == "https://seller.example/vs/rival" and len(choose_pages(home)) == 5


def test_scan_finds_script_badges_powered_by_and_integrations_pages():
    home = page("https://shop.example/", '<p>SYNTHETIC shop homepage text.</p>'
                '<script src="https://widget.rival-desk.example/embed.js"></script>'
                '<img src="/badge.png" alt="RivalDesk certified">'
                '<script src="/static/rival-desk-clone.js"></script>'
                "<footer>Chat powered by RivalDesk</footer>")
    hits = scan(signature(home, homepage=True), [RIVAL], "Shop")
    assert {h.quote.text for h in hits} == {"https://widget.rival-desk.example/embed.js", "RivalDesk certified",
                                           "Chat powered by RivalDesk"}
    assert all(h.criterion_id == "uses_direct_competitor:rival-desk.example" and h.found_by == "scan" for h in hits)
    integrations = page("https://shop.example/integrations", "<p>SYNTHETIC apps.</p><p>Connect RivalDesk in a click</p>")
    sig = signature(integrations)
    assert sig.kind == "integrations"
    assert [h.quote.text for h in scan(sig, [RIVAL], "Shop")] == ["Connect RivalDesk in a click"]


def test_scan_ignores_unrelated_words_and_first_party_code():
    other = page("https://shop.example/", "<p>SYNTHETIC: our rival desk chairs are sturdy and our app is fast.</p>"
                 '<script src="https://shop.example/rival-desk.js"></script>')
    short = Competitor(name="App", domain="app.example", classification="direct")
    assert scan(signature(other, homepage=True), [short], "Shop") == []
    assert scan(signature(other, homepage=True), [RIVAL], "Shop") == []


def test_signature_keeps_fetch_time():
    p = page("https://shop.example/", "<p>SYNTHETIC shop homepage text.</p>")
    stamped = p.source.model_copy(update={"retrieved_at": datetime(2026, 10, 1, tzinfo=UTC)})
    assert signature(type(p)(source=stamped, html=p.html, full_text=p.full_text)).fetched_at.day == 1
