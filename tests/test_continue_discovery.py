"""Saved candidates survive an independent query failure without paid search replay."""
import pytest
from fastapi.testclient import TestClient

from shortlist.api import create_app
from shortlist.config import Settings
from shortlist.domain import Candidate, Criterion, Profile, Source
from shortlist.providers import ProviderError, validate_extraction
from shortlist.store import Conflict, Store, saved_discovery_available
from shortlist.worker import execute_run


def interrupted_discovery(store):
    profile = Profile(seller_url="https://seller.example/", offer="Labelled acquisition research service",
                      target="AI business software", criteria=(Criterion(id="ai", description="AI software"),))
    identity = store.create_run(profile, "interrupted-discovery")
    fence = store.claim(identity)
    candidate = Candidate(domain="company.example", name="Labelled fixture", url="https://company.example/",
                          query="labelled", provider="fixture")
    checkpoint = store.get_run(identity)["checkpoint"]
    checkpoint.update(discovered=[candidate.model_dump(mode="json")], completed_queries=[0])
    attempt = store.reserve(identity, fence, "fixture", "search", "search:1")
    store.outcome(attempt, "failed", run_id=identity, fence=fence,
                  payload={"type": "provider", "message": "Labelled search failure"})
    store.checkpoint(identity, fence, "discovery", checkpoint, "partial", "Labelled search failure")
    return identity, fence


class Model:
    name = "fixture"

    def research(self, profile, candidate, sources):
        return validate_extraction({"name": "Labelled company", "findings": [
            {"criterion_id": "ai", "status": "unknown", "reason": "Labelled missing evidence"}]},
            profile, candidate.domain, sources)


def fetch(url, **kwargs):
    return Source(url=url, company_domain="company.example", title="Labelled fixture",
                  text="Labelled company page", content_hash="fixture")


def test_continue_api_preserves_target_attempts_and_never_searches(tmp_path):
    settings = Settings(db_path=tmp_path / "continue.sqlite3")
    store = Store(settings.db_path)
    identity, fence = interrupted_discovery(store)
    before = store.get_run(identity)
    client = TestClient(create_app(settings))
    path = f"/api/runs/{identity}/continue-discovery"
    assert client.get(f"/api/runs/{identity}").json()["can_continue_discovery"]
    assert client.post(path, json={"confirmation": "wrong"}).status_code == 422
    command = {"confirmation": "use_saved_candidates_without_search"}
    assert client.post(path, json=command).json()["status"] == "queued"
    queued = store.get_run(identity)
    assert queued["profile"] == before["profile"] and queued["attempts"] == before["attempts"]
    assert client.post(path, json=command).status_code == 200
    assert store.get_run(identity) == queued
    with pytest.raises(Conflict):
        store.checkpoint(identity, fence, "discovery", before["checkpoint"])

    class NoSearch:
        name = "fixture"

        def search(self, *args):
            raise AssertionError("Saved-candidate recovery must never search")

    assert execute_run(store, settings, identity, search=NoSearch(), model=Model(), fetch=fetch)
    finished = store.get_run(identity)
    assert len(finished["records"]) == 1 and finished["status"] == "partial"
    assert [a for a in finished["attempts"] if a["kind"] == "search"] == before["attempts"]
    store.continue_discovery(identity)
    assert store.get_run(identity) == finished


@pytest.mark.parametrize("state", ["outcome_unknown", "reserved"])
def test_uncertain_dispatch_blocks_saved_candidate_recovery(tmp_path, state):
    store = Store(tmp_path / "uncertain.sqlite3")
    identity, _ = interrupted_discovery(store)
    with store.connection() as db:
        db.execute("UPDATE attempts SET state=? WHERE run_id=?", (state, identity))
    before = store.get_run(identity)
    assert not saved_discovery_available(before)
    with pytest.raises(Conflict):
        store.continue_discovery(identity)
    assert store.get_run(identity) == before


def test_worker_keeps_candidates_from_one_query_when_another_fails(tmp_path):
    settings = Settings(db_path=tmp_path / "partial-query.sqlite3")
    store = Store(settings.db_path)
    profile = Profile(seller_url="https://seller.example/", offer="Labelled research service", target="AI software",
                      criteria=(Criterion(id="ai", description="AI software"),))
    identity = store.create_run(profile, "partial-query")
    calls = []

    class Search:
        name = "fixture"

        def search(self, query, seller_url):
            calls.append(query)
            if len(calls) == 2:
                raise ProviderError("Labelled independent search failure")
            return [Candidate(domain="company.example", name="Labelled", url="https://company.example/",
                              query=query, provider=self.name)]

    assert execute_run(store, settings, identity, search=Search(), model=Model(), fetch=fetch)
    run = store.get_run(identity)
    assert len(calls) == 2 and len(run["records"]) == 1 and run["status"] == "partial"
    assert run["checkpoint"]["discovery_failures"] == {"1": "Labelled independent search failure"}
    assert not execute_run(store, settings, identity, search=Search(), model=Model(), fetch=fetch)
