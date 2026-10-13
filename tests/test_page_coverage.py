"""Observed-link selection and bounded, durable three-page company research."""
import hashlib
import json

import pytest
from bs4 import BeautifulSoup

from shortlist.config import Settings
from shortlist.domain import Candidate, Criterion, Profile, Source
from shortlist.export import export_run
from shortlist.fetch import FetchError, research_links
from shortlist.providers import validate_extraction
from shortlist.store import Store
from shortlist.worker import execute_run


def test_observed_links_are_ranked_bounded_and_same_company():
    html = '''<nav><a href="/pricing">Pricing</a><a href="/about#team">Team</a>
    <a href="https://www.company.example/about">Duplicate</a><a href="/platform/product">Product</a>
    <a href="https://other.example/about">Other</a><a href="https://docs.company.example/product">Docs</a>
    <a href="https://company.example.evil.example/about">Lookalike</a><a href="/company?token=secret">Query</a>
    <a href="/blog/2026/product">Deep</a><a href="http://company.example/about">Insecure</a>
    <a href="https://[invalid">Malformed</a><a href="https://127.1/about">IP</a></nav>'''
    assert research_links("https://www.company.example/", BeautifulSoup(html, "html.parser")) == (
        "https://www.company.example/about", "https://www.company.example/platform/product")
    assert research_links("https://company.example/", BeautifulSoup("<p>/about is plain text</p>", "html.parser")) == ()


@pytest.mark.parametrize("failure,crash", [(False, False), (True, False), (False, True)])
def test_worker_followups_preserve_sources_failure_and_restart(tmp_path, failure, crash, monkeypatch):
    store = Store(tmp_path / "pages.sqlite3")
    settings = Settings(db_path=store.path)
    profile = Profile(seller_url="https://seller.example/", offer="Acquisition research service",
                      target="Private software businesses", criteria=(Criterion(id="private", description="Privately held"),))
    run_id = store.create_run(profile, "pages")
    fence = store.claim(run_id)
    candidate = Candidate(domain="company.example", url="https://company.example/", name="Labelled fixture",
                          query="fixture", provider="fixture")
    store.checkpoint(run_id, fence, "research", {"candidates": [candidate.model_dump(mode="json")]}, "queued")
    calls = []

    def fetch(url, expected_domain=None):
        calls.append(url)
        if failure and url.endswith("/pricing"):
            raise FetchError("Labelled pricing page failure")
        text = "Example is a privately held software company." if url.endswith("/about") else "Labelled software product page."
        links = ("https://company.example/about", "https://company.example/pricing") if url.endswith("/") else (
            "https://company.example/product",)
        return Source(url=url, company_domain=candidate.domain, title="Fixture", text=text,
                      content_hash=hashlib.sha256(text.encode()).hexdigest(), research_links=links)

    class Model:
        name = "labelled_fixture"

        def research(self, profile, candidate, sources):
            about = next(s for s in sources if s.url.endswith("/about"))
            return validate_extraction({"name": "Fixture", "findings": [{"criterion_id": "private", "status": "supported",
                "evidence": [{"source_id": about.id, "passage": about.text, "claim": "Privately held company"}]}]},
                profile, candidate.domain, sources)

        def verify(self, profile, record):
            from shortlist.verification import Judgment, Verification
            return Verification(judgments=[Judgment(assessment_id="criterion:private", verdict="entailed",
                                                   reason="Explicit labelled about-page ownership")])

    class Crash(BaseException):
        pass

    if crash:
        original = store.outcome

        def stop_after_followup(attempt, state, **kwargs):
            original(attempt, state, **kwargs)
            with store.connection() as db:
                operation = db.execute("SELECT operation_key FROM attempts WHERE id=?", (attempt,)).fetchone()[0]
            if operation.endswith(":page:1"):
                raise Crash()

        monkeypatch.setattr(store, "outcome", stop_after_followup)
        with pytest.raises(Crash):
            execute_run(store, settings, run_id, model=Model(), fetch=fetch)
        with store.connection() as db:
            db.execute("UPDATE runs SET lease_until=0 WHERE id=?", (run_id,))
        store = Store(store.path)
    execute_run(store, settings, run_id, model=Model(), fetch=fetch)
    saved = Store(store.path).get_run(run_id)
    assert calls == [candidate.url, "https://company.example/about", "https://company.example/pricing"]
    record = saved["records"][0]["research"]
    assert len(record["sources"]) == (2 if failure else 3)
    about = next(s for s in record["sources"] if s["url"].endswith("/about"))
    assert record["findings"][0]["evidence"][0]["source_id"] == about["id"]
    assert sum(a["kind"] == "fetch" for a in saved["attempts"]) == 3
    assert bool(saved["checkpoint"]["page_failures"][candidate.domain]) == failure
    assert bool(json.loads(export_run(saved, "json"))["page_failures"][candidate.domain]) == failure
    assert saved["status"] == ("partial" if failure else "ready")
    assert bool(saved["error"]) == failure


def test_legacy_cached_snapshot_without_links_is_refetched_not_rewritten(tmp_path):
    store = Store(tmp_path / "legacy-cache.sqlite3")
    profile = Profile(seller_url="https://seller.example", offer="Customer research service", target="Business software",
                      criteria=(Criterion(id="software", description="Offers software"),))
    run_id = store.create_run(profile, "legacy-cache")
    fence = store.claim(run_id)
    source = Source(url="https://company.example/", company_domain="company.example", title="Old snapshot",
                    text="Original immutable company text.", content_hash="fixture")
    store.cache_source(run_id, fence, source.url, source)
    with store.connection() as db:
        old = source.model_dump(mode="json", exclude={"research_links"})
        db.execute("UPDATE source_cache SET payload=?", (json.dumps(old),))
    assert store.cached_source(source.url, source.company_domain, 24, run_id=run_id, operation="fetch:company") is None
    with store.connection() as db:
        assert json.loads(db.execute("SELECT payload FROM source_cache").fetchone()[0]) == old
