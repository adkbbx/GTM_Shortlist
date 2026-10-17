"""Freshness, journal precedence and actual worker/database source reuse."""
import hashlib
from datetime import timedelta

import pytest

from shortlist.config import Settings
from shortlist.domain import Candidate, Criterion, Profile, Source, utcnow
from shortlist.providers import validate_extraction
from shortlist.store import Conflict, Store
from shortlist.worker import execute_run


@pytest.fixture
def cached(tmp_path):
    store = Store(tmp_path / "cache.sqlite3")
    profile = Profile(seller_url="https://seller.example", offer="Customer research service",
                      target="Business software", criteria=(Criterion(id="software", description="Offers software"),))
    run_id = store.create_run(profile, "cache")
    fence = store.claim(run_id)
    text = "Labelled fixture: company software information."
    source = Source(url="https://company.example/", company_domain="company.example", title="Labelled fixture",
                    text=text, content_hash=hashlib.sha256(text.encode()).hexdigest())
    return store, profile, run_id, fence, source


@pytest.mark.parametrize("age,ttl,hit", [(0, 24, True), (23, 24, True), (25, 24, False),
                                        (-1, 24, False), (0, 0, False)])
def test_freshness_preserves_source_identity_and_date(cached, age, ttl, hit):
    store, _, run_id, fence, source = cached
    source = source.model_copy(update={"retrieved_at": utcnow() - timedelta(hours=age)})
    store.cache_source(run_id, fence, source.url, source)
    restored = store.cached_source(source.url, source.company_domain, ttl, run_id=run_id, operation="fetch:company")
    assert (restored is not None) == hit
    if hit:
        assert restored == source
    assert store.get_run(run_id)["attempts"] == []


def test_cache_requires_exact_requested_url_and_domain(cached):
    store, _, run_id, fence, source = cached
    store.cache_source(run_id, fence, source.url, source)
    assert store.cached_source(source.url + "pricing", source.company_domain, 24,
                               run_id=run_id, operation="fetch:pricing") is None
    assert store.cached_source(source.url, "other.example", 24, run_id=run_id, operation="fetch:other") is None


def test_journal_attempt_takes_precedence_even_when_outcome_unknown(cached):
    store, _, run_id, fence, source = cached
    store.cache_source(run_id, fence, source.url, source)
    store.reserve(run_id, fence, "https", "fetch", "fetch:company")
    assert store.cached_source(source.url, source.company_domain, 24,
                               run_id=run_id, operation="fetch:company") is None


def test_cache_write_is_immutable_and_fenced(cached):
    store, _, run_id, fence, source = cached
    store.cache_source(run_id, fence, source.url, source)
    store.cache_source(run_id, fence, source.url, source)  # Idempotent replay.
    with pytest.raises(Conflict, match="cannot be changed"):
        store.cache_source(run_id, fence, source.url, source.model_copy(update={"text": "Changed source content"}))
    with store.connection() as db:
        db.execute("UPDATE runs SET lease_until=0 WHERE id=?", (run_id,))
    replacement = store.claim(run_id)
    assert replacement > fence
    with pytest.raises(Conflict, match="replaced"):
        store.cache_source(run_id, fence, source.url, source)


def test_corrupt_cache_stops_instead_of_silently_refetching(cached):
    store, _, run_id, fence, source = cached
    store.cache_source(run_id, fence, source.url, source)
    with store.connection() as db:
        db.execute("UPDATE source_cache SET payload='{}'")
    with pytest.raises(Conflict, match="corrupt"):
        store.cached_source(source.url, source.company_domain, 24, run_id=run_id, operation="fetch:company")


def test_two_worker_runs_reuse_fresh_page_without_new_fetch_attempt(cached):
    store, profile, run_id, fence, source = cached
    store.checkpoint(run_id, fence, "discovery", {}, "queued")
    fetches = []

    class Search:
        name = "labelled_fixture"

        def search(self, query, seller_url):
            return [Candidate(domain=source.company_domain, url=source.url, name="Labelled fixture",
                              query=query, provider=self.name)]

    class Model:
        name = "labelled_fixture"

        def research(self, profile, candidate, sources):
            return validate_extraction({"name": "Labelled fixture", "findings": []}, profile, candidate.domain, sources)

        def verify(self, profile, record):
            raise AssertionError("All-unknown research must skip paid verification")

    def fetch(*args, **kwargs):
        fetches.append(args[0])
        return source

    # A second seller: the same seller's later shortlists set aside companies it already has, but a fresh saved page
    # is reused across shortlists whoever asks.
    other_seller = profile.model_copy(update={"seller_url": "https://other-seller.example/"})
    for key, owner in (("cache", profile), ("second-run", other_seller)):
        identity = store.create_run(owner, key)
        execute_run(store, Settings(db_path=store.path), identity, search=Search(), model=Model(), fetch=fetch)
    assert len(fetches) == 1
    second = store.get_run(identity)
    assert sum(a["kind"] == "fetch" for a in second["attempts"]) == 0
    assert second["checkpoint"]["source_reuse"]["fetch:company.example"]["source_id"] == source.id
    assert second["records"][0]["research"]["sources"][0] == source.model_dump(mode="json")
