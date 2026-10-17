"""Partial seller output is editable without another provider request."""
import json
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from shortlist.api import create_app
from shortlist.config import Settings
from shortlist.domain import Source
from shortlist.prompting import Runtime
from shortlist.providers import Gemma, ModelOutputError, recover_customer_draft
from shortlist.store import Store
from shortlist.worker import execute_run

RECORDED = json.loads((Path(__file__).parents[1] / "examples/evaluation/seller-recovery-rakuten.json").read_text())["response"]
PUBLIC = {"id": "public", "subject": "target_customer", "customer_characteristic": "Sells consumer products through an online store", "required": False}


def test_recorded_response_preserves_summary_and_explains_all_removed_criteria():
    recovered = recover_customer_draft(RECORDED)
    assert recovered.offer == RECORDED["seller_offer"]
    assert recovered.target == RECORDED["target_customer"]
    assert recovered.unknowns == RECORDED["unknowns"]
    assert recovered.criteria == []
    assert len(recovered.criteria_issues) == 6
    assert all("internal needs" in issue.reason for issue in recovered.criteria_issues)
    assert RECORDED["customer_criteria"][0]["customer_characteristic"].startswith("Operates")


def test_keeps_valid_criteria_and_reports_bad_items_individually_without_inventing_replacements():
    raw = {**RECORDED, "customer_criteria": [PUBLIC, PUBLIC, RECORDED["customer_criteria"][2],
          {**PUBLIC, "id": "seller", "subject": "seller"}, "malformed criterion"]}
    before = deepcopy(raw)
    draft = recover_customer_draft(raw)
    assert len(draft.criteria) == 1
    assert draft.criteria[0].id == "public" and not draft.criteria[0].required
    assert draft.criteria[0].description == PUBLIC["customer_characteristic"]
    assert len(draft.criteria_issues) == 4 and raw == before


@pytest.mark.parametrize("change", [{"seller_offer": ""}, {"target_customer": ""}])
def test_missing_summary_fields_still_require_manual_entry(change):
    with pytest.raises(ValidationError):
        recover_customer_draft({**RECORDED, **change})


def test_fresh_worker_saves_editable_summary_with_one_model_call(tmp_path, monkeypatch):
    settings = Settings(db_path=tmp_path / "fresh.sqlite3")
    store = Store(settings.db_path)
    run_id = store.create_draft("https://seller.example/", "recover-fresh")
    model = Gemma(settings)
    model._runtime = Runtime(profile="compact", ollama=False)
    calls = []

    def complete(*args, **kwargs):
        calls.append(1)
        return deepcopy(RECORDED)

    monkeypatch.setattr(model, "complete", complete)
    source = Source(url="https://seller.example/", company_domain="seller.example", title="Labelled fixture",
                    text="Labelled seller source fixture.", content_hash="a" * 64)
    execute_run(store, settings, run_id, model=model, fetch=lambda *args: source)
    saved = store.get_run(run_id)
    assert saved["status"] == "awaiting_confirmation" and saved["error"] is None
    assert saved["checkpoint"]["draft"]["offer"] == RECORDED["seller_offer"]
    assert len(saved["checkpoint"]["draft"]["criteria_issues"]) == 6
    assert saved["profile"] == {} and len(saved["attempts"]) == 2
    assert calls == [1] and all(attempt["state"] == "succeeded" for attempt in saved["attempts"])


@pytest.mark.parametrize("corrupt", [False, True])
def test_existing_failed_response_recovers_read_only_and_empty_criteria_cannot_confirm(tmp_path, monkeypatch, corrupt):
    settings = Settings(db_path=tmp_path / "saved.sqlite3")
    store = Store(settings.db_path)
    run_id = store.create_draft("https://seller.example/", "recover-saved")
    fence = store.claim(run_id)
    checkpoint = store.get_run(run_id)["checkpoint"]
    checkpoint["seller_model_output"] = {"content": "{truncated" if corrupt else json.dumps(RECORDED), "issues": []}
    store.checkpoint(run_id, fence, "confirmation", checkpoint, "awaiting_confirmation", "Gemma output failed validation")
    before = store.get_run(run_id)
    monkeypatch.setattr(Gemma, "complete", lambda *args, **kwargs: pytest.fail("No provider request permitted"))
    client = TestClient(create_app(settings))
    for _ in range(2):
        response = client.get(f"/api/runs/{run_id}")
        assert response.status_code == 200
        view = response.json()
        if corrupt:
            assert view["draft"] is None and "couldn't create" in view["error"]
        else:
            assert view["draft"]["offer"] == RECORDED["seller_offer"]
            assert view["draft"]["criteria"] == []
            assert "recovered" in view["error"] and "No new model call" in view["error"]
    rejected = client.post(f"/api/runs/{run_id}/confirm", json={"offer": RECORDED["seller_offer"],
        "target": RECORDED["target_customer"], "criteria": []})
    assert rejected.status_code == 422
    assert store.get_run(run_id) == before


def test_irrecoverable_model_summary_is_still_reported_without_retry(monkeypatch):
    model = Gemma(Settings())
    model._runtime = Runtime(profile="full", ollama=False)
    calls = []
    def complete(*args, **kwargs):
        calls.append(1)
        return {**RECORDED, "seller_offer": ""}
    monkeypatch.setattr(model, "complete", complete)
    source = Source(url="https://seller.example/", company_domain="seller.example", title="Fixture", text="Fixture source", content_hash="b" * 64)
    with pytest.raises(ModelOutputError):
        model.seller(source)
    assert calls == [1]
