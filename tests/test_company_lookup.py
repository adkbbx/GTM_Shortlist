"""A company name is unresolved identity, never a guessed domain."""
import hashlib
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from shortlist.api import create_app
from shortlist.config import Settings
from shortlist.domain import Candidate, Criterion, Source
from shortlist.providers import ProviderError, SellerDraft, company_name_matches
from shortlist.store import Conflict, Store
from shortlist.worker import execute_run


class LookupSearch:
    name = "labelled-website-lookup"
    def __init__(self):
        self.calls = []
    def search(self, query, seller_url):
        self.calls.append((query, seller_url))
        return [Candidate(domain=domain, url=f"https://{domain}/", name="Eygentic Example Software (labelled fixture)",
                          query=query, provider=self.name) for domain in ("business.example", "namesake.example")]


def assert_lookup_lifecycle(store, settings):
    identity = store.create_draft(None, "named-company", company_name="Eygentic")
    assert store.create_draft(None, "named-company", company_name="eygentic") == identity
    with pytest.raises(Conflict):
        store.create_draft(None, "named-company", company_name="Another company")
    with pytest.raises(Conflict):
        store.confirm_website(identity, "https://business.example/")
    search = LookupSearch()
    def forbidden(*args, **kwargs):
        raise AssertionError("No page/model call is allowed before website choice")
    class NoModel:
        seller = forbidden
    assert execute_run(store, settings, identity, search=search, fetch=forbidden, model=NoModel())
    run = store.get_run(identity)
    assert run["stage"] == "website" and run["status"] == "awaiting_confirmation"
    assert run["checkpoint"]["seller_url"] is None
    assert len(run["checkpoint"]["website_matches"]) == 2
    assert len(run["attempts"]) == 1 and run["attempts"][0]["kind"] == "search"
    matches = run["checkpoint"]["website_matches"]
    # Crash after provider receipt but before final stage checkpoint: replay the
    # same journal value without another paid lookup or changed discovery dates.
    with store.connection() as db:
        db.execute("UPDATE runs SET status='queued',stage='identity',lease_until=0,checkpoint=? WHERE id=?",
                   ('{"company_name":"Eygentic","seller_url":null}', identity))
    assert execute_run(store, settings, identity, search=search, fetch=forbidden, model=NoModel())
    assert len(search.calls) == 1
    assert store.get_run(identity)["checkpoint"]["website_matches"] == matches
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: store.confirm_website(identity, "https://business.example/"), range(2)))
    chosen = store.get_run(identity)
    store.confirm_website(identity, "https://business.example/")
    assert store.get_run(identity) == chosen
    assert sum(event["label"] == "You confirmed the company website" for event in chosen["events"]) == 1
    with pytest.raises(Conflict):
        store.confirm_website(identity, "https://namesake.example/")
    text = "Labelled fixture seller offers business software."
    source = Source(url="https://business.example/", company_domain="business.example", title="Fixture",
                    text=text, content_hash=hashlib.sha256(text.encode()).hexdigest())
    class Model:
        name = "labelled-website-profile"
        def seller(self, source):
            return SellerDraft(offer="Labelled business software", target="Labelled business customers",
                               criteria=[Criterion(id="software", description="Uses business software")])
    execute_run(store, settings, identity, model=Model(), fetch=lambda *args: source)
    final = store.get_run(identity)
    assert final["stage"] == "confirmation"
    assert final["checkpoint"]["draft"]["offer"] == "Labelled business software"
    assert final["profile"] == {} and len(search.calls) == 1
    return identity


def test_lookup_replay_choice_and_profile_use_one_saved_run(tmp_path):
    store = Store(tmp_path / "identity.sqlite3")
    assert_lookup_lifecycle(store, Settings(db_path=store.path))


