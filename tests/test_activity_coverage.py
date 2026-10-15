"""Labelled activity-page fixtures; never dispatch live provider requests."""
import hashlib
import json
from datetime import UTC, datetime
from urllib.parse import urlsplit

import pytest
from bs4 import BeautifulSoup

from shortlist.config import Settings
from shortlist.domain import Candidate, Criterion, Profile, Source
from shortlist.export import export_run
from shortlist.fetch import FetchError, activity_links
from shortlist.providers import validate_extraction
from shortlist.store import Store
from shortlist.worker import execute_run


def test_activity_frontier_is_observed_same_company_and_bounded():
    soup = BeautifulSoup('''<nav><a href="/blog">Blog</a><a href="/careers">Careers</a>
        <a href="/news/launch">Launch</a><a href="/news/launch#top">Duplicate</a>
        <a href="https://evil.example/news">Other</a><a href="https://jobs.company.example/jobs">Subdomain</a>
        <a href="/news?token=secret">Query</a><a href="http://company.example/news">HTTP</a>
        <a href="/product/news">Product</a><a href="/news/a/b/c">Deep</a>
        <a href="https://127.0.0.1/news">IP</a><a href="https://[broken">Broken</a></nav>''', "html.parser")
    assert activity_links("https://company.example/", soup) == ("https://company.example/news/launch",)
    assert activity_links("https://company.example/news/launch", soup) == ("https://company.example/careers",)
    assert activity_links("https://company.example/", BeautifulSoup("<p>/news is not a link</p>", "html.parser")) == ()


def test_empty_activity_preserves_historical_nested_serialization():
    source = Source(url="https://company.example/", company_domain="company.example", title="Fixture",
                    text="Labelled fixture page.", content_hash="fixture")
    old = source.model_dump(mode="json", exclude={"activity_links"})
    assert Source.model_validate(old).model_dump(mode="json") == old
    assert json.loads(source.model_dump_json()) == old


@pytest.mark.parametrize("policy,failure,crash", [(2, False, False), (3, False, False),
    (3, True, False), (3, False, True)])
def test_activity_selection_preserves_primary_and_replays_outcome(tmp_path, monkeypatch, policy, failure, crash):
    profile = Profile(seller_url="https://seller.example/", offer="Acquisition research service",
        target="AI logistics software", criteria=(Criterion(id="software", description="Offers software"),),
        confirmed_at=datetime(2026, 10, 15, tzinfo=UTC))
    candidates = [Candidate(domain=f"company-{i}.example", url=f"https://company-{i}.example/",
        name="Labelled company fixture", query="fixture", provider="fixture") for i in range(6)]
    store = Store(tmp_path / "activity.sqlite3")
    settings = Settings(db_path=store.path, source_cache_hours=0)
    run_id = store.create_run(profile, "activity-selection")
    fence = store.claim(run_id)
    store.checkpoint(run_id, fence, "discovery", {"candidates": [c.model_dump(mode="json") for c in candidates],
        "selection_policy": policy}, "queued")
    calls, researched = [], []

    def fetch(url, expected_domain=None):
        calls.append(url)
        if failure and url.endswith("/news"):
            raise FetchError("Labelled activity source failure")
        text = "AI logistics software."
        if url.endswith("/news") and expected_domain in {c.domain for c in candidates[3:]}:
            text += " On 2026-10-01, we are hiring a marketer."
        primary = urlsplit(url).path == "/"
        return Source(url=url, company_domain=expected_domain, title="Labelled fixture", text=text,
            content_hash=hashlib.sha256(text.encode()).hexdigest(),
            activity_links=(f"https://{expected_domain}/news",) if primary else (f"https://{expected_domain}/news/never-follow",),
            research_links=(f"https://{expected_domain}/about", f"https://{expected_domain}/team") if primary else ())

    class Model:
        name = "labelled_fixture"

        def research(self, profile, candidate, sources):
            researched.append(candidate.domain)
            assert len(sources) == (4 if policy == 3 and not failure else 3)
            return validate_extraction({"name": candidate.name, "findings": []}, profile, candidate.domain, sources)

    class Crash(BaseException):
        pass

    if crash:
        original = store.outcome

        def after_outcome(attempt, state, **kwargs):
            original(attempt, state, **kwargs)
            with store.connection() as db:
                operation = db.execute("SELECT operation_key FROM attempts WHERE id=?", (attempt,)).fetchone()[0]
            if operation.endswith(":activity"):
                raise Crash()
        monkeypatch.setattr(store, "outcome", after_outcome)
        with pytest.raises(Crash):
            execute_run(store, settings, run_id, model=Model(), fetch=fetch)
        with store.connection() as db:
            db.execute("UPDATE runs SET lease_until=0 WHERE id=?", (run_id,))
        store = Store(store.path)
    execute_run(store, settings, run_id, model=Model(), fetch=fetch)
    saved = Store(store.path).get_run(run_id)
    expected = candidates[3:] if policy == 3 and not failure else candidates[:3]
    assert researched == [c.domain for c in expected]
    assert len(calls) == len(set(calls)) == (12 if policy == 2 else 18)
    assert not any("never-follow" in url for url in calls)
    assert sum(a["kind"] == "model" for a in saved["attempts"]) == 3
    assert sum(a["kind"] == "search" for a in saved["attempts"]) == 0
    assert len(saved["records"]) == 3
    assert bool(saved["checkpoint"].get("activity_failures")) == failure
    assert bool(json.loads(export_run(saved, "json"))["activity_failures"]) == failure
    if policy == 3 and not failure:
        signal = saved["checkpoint"]["selection"][0]["signals"][0]
        news = next(s for s in saved["records"][0]["research"]["sources"] if s["url"].endswith("/news"))
        assert signal["source_id"] == news["id"]
        assert signal["event_date"] == "2026-10-01"
    assert not execute_run(Store(store.path), settings, run_id, model=Model(), fetch=fetch)


