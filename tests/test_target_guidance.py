"""Labelled saved-target and synthetic edge cases. No providers are used."""
import copy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from shortlist.api import create_app
from shortlist.config import Settings
from shortlist.domain import Criterion, Profile
from shortlist.progress import low_yield_explanation
from shortlist.providers import broad_target
from shortlist.store import Store

SAVED = json.loads((Path(__file__).resolve().parents[1] / "examples/evaluation/target-breadth.json").read_text())


@pytest.mark.parametrize("case", SAVED, ids=[case["label"] for case in SAVED])
def test_labelled_saved_confirmed_targets(case):
    assert broad_target(case["target"]) is case["broad"]


@pytest.mark.parametrize("target,broad", [
    ("B2B and SaaS companies seeking to make their customer acquisition more predictable.", True),
    ("Global digital enterprises", True),
    ("SMB e-commerce software startups", True),
    ("B2B software companies with growing channel partner networks", False),
    ("Software companies using Kubernetes", False),
    ("Software companies focused on healthcare", False),
    ("Sales operations teams within technology companies", False),
    ("Software companies (AI)", False),
    ("Independent coffee roasters that sell wholesale to cafes", False),
    ("B2B SaaS startups seeking predictable growth", True),
    ("", False),
    ("   ", False),
])
def test_breadth_preserves_defining_clauses_roles_and_technologies(target, broad):
    assert broad_target(target) is broad


def saved_run(candidates=1):
    return {"status": "partial", "profile": {"target": "B2B SaaS"}, "records": [], "attempts": [],
            "checkpoint": {"company_limit": 3, "completed_queries": [0, 1, 2],
                           "candidates": [{"domain": f"fixture-{i}.example"} for i in range(candidates)]}}


def test_low_yield_never_invents_filtered_results_or_failures():
    run = saved_run()
    before = copy.deepcopy(run)
    assert low_yield_explanation(run) == "Discovery saved 1 company candidate for this target."
    assert run == before
    assert low_yield_explanation(saved_run(0)) == "Discovery saved 0 company candidates for this target."


def test_low_yield_explains_only_saved_set_aside_reasons():
    run = saved_run()
    run["checkpoint"].update(candidate_failures={
        "article.example": {"reason": "Article, guide, news or directory page; an official company or product page is required"},
        "service.example": {"reason": "Sells services to this market rather than being in it"},
        "unreadable.example": {"reason": "Website connection failed"},
    }, previously_researched=["prior.example", "prior.example"])
    message = low_yield_explanation(run)
    assert "1 page was set aside as articles, lists or reference pages" in message
    assert "1 service provider was set aside" in message
    assert "1 already researched company was set aside" in message
    assert "unreadable" not in message


@pytest.mark.parametrize("change", [
    {"status": "queued"}, {"status": "running"}, {"status": "awaiting_confirmation"}, {"profile": None},
    {"records": [{}, {}, {}]},
])
def test_low_yield_only_for_finished_confirmed_short_batches(change):
    assert low_yield_explanation(saved_run() | change) is None


def test_low_yield_respects_batch_size_and_missing_discovery():
    run = saved_run()
    run["checkpoint"]["company_limit"] = 1
    run["records"] = [{}]
    assert low_yield_explanation(run) is None
    assert low_yield_explanation(saved_run(6)) is None
    run = saved_run()
    del run["checkpoint"]["candidates"]
    assert low_yield_explanation(run) is None
    run = saved_run()
    run["checkpoint"]["completed_queries"] = []
    assert low_yield_explanation(run) is None
    run["checkpoint"]["termination"] = "user_stopped"
    assert low_yield_explanation(run) is None


def test_failed_searches_are_not_described_as_content_rejections():
    run = saved_run(0)
    run["checkpoint"]["discovery_failures"] = {"2": "Labelled interrupted search"}
    assert low_yield_explanation(run).endswith("Some discovery searches could not finish.")


def test_api_guidance_and_review_projection_are_credit_free_and_read_only(tmp_path):
    settings = Settings(db_path=tmp_path / "guidance.sqlite3")
    store = Store(settings.db_path)
    profile = Profile(seller_url="https://seller.example/", offer="Labelled acquisition review service",
                      target="B2B SaaS companies", criteria=(Criterion(id="software", description="Sells software"),))
    identity = store.create_run(profile, "labelled-guidance")
    store.checkpoint(identity, store.claim(identity), "review", saved_run()["checkpoint"], "partial")
    before = store.get_run(identity)
    client = TestClient(create_app(settings))
    for target, broad in [(profile.target, True), ("Private AI B2B SaaS startups", False)]:
        response = client.post("/api/target-guidance", json={"target": target})
        assert response.status_code == 200
        assert response.json() == {"broad": broad}
    assert client.post("/api/target-guidance", json={"target": "x" * 2001}).status_code == 422
    assert client.get(f"/api/runs/{identity}").json()["low_yield_explanation"] == low_yield_explanation(before)
    assert store.get_run(identity) == before
