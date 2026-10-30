"""Labelled synthetic providers for browser tests of the real API/worker/database.

Never use this as the live application server. It performs no company discovery.
"""

import os
import sqlite3
import tempfile
import threading
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from ui_test_providers import FixtureModel, FixtureSearch, fixture_fetch

from shortlist.api import create_app
from shortlist.config import Settings
from shortlist.domain import Candidate, OperatorReviewCommand, Profile
from shortlist.fetch import FetchError
from shortlist.local_credentials import LocalCredentials, validate_tavily_key
from shortlist.store import Store
from shortlist.worker import execute_run

# Browser journeys share one fixture database but are independent; one journey's companies are not set aside in the
# next. tests/test_discovery_policy.py covers setting aside companies from earlier shortlists.
Store.researched_elsewhere = lambda self, run_id, seller_url: set()
test_directory = tempfile.TemporaryDirectory(prefix="gtm-shortlist-ui-")
settings = Settings(
    db_path=Path(os.environ.get("SHORTLIST_UI_TEST_DB", str(Path(test_directory.name) / "research.sqlite3"))),
    tavily_key="labelled_fixture_not_a_real_key",
    gemma_base_url="https://labelled-fixture.example",
    gemma_model="labelled_fixture",
)
store = Store(settings.db_path)
stopped = threading.Event()
held_runs = {}
held_lock = threading.Lock()


def loop():
    while not stopped.is_set():
        store.worker_heartbeat("labelled_browser_fixture")
        for run in store.list_runs():
            if run["status"] in ("queued", "running"):
                if store.get_run(run["id"])["checkpoint"].get("competitor_fixture"):
                    continue
                with held_lock:
                    hold = held_runs.get(run["id"])
                def fetch(url, expected_domain=None, hold=hold):
                    if hold and expected_domain == "example-2.com" and not hold.wait(30):
                        raise FetchError("Labelled browser stop fixture was not released")
                    return fixture_fetch(url, expected_domain)
                execute_run(
                    store,
                    settings.model_copy(update={"source_cache_hours": 0}) if hold else settings,
                    run["id"],
                    search=FixtureSearch(),
                    model=FixtureModel(),
                    fetch=fetch,
                )
        stopped.wait(0.1)