@pytest.mark.parametrize("outcome", ["empty", "failure", "unknown"])
def test_failed_lookup_allows_manual_public_website_without_redispatch(tmp_path, outcome):
    store = Store(tmp_path / "identity.sqlite3")
    settings = Settings(db_path=store.path)
    identity = store.create_draft(None, "lookup-fallback", company_name="Some Company")
    class Search:
        name = "labelled-lookup-failure"
        def search(self, *args):
            if outcome == "unknown":
                raise AssertionError("Unknown outcomes must not redispatch")
            if outcome == "failure":
                raise ProviderError("Labelled provider failure")
            return []
    if outcome == "unknown":
        fence = store.claim(identity)
        from shortlist.journal import call_step
        class Crash(BaseException):
            pass
        def crash():
            raise Crash()
        with pytest.raises(Crash):
            call_step(store, identity, fence, 200, kind="search", provider=Search.name, operation="seller:identity",
                      function=crash, inputs={"query": '"Some Company" official company website', "company_name": "Some Company"}, decode=list)
        with store.connection() as db:
            db.execute("UPDATE runs SET lease_until=0 WHERE id=?", (identity,))
    execute_run(store, settings, identity, search=Search())
    run = store.get_run(identity)
    assert run["stage"] == "website" and run["checkpoint"]["website_matches"] == []
    assert len(run["attempts"]) == 1
    store.confirm_website(identity, "https://manual.example/")
    assert store.get_run(identity)["checkpoint"]["seller_url"] == "https://manual.example/"


def test_company_api_handles_unresolved_identity_and_stopped_selection(tmp_path):
    settings = Settings(db_path=tmp_path / "identity.sqlite3")
    client = TestClient(create_app(settings))
    response = client.post("/api/sellers", json={"seller_url": "Example Software", "request_key": "lookup-api"})
    assert response.status_code == 201
    identity = response.json()["id"]
    assert response.json()["seller_url"] is None and response.json()["company_name"] == "Example Software"
    store = Store(settings.db_path)
    execute_run(store, settings, identity, search=LookupSearch())
    assert client.get(f"/api/runs/{identity}").json()["website_matches"][0]["domain"] == "business.example"
    assert client.post(f"/api/runs/{identity}/confirm", json={"offer": "Labelled valid offer", "target": "Valid target",
        "criteria": [{"id": "ai", "description": "AI software"}]}).status_code == 409
    assert client.post(f"/api/runs/{identity}/website", json={"website_url": "127.0.0.1"}).status_code == 422
    store.stop_run(identity)
    assert client.post(f"/api/runs/{identity}/website", json={"website_url": "business.example"}).status_code == 409


def test_invalid_lookup_links_are_never_presented_as_website_matches(tmp_path):
    store = Store(tmp_path / "invalid-link.sqlite3")
    identity = store.create_draft(None, "invalid-lookup", company_name="Eygentic")
    class Search:
        name = "labelled-invalid-lookup"
        def search(self, *args):
            return [Candidate(domain="business.example", url="javascript:alert(1)", name="Invalid labelled fixture",
                              query="fixture", provider=self.name)]
    execute_run(store, Settings(db_path=store.path), identity, search=Search())
    run = store.get_run(identity)
    assert run["checkpoint"]["website_matches"] == []
    assert run["attempts"][0]["state"] == "failed"
    assert run["stage"] == "website"


@pytest.mark.parametrize("domain,title,expected", [
    ("eygentic.com", "Customer acquisition", True),
    ("namesake.example", "Eygentic (labelled namesake)", True),
    ("genome.gov", "Eugenics history", False),
    ("en.wikipedia.org", "Eygentic", False),
])
def test_name_relevance_never_treats_search_spelling_correction_as_identity(domain, title, expected):
    candidate = Candidate(domain=domain, url=f"https://{domain}/", name=title, query='"Eygentic"', provider="fixture")
    assert company_name_matches(candidate, "Eygentic") is expected


def test_saved_unrelated_matches_are_hidden_without_rewriting_the_lookup(tmp_path):
    settings = Settings(db_path=tmp_path / "old-lookup.sqlite3")
    store = Store(settings.db_path)
    identity = store.create_draft(None, "old-lookup", company_name="Eygentic")
    candidate = Candidate(domain="genome.gov", url="https://genome.gov/", name="Eugenics", query="old lookup", provider="fixture")
    store.checkpoint(identity, store.claim(identity), "website", {"company_name": "Eygentic", "seller_url": None,
                     "website_matches": [candidate.model_dump(mode="json")]}, "awaiting_confirmation")
    before = store.get_run(identity)
    client = TestClient(create_app(settings))
    response = client.get(f"/api/runs/{identity}").json()
    assert response["website_matches"] == []
    assert "No clear website match" in response["error"]
    assert store.get_run(identity) == before
