"""Labelled synthetic providers for browser tests of the real API/worker/database.

Never use this as the live application server. It performs no company discovery.
"""

import os
import threading
import time
from pathlib import Path

import uvicorn
from ui_test_providers import FixtureModel, FixtureSearch, fixture_fetch

from shortlist.api import create_app
from shortlist.config import Settings
from shortlist.store import Store
from shortlist.worker import execute_run

settings = Settings(
    db_path=Path(os.environ.get("SHORTLIST_UI_TEST_DB", "data/ui-test.sqlite3")),
    tavily_key="labelled_fixture_not_a_real_key",
    gemma_base_url="https://labelled-fixture.example",
    gemma_model="labelled_fixture",
)
store = Store(settings.db_path)


def loop():
    while True:
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
        time.sleep(0.1)


if __name__ == "__main__":
    threading.Thread(target=loop, daemon=True).start()
    uvicorn.run(create_app(settings), host="127.0.0.1", port=8015, log_level="warning")
