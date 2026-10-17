import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from shortlist.api import create_app
from shortlist.config import Settings
from shortlist.domain import Candidate, Criterion, Source
from shortlist.market import Campaign, CampaignPlan, competitor_query, market_candidates, read_campaign_plan
from shortlist.providers import ProviderError, SellerDraft
from shortlist.store import Conflict, Store
from shortlist.worker import execute_run


def draft():
    return SellerDraft(offer="Customer acquisition experiments for software businesses", target="Business software startups",
                       criteria=[Criterion(id="software", description="Offers business software")])


def candidates():
    return [Candidate(domain=f"competitor-{i}.example", name=f"Labelled competitor {i}",
                      url=f"https://competitor-{i}.example/", query="fixture", provider="fixture", excerpt="Labelled customer acquisition experiments for software businesses.")
            for i in range(18)]


def campaign_plan():
    return CampaignPlan(campaigns=(Campaign(name="Software founders", target="Business software startups",
        rationale="Campaign hypothesis based on the seller's software offer.", criteria=tuple(draft().criteria)),))


@pytest.mark.parametrize("crash,search_failure,model_failure", [(False, False, False), (True, False, False),
                                                              (False, True, False), (False, False, True)])
def test_market_flow_is_saved_bounded_recoverable_and_confirmed(tmp_path, monkeypatch, crash, search_failure, model_failure):
    settings = Settings(db_path=tmp_path / "market.sqlite3")
    store = Store(settings.db_path)
    identity = store.create_draft("https://seller.example/", "market-flow", experience_version=2)
    calls = []

    class Search:
        name = "fixture"

        def search(self, query, seller_url):
            calls.append("search")
            if search_failure:
                raise ProviderError("Labelled failed competitor search")
            return candidates()

    class Model:
        name = "fixture"

        def seller(self, source):
            calls.append("seller")
            return draft()

        def market(self, seller, competitors):
            calls.append("campaigns")
            assert len(competitors) <= 15
            if model_failure:
                raise ProviderError("Labelled unavailable campaign planner")
            return campaign_plan()

    text = "Labelled seller fixture page."
    source = Source(url="https://seller.example/", company_domain="seller.example", title="Fixture", text=text,
                    content_hash=hashlib.sha256(text.encode()).hexdigest())

    class Crash(BaseException):
        pass

    original = store.checkpoint
    if crash:
        def interrupt(*args, **kwargs):
            original(*args, **kwargs)
            if "market_candidates" in args[3] and "market_plan" not in args[3]:
                raise Crash()
        monkeypatch.setattr(store, "checkpoint", interrupt)
        with pytest.raises(Crash):
            execute_run(store, settings, identity, search=Search(), model=Model(), fetch=lambda *args: source)
        with store.connection() as db:
            db.execute("UPDATE runs SET lease_until=0 WHERE id=?", (identity,))
        store = Store(store.path)
    execute_run(store, settings, identity, search=Search(), model=Model(), fetch=lambda *args: source)
    saved = store.get_run(identity)
    assert calls == ["seller", "search", "campaigns"]
    assert saved["status"] == "awaiting_confirmation"
    assert saved["profile"] == {}
    assert saved["records"] == []
    market = saved["checkpoint"]["market"]
    assert len(market["competitors"]) == (0 if search_failure else 15)
    assert len(market["campaigns"]) == (0 if model_failure else 1)
    assert market["status"] == ("partial" if search_failure or model_failure else "saved")
    assert len(saved["attempts"]) == 4
    client = TestClient(create_app(settings))
    response = client.get(f"/api/runs/{identity}")
    assert response.json()["market"] == market
    assert response.json()["experience_version"] == 2
    from shortlist.export import export_run
    exported = json.loads(export_run(saved, "json"))
    assert exported["market"] == market
    assert exported["seller_source"]["content_hash"] == source.content_hash
    # A name from another run cannot silently become this run's campaign context.
    payload = {**draft().model_dump(exclude={"unknowns"}), "campaign_name": "Unknown campaign",
               "discovery_terms": "Business software expansion"}
    assert client.post(f"/api/runs/{identity}/confirm", json=payload).status_code == 409
    if not model_failure:
        payload["campaign_name"] = "Software founders"
        assert client.post(f"/api/runs/{identity}/confirm", json=payload).status_code == 200
        confirmed = store.get_run(identity)
        assert confirmed["checkpoint"]["campaign_name"] == "Software founders"
        assert confirmed["profile"]["target"] == draft().target
        assert confirmed["checkpoint"]["discovery_terms"] == "Business software expansion"
        assert client.post(f"/api/runs/{identity}/confirm", json=payload).status_code == 200
        assert client.post(f"/api/runs/{identity}/confirm", json={**payload, "discovery_terms": "Different business search"}).status_code == 409
        assert calls == ["seller", "search", "campaigns"]


