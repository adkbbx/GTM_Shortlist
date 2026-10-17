import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from shortlist.domain import Criterion, Profile, Review
from shortlist.fetch import FetchError
from shortlist.journal import call_step
from shortlist.providers import ModelOutputError, SellerDraft
from shortlist.store import Conflict, Store


@pytest.fixture
def setup(tmp_path):
    store = Store(tmp_path / "journal.sqlite3")
    profile = Profile(seller_url="https://seller.example", offer="Acquisition experiments",
                      target="AI business software", criteria=(Criterion(id="ai", description="AI software"),))
    run_id = store.create_run(profile, "journal-test")
    return store, run_id


@pytest.mark.parametrize("crash,with_facts,with_people", [("search", False, False), ("fetch", False, False),
    ("model", False, False), ("verify", False, False), ("model", True, False), ("verify", True, False),
    ("model", False, True), ("verify", False, True)])
def test_actual_process_death_after_outcome_replays_without_paid_dispatch(setup, crash, with_facts, with_people):
    store, run_id = setup
    fixture = Path(__file__).parent / "fixtures/crash_worker.py"
    command = [sys.executable, str(fixture), str(store.path), run_id]
    if with_facts:
        command.append("--company-facts")
    if with_people:
        command.append("--people")
    first = subprocess.run([*command, "--crash", crash], check=False, timeout=20, capture_output=True)
    assert first.returncode == 91, first.stderr.decode()
    interrupted = Store(store.path).get_run(run_id)
    assert interrupted["status"] == "running"
    assert interrupted["attempts"][-1]["state"] == "succeeded"
    with store.connection() as db:
        db.execute("UPDATE runs SET lease_until=0 WHERE id=?", (run_id,))
    resumed = subprocess.run(command, check=False, timeout=20, capture_output=True)
    assert resumed.returncode == 0, resumed.stderr.decode()
    saved = Store(store.path).get_run(run_id)
    assert saved["status"] == "ready"
    assert len(saved["records"]) == 1
    facts = saved["records"][0]["research"].get("company_facts", [])
    assert len(facts) == int(with_facts)
    if with_facts:
        assert facts[0]["evidence"]["source_id"] == saved["records"][0]["research"]["sources"][0]["id"]
    people = saved["records"][0]["research"].get("people", [])
    assert len(people) == int(with_people)
    if with_people:
        with store.connection() as db:
            payload = json.loads(db.execute("SELECT r.payload FROM attempt_results r JOIN attempts a ON a.id=r.attempt_id "
                "WHERE a.run_id=? AND a.operation_key LIKE 'model:%'", (run_id,)).fetchone()[0])
        assert people == payload["people"]
    calls = [json.loads(line)["kind"] for line in store.path.with_suffix(".calls.jsonl").read_text().splitlines()]
    # One company from two searches is low yield, so discovery policy 2 spends its one extra search.
    assert calls == ["search", "search", "search", "fetch", "model", "verify"]
    assert len(saved["attempts"]) == 6
    store.review(run_id, saved["records"][0]["research"]["id"], Review(decision="accepted", reason="Fixture review"))
    with store.connection() as db:
        db.execute("UPDATE runs SET status='queued' WHERE id=?", (run_id,))
    rerun = subprocess.run(command, check=False, timeout=20, capture_output=True)
    assert rerun.returncode == 0, rerun.stderr.decode()
    assert Store(store.path).get_run(run_id)["records"][0]["review"]["decision"] == "accepted"
    assert store.path.with_suffix(".calls.jsonl").read_text().count("kind") == 6


