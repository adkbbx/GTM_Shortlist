import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from shortlist.api import create_app
from shortlist.config import Settings
from shortlist.domain import Criterion, OperatorReviewCommand, Profile, Research, Review, Source
from shortlist.export import export_run
from shortlist.review_queue import review_queue
from shortlist.store import Conflict, Store


def test_operator_triage_is_read_only_and_customer_acceptance_is_separate(tmp_path, monkeypatch, capsys):
    from shortlist.cli import main
    settings = Settings(db_path=tmp_path / "queue.sqlite3")
    store = Store(settings.db_path)
    profile = Profile(seller_url="https://seller.example/", offer="Labelled research service",
                      target="Business software", criteria=(Criterion(id="software", description="Offers software"),))
    identity = store.create_run(profile, "queue-fixture")
    fence = store.claim(identity)
    research = Research(domain="company.example", name="Labelled triage fixture", profile_id=profile.id,
                        findings=(), sources=(), qualification="needs_verification", status="partial",
                        unknowns=("No readable sources were available in this fixture",))
    store.save_record(identity, fence, research, billable=False)
    store.checkpoint(identity, fence, "complete", {}, "partial")
    before = store.get_run(identity)
    queue = review_queue(store)
    assert len(queue) == 1 and queue[0]["research"]["id"] == research.id
    assert queue[0]["operator_review"] is None and queue[0]["customer_review"] is None
    assert store.get_run(identity) == before
    store.review(identity, research.id, Review(decision="accepted", reason="Labelled customer decision"))
    assert review_queue(store)[0]["customer_review"]["decision"] == "accepted"
    store.review(identity, research.id, Review(decision="needs_research", reason="Missing sources"))
    monkeypatch.setattr("shortlist.cli.Settings.load", lambda: settings)
    monkeypatch.setattr("sys.argv", ["shortlist", "review-queue"])
    main()
    output = json.loads(capsys.readouterr().out)
    assert output[0]["customer_review"]["decision"] == "needs_research"
    assert output[0]["operator_review"] is None
    store.delete_run(identity)
    assert review_queue(store) == []


def completed_sheet(store):
    profile = Profile(seller_url="https://seller.example/", offer="Labelled review test service",
                      target="Business software", criteria=(Criterion(id="software", description="Offers software"),))
    identity = store.create_run(profile, "operator-fixture")
    fence = store.claim(identity)
    source = Source(url="https://company.example/", company_domain="company.example", title="Labelled operator fixture",
                    text="TEST FIXTURE. Company offers software.", content_hash="fixture-hash")
    research = Research(domain="company.example", name="Operator test fixture", profile_id=profile.id,
                        findings=(), sources=(source,), qualification="needs_verification", status="partial")
    store.cache_source(identity, fence, source.url, source)
    store.save_record(identity, fence, research, billable=False)
    store.checkpoint(identity, fence, "complete", {}, "partial")
    return identity, research


def review_command(identity, research, **changes):
    payload = {"run_id": identity, "record_id": research.id, "request_key": "operator-note-one", "previous_id": None,
               "annotation": {"outcome": "reviewed", "reviewer": "Labelled fixture reviewer",
                              "note": "Inspected the supplied fixture. Ownership remains unknown.",
                              "source_ids": [research.sources[0].id]}}
    payload.update(changes)
    return OperatorReviewCommand.model_validate(payload)


def test_operator_history_is_independent_immutable_replay_safe_and_deleted(tmp_path):
    store = Store(tmp_path / "notes.sqlite3")
    identity, research = completed_sheet(store)
    before = store.get_run(identity)["records"][0]
    store.review(identity, research.id, Review(decision="accepted", reason="Customer fixture decision"))
    command = review_command(identity, research)
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: store.annotate(command), range(6)))
    first = results[0]
    assert {item["id"] for item in results} == {first["id"]}
    assert review_queue(store) == []
    after = store.get_run(identity)["records"][0]
    assert after["research"] == before["research"]
    assert after["review"]["decision"] == "accepted"
    assert after["operator_review"] == first
    client = TestClient(create_app(Settings(db_path=store.path)))
    assert client.get(f"/api/runs/{identity}").json()["records"][0]["operator_review"] == first
    with pytest.raises(Conflict, match="different inputs"):
        store.annotate(review_command(identity, research, previous_id=first["id"]))
    with pytest.raises(Conflict, match="changed"):
        store.annotate(review_command(identity, research, request_key="operator-stale-note"))
    followup = review_command(identity, research, request_key="operator-followup", previous_id=first["id"],
                             annotation={"outcome": "needs_research", "reviewer": "Second fixture reviewer",
                                         "note": "A separate ownership source still needs inspection.", "source_ids": []})
    second = store.annotate(followup)
    assert second["research_hash"] == first["research_hash"]
    assert store.operator_history(identity, research.id) == [second, first]
    assert review_queue(store)[0]["operator_review"] == second
    exported = json.loads(export_run(store.get_run(identity), "json", accepted_only=True))
    assert exported["records"][0]["operator_review"] == second
    assert "Service review" in export_run(store.get_run(identity), "csv")
    assert "A separate ownership source still needs inspection." in export_run(store.get_run(identity), "csv")
    store.delete_run(identity)
    with store.connection() as db:
        assert db.execute("SELECT count(*) FROM operator_reviews").fetchone()[0] == 0
    with pytest.raises(KeyError):
        store.annotate(command)


def test_operator_cli_and_source_validation(tmp_path, monkeypatch, capsys):
    from shortlist.cli import main
    settings = Settings(db_path=tmp_path / "cli.sqlite3")
    store = Store(settings.db_path)
    identity, research = completed_sheet(store)
    command = review_command(identity, research)
    invalid = command.model_dump(mode="json")
    invalid["annotation"]["source_ids"] = []
    with pytest.raises(ValidationError):
        OperatorReviewCommand.model_validate(invalid)
    invalid["annotation"]["source_ids"] = ["foreign-source"]
    with pytest.raises(ValueError, match="outside"):
        store.annotate(OperatorReviewCommand.model_validate(invalid))
    path = tmp_path / "review.json"
    path.write_text(command.model_dump_json(), encoding="utf-8")
    monkeypatch.setattr("shortlist.cli.Settings.load", lambda: settings)
    monkeypatch.setattr("sys.argv", ["shortlist", "annotate", str(path)])
    main()
    review = json.loads(capsys.readouterr().out)
    monkeypatch.setattr("sys.argv", ["shortlist", "review-history", identity, research.id])
    main()
    assert json.loads(capsys.readouterr().out) == [review]


def test_simultaneous_operator_corrections_require_latest_history(tmp_path):
    store = Store(tmp_path / "race.sqlite3")
    identity, research = completed_sheet(store)

    def append(index):
        try:
            return store.annotate(review_command(identity, research, request_key=f"reviewer-race-{index}"))
        except Conflict:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(append, range(2)))
    assert sum(result is not None for result in results) == 1
    assert len(store.operator_history(identity, research.id)) == 1