def test_market_identity_and_campaign_contracts():
    values = candidates()
    assert len(market_candidates(values + values, "https://seller.example/")) == 15
    assert not market_candidates([values[0]], values[0].url)
    with pytest.raises(ValueError):
        market_candidates([values[0].model_copy(update={"url": "http://127.0.0.1/"})], "https://seller.example/")
    with pytest.raises(ValueError):
        CampaignPlan(campaigns=(campaign_plan().campaigns[0],) * 2)
    query = competitor_query(draft().offer, "https://seller.example/")
    assert "seller.example" in query and "customer acquisition" in query


def test_experience_is_immutable_under_the_same_request_key(tmp_path):
    store = Store(tmp_path / "versions.sqlite3")
    identity = store.create_draft("https://seller.example/", "versioned", experience_version=2)
    assert store.create_draft("https://seller.example/", "versioned", experience_version=2) == identity
    with pytest.raises(Conflict):
        store.create_draft("https://seller.example/", "versioned", experience_version=1)
    assert store.get_run(identity)["profile"] == {}


def test_private_performance_conditions_are_hypotheses_not_required_criteria():
    base = campaign_plan().campaigns[0]
    mixed = base.model_copy(update={"criteria": (
        Criterion(id="public", description="Company announced expansion into a new region"),
        Criterion(id="private", description="Lack of historical data for the new target segment")),
        "search_terms": "Companies with poor lead quality"})
    private_only = base.model_copy(update={"name": "Private performance", "criteria": (
        Criterion(id="private", description="Hiring marketers but showing signs of pipeline volatility"),)})
    product = base.model_copy(update={"name": "Analytics software", "criteria": (
        Criterion(id="product", description="Offers lead quality analytics software"),)})
    plan = read_campaign_plan(CampaignPlan(campaigns=(mixed, private_only, product)))
    assert len(plan.campaigns) == 2
    assert [c.id for c in plan.campaigns[0].criteria] == ["public"]
    assert plan.campaigns[0].hypotheses == ("Lack of historical data for the new target segment",)
    assert plan.campaigns[0].search_terms == ""
    assert plan.issues
    assert read_campaign_plan(plan) == plan


def test_stopping_during_campaign_generation_fences_the_late_provider_response(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from scripts.ui_test_providers import FixtureModel, FixtureSearch, fixture_fetch

    settings = Settings(db_path=tmp_path / "market-stop.sqlite3")
    store = Store(settings.db_path)
    identity = store.create_draft("https://seller.example/", "market-stop", experience_version=2)
    entered, release = Event(), Event()

    class HeldModel(FixtureModel):
        def market(self, seller, competitors):
            entered.set()
            assert release.wait(15)
            return super().market(seller, competitors)

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(execute_run, store, settings, identity, search=FixtureSearch(),
                             model=HeldModel(), fetch=fixture_fetch)
        try:
            assert entered.wait(15)
            waiting = TestClient(create_app(settings)).get(f"/api/runs/{identity}").json()
            assert waiting["stage"] == "campaigns"
            assert len(waiting["market"]["competitors"]) == 15
            assert waiting["market"]["campaigns"] == []
            store.stop_run(identity)
            stopped = store.get_run(identity)
        finally:
            release.set()
        assert future.result(timeout=15) is True
    assert store.get_run(identity) == stopped
    assert stopped["checkpoint"]["termination"] == "user_stopped"
    assert "market" not in stopped["checkpoint"]
