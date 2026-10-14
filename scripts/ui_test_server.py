"""Labelled synthetic providers for browser tests of the real API/worker/database.

Never use this as the live application server. It performs no company discovery.
"""

import os
import tempfile
import threading
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from ui_test_providers import FixtureModel, FixtureSearch, fixture_fetch

from shortlist.api import create_app
from shortlist.config import Settings
from shortlist.domain import OperatorReviewCommand
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


def loop():
    while not stopped.is_set():
        store.worker_heartbeat("labelled_browser_fixture")
        for run in store.list_runs():
            if run["status"] in ("queued", "running"):
                execute_run(
                    store,
                    settings,
                    run["id"],
                    search=FixtureSearch(),
                    model=FixtureModel(),
                    fetch=fixture_fetch,
                )
        stopped.wait(0.1)


if __name__ == "__main__":
    thread = threading.Thread(target=loop, daemon=True)
    thread.start()
    application = FastAPI()

    @application.post("/__fixture_operator_review")
    def annotation(command: OperatorReviewCommand):
        # Isolated browser fixture only; never exposed by the production API.
        return store.annotate(command)

    application.mount("/", create_app(settings))
    try:
        uvicorn.run(application, host="127.0.0.1", port=8015, log_level="warning")
    finally:
        stopped.set()
        thread.join(timeout=10)
        test_directory.cleanup()
