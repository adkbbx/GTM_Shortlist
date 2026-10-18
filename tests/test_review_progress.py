"""Review progress follows saved human decisions, independently of qualification."""
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from scripts.ui_test_providers import FixtureModel, FixtureSearch, fixture_fetch
from shortlist.api import create_app
from shortlist.config import Settings
from shortlist.domain import Profile
from shortlist.progress import public_events
from shortlist.store import Store
from shortlist.worker import execute_run


def test_review_api_projects_partial_and_complete_progress_without_rewriting_history(tmp_path):
    settings = Settings(db_path=tmp_path / "labelled-review.sqlite3")
    store = Store(settings.db_path)
    draft = FixtureModel().seller(None)
    profile = Profile(seller_url="https://seller.example/", offer=draft.offer, target=draft.target, criteria=tuple(draft.criteria))
    identity = store.create_run(profile, "labelled-review")
    execute_run(store, settings, identity, search=FixtureSearch(), model=FixtureModel(), fetch=fixture_fetch)
    before = store.get_run(identity)
    client = TestClient(create_app(settings))
    for index, record in enumerate(before["records"]):
        response = client.post(f"/api/runs/{identity}/records/{record['research']['id']}/review",
                               json={"decision": "accepted" if index == 0 else "rejected", "reason": "Labelled human decision"})
        assert response.status_code == 200
        event = response.json()["progress"]["events"][-1]
        assert event["label"] == f"Reviewed {index + 1} of 2 companies"
        assert event["state"] == ("succeeded" if index == 1 else "waiting")
    after = store.get_run(identity)
    assert after["events"] == before["events"]
    assert [r["research"] for r in after["records"]] == [r["research"] for r in before["records"]]
    assert client.get(f"/api/runs/{identity}").json()["progress"]["events"][-1]["state"] == "succeeded"


@pytest.mark.parametrize("records,expected", [
    ([], "waiting"),
    ([{"source_issue": "Historical invalid source", "review": {"decision": "accepted"}}], "waiting"),
    ([{"review": {"decision": "needs_research"}}, {"source_issue": "Historical invalid source", "review": None}], "succeeded"),
])
def test_only_eligible_saved_companies_count(records, expected):
    run = {"checkpoint": {}, "events": [{"phase": "review", "label": "Saved companies for your review", "state": "waiting"}]}
    before = deepcopy(run)
    assert public_events(run, records)[-1]["state"] == expected
    assert run == before