def test_corrupt_saved_verification_identity_stops_without_redispatch(setup):
    store, run_id = setup
    fixture = Path(__file__).parent / "fixtures/crash_worker.py"
    command = [sys.executable, str(fixture), str(store.path), run_id]
    interrupted = subprocess.run([*command, "--crash", "verify"], check=False, timeout=20, capture_output=True)
    assert interrupted.returncode == 91, interrupted.stderr.decode()
    with store.connection() as db:
        row = db.execute("SELECT r.attempt_id,r.payload FROM attempt_results r JOIN attempts a ON a.id=r.attempt_id "
                         "WHERE a.run_id=? AND a.operation_key LIKE 'verify:%'", (run_id,)).fetchone()
        payload = json.loads(row["payload"])
        payload["judgments"][0]["assessment_id"] = "criterion:invented"
        db.execute("UPDATE attempt_results SET payload=? WHERE attempt_id=?",
                   (json.dumps(payload), row["attempt_id"]))
        db.execute("UPDATE runs SET lease_until=0 WHERE id=?", (run_id,))
    resumed = subprocess.run(command, check=False, timeout=20, capture_output=True)
    assert resumed.returncode == 0, resumed.stderr.decode()
    saved = Store(store.path).get_run(run_id)
    assert saved["status"] == "partial"
    assert not saved["records"]
    assert "does not match this runtime" in saved["error"]
    assert store.path.with_suffix(".calls.jsonl").read_text().count("kind") == 6


def step(store, run_id, fence, function, *, inputs=None, provider="fixture"):
    return call_step(store, run_id, fence, 200, kind="model", provider=provider, operation="seller:model",
                     inputs=inputs or {"fixture": 1}, function=function, decode=SellerDraft.model_validate)


def result():
    return SellerDraft(offer="Labelled fixture offer", target="AI business software", criteria=[
        Criterion(id="ai", description="AI software")])


def test_saved_result_restores_without_executing_and_preserves_values(setup):
    store, run_id = setup
    fence = store.claim(run_id)
    original = step(store, run_id, fence, result)
    restored = step(Store(store.path), run_id, fence, lambda: pytest.fail("Paid dispatch repeated"))
    assert restored == original
    assert len(store.get_run(run_id)["attempts"]) == 1


@pytest.mark.parametrize("failure", (FetchError("Safe fetch failure"), ModelOutputError("malformed fixture", [{"type": "missing"}])))
def test_saved_failure_replays_without_another_attempt(setup, failure):
    store, run_id = setup
    fence = store.claim(run_id)
    def fail():
        raise failure
    with pytest.raises(type(failure)):
        step(store, run_id, fence, fail)
    with pytest.raises(type(failure)) as caught:
        step(store, run_id, fence, lambda: pytest.fail("Failed request repeated"))
    assert str(caught.value) == str(failure)
    if isinstance(failure, ModelOutputError):
        assert caught.value.diagnostic() == failure.diagnostic()
    assert len(store.get_run(run_id)["attempts"]) == 1


def test_changed_inputs_and_provider_stop_replay(setup):
    store, run_id = setup
    fence = store.claim(run_id)
    step(store, run_id, fence, result)
    with pytest.raises(Conflict, match="inputs or provider changed"):
        step(store, run_id, fence, lambda: pytest.fail("Changed input dispatched"), inputs={"fixture": 2})
    with pytest.raises(Conflict, match="inputs or provider changed"):
        step(store, run_id, fence, lambda: pytest.fail("Changed provider dispatched"), provider="other")


def test_uncertain_outcome_never_redispatches(setup):
    store, run_id = setup
    fence = store.claim(run_id)
    class ProcessDeath(BaseException):
        pass
    def uncertain():
        raise ProcessDeath()
    with pytest.raises(ProcessDeath):
        step(store, run_id, fence, uncertain)
    with pytest.raises(Conflict, match="outcome is uncertain"):
        step(Store(store.path), run_id, fence, lambda: pytest.fail("Uncertain request repeated"))
    assert store.get_run(run_id)["attempts"][0]["state"] == "outcome_unknown"