if __name__ == "__main__":
    thread = threading.Thread(target=loop, daemon=True)
    thread.start()
    application = FastAPI()

    @application.get("/api/runs/{run_id}/site-icon/{domain}")
    def fixture_site_icon(run_id: str, domain: str):
        # Browser tests explicitly substitute declared icons. Never fetch live sites.
        return {"url": None}

    @application.get("/", response_class=HTMLResponse)
    def fixture_home():
        # Never inherit an operator's live directory ID from built frontend assets.
        html = (Path(__file__).resolve().parents[1] / "dist" / "index.html").read_text(encoding="utf-8")
        # Existing journeys start from the classic workspace; agent specs open /?flow=agent.
        return html.replace("<head>", '<head><meta name="shortlist-company-suggestions-client-id" content="">'
                            '<meta name="shortlist-start-flow" content="classic">')

    @application.post("/__fixture_recoverable_offer")
    def recoverable_offer(keep_valid: bool = False):
        import json
        from uuid import uuid4
        raw = json.loads((Path(__file__).resolve().parents[1] / "examples/evaluation/seller-recovery-rakuten.json").read_text())["response"]
        if keep_valid:
            raw["customer_criteria"][0] = {"id": "online-store", "subject": "target_customer",
                "customer_characteristic": "Sells consumer products through an online store", "required": True}
        with held_lock:
            identity = store.create_draft("https://seller.example/", "recoverable-offer-" + uuid4().hex)
            fence = store.claim(identity)
            checkpoint = store.get_run(identity)["checkpoint"]
            checkpoint["seller_model_output"] = {"content": json.dumps(raw), "issues": [{"type": "value_error"}]}
            store.checkpoint(identity, fence, "confirmation", checkpoint, "awaiting_confirmation",
                             "Gemma output failed validation")
        return {"id": identity}

    @application.post("/__fixture_failed_offer")
    def failed_offer():
        from uuid import uuid4
        with held_lock:
            identity = store.create_draft("https://seller.example/", "failed-offer-" + uuid4().hex)
            fence = store.claim(identity)
            checkpoint = store.get_run(identity)["checkpoint"]
            checkpoint["seller_model_output"] = {"content": "{}", "issues": [{"type": "missing"}]}
            store.checkpoint(identity, fence, "confirmation", checkpoint, "awaiting_confirmation",
                            "Gemma output failed validation. Enter and confirm your offer and target manually to continue.")
        return {"id": identity}

    @application.post("/__fixture_unstarted_seller")
    def unstarted_seller():
        from uuid import uuid4
        with held_lock:
            identity = store.create_draft("https://seller.example/", "unstarted-seller-" + uuid4().hex)
            fence = store.claim(identity)
            checkpoint = store.get_run(identity)["checkpoint"]
            store.checkpoint(identity, fence, "seller", checkpoint, "partial", "Labelled pre-dispatch setup failure")
        return {"id": identity}

    @application.post("/__fixture_saved_discovery")
    def saved_discovery():
        from uuid import uuid4
        draft = FixtureModel().seller(None)
        profile = Profile(seller_url="https://seller.example/", offer=draft.offer, target=draft.target,
                          criteria=tuple(draft.criteria))
        with held_lock:
            identity = store.create_run(profile, "saved-discovery-" + uuid4().hex)
            fence = store.claim(identity)
            checkpoint = store.get_run(identity)["checkpoint"]
            candidate = FixtureSearch().search("labelled saved search", profile.seller_url)[0]
            checkpoint.update(discovered=[candidate.model_dump(mode="json")], completed_queries=[0])
            attempt = store.reserve(identity, fence, FixtureSearch.name, "search", "search:1")
            store.outcome(attempt, "failed", run_id=identity, fence=fence,
                          payload={"type": "provider", "message": "Labelled interrupted discovery"})
            store.checkpoint(identity, fence, "discovery", checkpoint, "partial", "Labelled interrupted discovery")
        return {"id": identity}

    @application.post("/__fixture_broad_target")
    def broad_target_fixture(campaigns: bool = True):
        from uuid import uuid4

        from shortlist.market import MarketResearch
        draft = FixtureModel().seller(None).model_copy(update={"target":
            "B2B and SaaS companies seeking to make their customer acquisition more predictable."})
        with held_lock:
            identity = store.create_draft("https://seller.example/", "broad-target-" + uuid4().hex)
            fence = store.claim(identity)
            checkpoint = store.get_run(identity)["checkpoint"]
            checkpoint["draft"] = draft.model_dump(mode="json")
            if campaigns:
                checkpoint["market"] = MarketResearch(competitors=(), campaigns=FixtureModel().market(draft, []).campaigns, status="saved").model_dump(mode="json")
            store.checkpoint(identity, fence, "confirmation", checkpoint, "awaiting_confirmation")
        return {"id": identity}

    @application.post("/__fixture_low_yield")
    def low_yield_fixture(empty: bool = False):
        from uuid import uuid4
        draft = FixtureModel().seller(None)
        profile = Profile(seller_url="https://seller.example/", offer=draft.offer, target="B2B SaaS companies",
                          criteria=tuple(draft.criteria))
        with held_lock:
            identity = store.create_run(profile, "low-yield-" + uuid4().hex)
            fence = store.claim(identity)
            candidate = FixtureSearch().search("labelled fixture", profile.seller_url)[1]
            if not empty:
                sources = tuple(fixture_fetch(url, candidate.domain) for url in (candidate.url, candidate.url + "about"))
                store.save_record(identity, fence, FixtureModel().research(profile, candidate, sources))
            checkpoint = store.get_run(identity)["checkpoint"]
            checkpoint.update(company_limit=3, completed_queries=[0, 1, 2],
                              candidates=[] if empty else [candidate.model_dump(mode="json")],
                              candidate_failures={"service.example": {"reason": "Sells services to this market rather than being in it"}})
            store.checkpoint(identity, fence, "review", checkpoint, "partial")
        return {"id": identity}

    @application.post("/__fixture_competitors")
    def competitor_fixture():
        import json
        from uuid import uuid4

        from check_competitors import CASES, inputs

        from shortlist.providers import validate_extraction

        class SavedPageModel:
            name = "labelled_saved_page_fixture"

            def research(self, profile, candidate, sources):
                return validate_extraction({"name": candidate.name, "findings": []}, profile, candidate.domain, sources)

        rows = [inputs(c) for c in json.loads(CASES.read_text(encoding="utf-8"))["cases"]
                if c["seller"]["domain"] == "unifyr.com"]
        profile = rows[0][0]
        with held_lock:
            identity = store.create_run(profile, "saved-peer-fixture-" + uuid4().hex)
            fence = store.claim(identity)
            checkpoint = store.get_run(identity)["checkpoint"]
            checkpoint.update(competitor_fixture=True, company_limit=6,
                candidates=[c.model_dump(mode="json") for _, c, _ in rows],
                sources={c.domain: [s.model_dump(mode="json")] for _, c, s in rows})
            store.checkpoint(identity, fence, "research", checkpoint, "queued")
        def forbidden(*args, **kwargs):
            raise AssertionError("Saved-page browser fixture must not fetch")
        execute_run(store, settings, identity, model=SavedPageModel(), fetch=forbidden)
        return {"id": identity}

    @application.post("/__fixture_corrupt_provider")
    def corrupt_provider():
        credentials = LocalCredentials(settings.db_path)
        credentials.save(validate_tavily_key("tvly-labelled-corruption-fixture"))
        with sqlite3.connect(credentials.path) as db:
            db.execute("UPDATE local_provider SET payload=?", (b"labelled corrupt fixture",))
        return {"fixture": True}

    @application.post("/__fixture_held_run")
    def held_run():
        draft = FixtureModel().seller(None)
        profile = Profile(seller_url="https://eygentic.com/", offer=draft.offer, target=draft.target,
                          criteria=tuple(draft.criteria))
        from uuid import uuid4
        with held_lock:
            identity = store.create_run(profile, "held-browser-" + uuid4().hex)
            held_runs[identity] = threading.Event()
        return {"id": identity}

    @application.post("/__fixture_historical_article")
    def historical_article():
        from uuid import uuid4

        from shortlist.providers import validate_extraction
        draft = FixtureModel().seller(None)
        profile = Profile(seller_url="https://seller.example/", offer=draft.offer,
                          target=draft.target, criteria=tuple(draft.criteria))
        with held_lock:
            identity = store.create_run(profile, "historical-article-" + uuid4().hex)
            fence = store.claim(identity)
            source = fixture_fetch("https://publisher.example/blog/third-party-product", "publisher.example")
            record = validate_extraction({"name": "Another company", "findings": []}, profile, "publisher.example", (source,))
            with store.connection() as db:
                db.execute("INSERT INTO records(id,run_id,domain,research) VALUES (?,?,?,?)",
                           (record.id, identity, record.domain, record.model_dump_json()))
            store.checkpoint(identity, fence, "review", {}, "partial")
        return {"id": identity}

    @application.post("/__fixture_three_companies")
    def three_companies():
        from uuid import uuid4
        draft = FixtureModel().seller(None)
        profile = Profile(seller_url="https://seller.example/", offer=draft.offer,
                          target="Three comparison companies in business software", criteria=tuple(draft.criteria))
        with held_lock:
            identity = store.create_run(profile, "three-companies-" + uuid4().hex)
        return {"id": identity}

    @application.post("/__fixture_activity_selection")
    def activity_selection():
        from uuid import uuid4
        draft = FixtureModel().seller(None)
        profile = Profile(seller_url="https://seller.example/", offer=draft.offer,
                          target=draft.target, criteria=tuple(draft.criteria))
        with held_lock:
            identity = store.create_run(profile, "activity-selection-" + uuid4().hex)
            fence = store.claim(identity)
            candidate = Candidate(domain="activity-fixture.example", url="https://activity-fixture.example/",
                                  name="Labelled activity fixture", query="fixture", provider="fixture")
            store.checkpoint(identity, fence, "discovery", {"candidates": [candidate.model_dump(mode="json")],
                             "selection_policy": 3}, "queued")
        return {"id": identity}

    @application.post("/__fixture_release/{run_id}")
    def release_run(run_id: str):
        with held_lock:
            held_runs[run_id].set()
        return {"fixture": True}

    @application.post("/__fixture_operator_review")
    def annotation(command: OperatorReviewCommand):
        # Isolated browser fixture only; never exposed by the production API.
        return store.annotate(command)

    workspace = create_app(settings)
    # Website-only agent: LABELLED SYNTHETIC providers (shortlist.agent.synthetic), no network and no keys.
    from shortlist.agent.settings import AgentSettings
    from shortlist.agent.synthetic import synthetic_providers
    workspace.state.agent_service.settings = lambda: AgentSettings()
    workspace.state.agent_service.providers = lambda agent_settings: synthetic_providers(pace=0.08)
    # Journeys share one database but are independent, as for the classic flow above: no earlier-search history.
    workspace.state.agent_service.history_days = None
    application.mount("/", workspace)
    try:
        uvicorn.run(application, host="127.0.0.1", port=8015, log_level="warning")
    finally:
        stopped.set()
        with held_lock:
            for hold in held_runs.values():
                hold.set()
        thread.join(timeout=10)
        test_directory.cleanup()
