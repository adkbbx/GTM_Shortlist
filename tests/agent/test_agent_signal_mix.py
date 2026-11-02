"""The signal mix (2 November): live runs found every company through job posts and had no timing signal, because a
seller's site rarely says when to buy. Discovery now spreads its searches across hiring, news, social posts and
lookalikes, and X posts are read through X's embed endpoint. Responses here are SYNTHETIC."""
from datetime import date

import httpx

from shortlist.agent.discovery import interleaved, signal_of
from shortlist.agent.models import CandidateRef, Signal
from shortlist.agent.pages import ground, verified_date, x_post


def test_each_company_carries_the_kind_of_signal_that_found_it():
    assert signal_of("News", "") == "news"  # the model's own label wins
    assert signal_of("", "open job post on its Lever board: SDR (https://jobs.lever.co/a/1)") == "hiring"
    assert signal_of("", 'search "site:jobs.ashbyhq.com SDR outbound"') == "hiring"
    assert signal_of("", "similar to Ramp") == "lookalike"
    assert signal_of("", 'search "site:linkedin.com/posts we\'re hiring first SDR"') == "social"
    assert signal_of("", "raised a Series A in September (TechCrunch)") == "news"
    assert signal_of("", "") == ""


def test_candidates_are_researched_one_signal_at_a_time():
    refs = [CandidateRef(domain=f"{kind}{n}.example", url=f"https://{kind}{n}.example/", signal=kind)
            for kind, n in [("hiring", 1), ("hiring", 2), ("hiring", 3), ("news", 1), ("social", 1), ("news", 2)]]
    assert [ref.domain for ref in interleaved(refs)] == [
        "hiring1.example", "news1.example", "social1.example", "hiring2.example", "news2.example", "hiring3.example"]


def test_a_role_on_the_companys_own_careers_pages_counts_as_open():
    from shortlist.agent.pages import own_role_page, page_from_document

    def page(url, body="<p>SYNTHETIC careers page: we are hiring a support lead for chat and email.</p>"):
        return page_from_document(url, f"<html><body>{body}</body></html>".encode(), None)
    assert own_role_page(page("https://trailgear.example/careers/support-lead"), "trailgear.example")
    assert own_role_page(page("https://jobs.trailgear.example/support-lead"), "trailgear.example")
    assert not own_role_page(page("https://trailgear.example/careers"), "trailgear.example")  # an index, not a role
    assert not own_role_page(page("https://other.example/careers/support-lead"), "trailgear.example")
    closed = "<p>SYNTHETIC: this position has been filled. Thank you for your interest in Trailgear.</p>"
    assert not own_role_page(page("https://trailgear.example/careers/support-lead", closed), "trailgear.example")


def test_only_a_source_link_that_search_returned_is_kept():
    from shortlist.agent.discovery import source_link
    seen = {"https://news.example/trailgear-raises-seed"}
    assert source_link("https://news.example/trailgear-raises-seed", seen) == "https://news.example/trailgear-raises-seed"
    assert source_link("https://news.example/invented-article", seen) == ""


def test_a_standard_timing_signal_is_labelled_and_needs_no_quote():
    assert Signal(id="timing-std-1", kind="timing", text="Announced a new funding round", standard=True).quotes == []
    try:
        Signal(id="timing-1", kind="timing", text="Announced a new funding round")
    except ValueError as exc:
        assert "needs a quote" in str(exc)
    else:
        raise AssertionError("a signal inferred from the site must be quoted")


def test_an_x_post_is_read_through_the_embed_endpoint_with_its_date():
    embed = {"author_name": "Trailgear", "html": '<blockquote class="twitter-tweet"><p lang="en">We just raised our '
             'seed round and are hiring our first support lead (SYNTHETIC)</p>&mdash; Trailgear (@trailgear) '
             '<a href="https://x.com/trailgear/status/1?ref_src=twsrc">October 20, 2026</a></blockquote>'}
    requests = []

    def handle(request):
        requests.append(str(request.url))
        if request.url.host == "publish.twitter.com":
            return httpx.Response(301, headers={"location": "https://publish.x.com/oembed?url=x"})
        return httpx.Response(200, json=embed)
    page = x_post("https://twitter.com/trailgear/status/1858?s=20", transport=httpx.MockTransport(handle))
    assert page.url == "https://x.com/trailgear/status/1858" and page.domain == "x.com"
    assert requests[0].startswith("https://publish.x.com/oembed?url=https%3A%2F%2Fx.com%2Ftrailgear%2Fstatus%2F1858")
    assert verified_date(None, page) == date(2026, 10, 20)
    assert ground("We just raised our seed round and are hiring our first support lead", page) is not None