def test_lost_worker_cannot_finalize_or_overwrite_replacement_outcome(setup):
    store, run_id = setup
    fence = store.claim(run_id)
    attempt = store.reserve(run_id, fence, "fixture", "model", "operation")
    with store.connection() as db:
        db.execute("UPDATE runs SET lease_until=0 WHERE id=?", (run_id,))
    replacement = store.claim(run_id)
    with pytest.raises(Conflict, match="lease expired"):
        store.outcome(attempt, "succeeded", run_id=run_id, fence=fence, payload={"bad": "stale"})
    assert store.get_run(run_id)["attempts"][0]["state"] == "outcome_unknown"
    store.outcome(attempt, "failed", run_id=run_id, fence=replacement, payload={"type": "provider", "message": "Unknown"})
    with pytest.raises(Conflict, match="already final"):
        store.outcome(attempt, "succeeded", run_id=run_id, fence=replacement, payload={"bad": "overwrite"})


def test_concurrent_start_only_one_worker_can_dispatch(setup):
    store, run_id = setup
    with ThreadPoolExecutor(max_workers=6) as pool:
        fences = list(pool.map(lambda _: Store(store.path).claim(run_id), range(6)))
    assert sum(fence is not None for fence in fences) == 1


def test_state_and_payload_commit_roll_back_together(setup):
    store, run_id = setup
    fence = store.claim(run_id)
    attempt = store.reserve(run_id, fence, "fixture", "model", "operation")
    with store.connection() as db:
        db.execute("CREATE TRIGGER fixture_abort BEFORE UPDATE ON attempt_results BEGIN SELECT RAISE(ABORT,'fixture'); END")
    import sqlite3
    with pytest.raises(sqlite3.IntegrityError):
        store.outcome(attempt, "succeeded", run_id=run_id, fence=fence, payload={"ok": True})
    assert Store(store.path).get_run(run_id)["attempts"][0]["state"] == "outcome_unknown"


def test_corrupt_saved_result_stops_without_dispatch(setup):
    store, run_id = setup
    fence = store.claim(run_id)
    step(store, run_id, fence, result)
    with store.connection() as db:
        db.execute("UPDATE attempt_results SET payload='broken'")
    with pytest.raises(Conflict, match="result is corrupt"):
        step(store, run_id, fence, lambda: pytest.fail("Corrupt result repeated"))


def test_invalid_failure_shape_stops_without_crashing_or_dispatch(setup):
    store, run_id = setup
    fence = store.claim(run_id)
    def fail():
        raise FetchError("Fixture failure")
    with pytest.raises(FetchError):
        step(store, run_id, fence, fail)
    with store.connection() as db:
        db.execute("UPDATE attempt_results SET payload='{}'")
    with pytest.raises(Conflict, match="failure is corrupt"):
        step(store, run_id, fence, lambda: pytest.fail("Invalid failure repeated"))


def test_pending_jobs_independent_of_latest_100_ui_runs(setup):
    store, oldest = setup
    profile = Profile.model_validate(store.get_run(oldest)["profile"])
    for index in range(101):
        store.create_run(profile, f"later-{index}")
    # Windows clocks can give consecutive inserts the same timestamp. Ordering
    # must preserve queue age even under that real boundary condition.
    with store.connection() as db:
        db.execute("UPDATE runs SET created_at='2026-10-13T19:00:00+00:00'")
    assert oldest not in {r["id"] for r in store.list_runs()}
    assert store.pending_runs()[0] == oldest
    store.claim(oldest)
    assert oldest not in store.pending_runs()
    with store.connection() as db:
        db.execute("UPDATE runs SET lease_until=0 WHERE id=?", (oldest,))
    assert store.pending_runs()[0] == oldest


def test_legacy_attempt_without_journal_stops_safely(setup):
    store, run_id = setup
    fence = store.claim(run_id)
    attempt = store.reserve(run_id, fence, "fixture", "model", "seller:model")
    with store.connection() as db:
        db.execute("DELETE FROM attempt_results WHERE attempt_id=?", (attempt,))
    with pytest.raises(Conflict, match="Legacy attempt"):
        step(store, run_id, fence, lambda: pytest.fail("Legacy request repeated"))