@pytest.mark.parametrize("stopped", [False, True])
def test_activity_link_cannot_escape_company_or_write_after_stop(tmp_path, stopped):
    from shortlist.store import Conflict

    profile = Profile(seller_url="https://seller.example/", offer="Acquisition research service",
        target="AI logistics software", criteria=(Criterion(id="software", description="Offers software"),))
    store = Store(tmp_path / f"boundary-{stopped}.sqlite3")
    settings = Settings(db_path=store.path, source_cache_hours=0)
    run_id = store.create_run(profile, "activity-boundary")
    candidate = Candidate(domain="company.example", url="https://company.example/", name="Labelled fixture",
        query="fixture", provider="fixture")
    fence = store.claim(run_id)
    store.checkpoint(run_id, fence, "discovery", {"candidates": [candidate.model_dump(mode="json")],
        "selection_policy": 3}, "queued")
    calls = []

    def fetch(url, expected_domain=None):
        calls.append(url)
        if url.endswith("/news"):
            store.stop_run(run_id)
        return Source(url=url, company_domain=expected_domain, title="Fixture", text="AI logistics software.",
            content_hash="fixture", activity_links=("https://company.example/news" if stopped else "https://evil.example/news",))

    class Model:
        name = "labelled_fixture"

        def research(self, profile, candidate, sources):
            return validate_extraction({"name": candidate.name, "findings": []}, profile, candidate.domain, sources)

    execute_run(store, settings, run_id, model=Model(), fetch=fetch)
    saved = store.get_run(run_id)
    if stopped:
        assert calls == [candidate.url, "https://company.example/news"]
        assert saved["checkpoint"]["termination"] == "user_stopped"
        assert not saved["records"]
        assert "completed_activity" not in saved["checkpoint"]
        assert len(saved["checkpoint"]["sources"][candidate.domain]) == 1
        with pytest.raises(Conflict):
            store.checkpoint(run_id, fence, "review", {}, "ready")
    else:
        assert calls == [candidate.url]
        assert saved["checkpoint"]["activity_failures"][candidate.domain]["reason"] == "Activity link changed company identity"
        assert saved["status"] == "partial"
        assert len(saved["records"]) == 1


def test_actual_fetch_retains_activity_frontier_before_navigation_is_removed(monkeypatch):
    from io import BytesIO

    from shortlist.fetch import fetch_page

    body = b'<html><title>Labelled company</title><nav><a href="/news">Company news</a></nav><main>We offer AI logistics software for business operations.</main></html>'
    monkeypatch.setattr("shortlist.fetch.resolve_public", lambda *args, **kwargs: "8.8.8.8")

    class Response(BytesIO):
        status = 200

        def getheader(self, key, default=None):
            return "text/html" if key == "Content-Type" else default

    class Connection:
        def __init__(self, *args):
            self.stream_socket = self

        def connect(self):
            pass

        def settimeout(self, timeout):
            pass

        def request(self, *args, **kwargs):
            pass

        def getresponse(self):
            return Response(body)

        def close(self):
            pass

    monkeypatch.setattr("shortlist.fetch.PinnedHTTPSConnection", Connection)
    source = fetch_page("https://company.example/", expected_domain="company.example")
    assert source.activity_links == ("https://company.example/news",)
    assert "Company news" not in source.text
    assert source.content_hash == hashlib.sha256(body).hexdigest()
    assert source.model_dump(mode="json")["activity_links"] == ["https://company.example/news"]
