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
from ui_test_providers import FixtureModel, FixtureSearch, fixture_fetch

from shortlist.api import create_app
from shortlist.config import Settings
from shortlist.domain import Candidate, OperatorReviewCommand, Profile
from shortlist.fetch import FetchError
from shortlist.local_credentials import LocalCredentials, validate_tavily_key
from shortlist.store import Store
from shortlist.worker import execute_run

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

    application.mount("/", create_app(settings))
    try:
        uvicorn.run(application, host="127.0.0.1", port=8015, log_level="warning")
    finally:
        stopped.set()
        with held_lock:
            for hold in held_runs.values():
                hold.set()
        thread.join(timeout=10)
        test_directory.cleanup()
