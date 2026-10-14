import hashlib
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from shortlist.api import create_app
from shortlist.config import Settings
from shortlist.domain import Criterion, Profile, Source, utcnow
from shortlist.providers import validate_extraction
from shortlist.store import Conflict, Store


def test_delete_erases_content_but_preserves_spend_and_request_identity(tmp_path):
    store = Store(tmp_path / "deletion.sqlite3")
    profile = Profile(seller_url="https://seller.example/", offer="Private seller offer fixture",
                      target="Business software", criteria=(Criterion(id="software", description="Offers software"),))
    identity = store.create_run(profile, "delete-once")
    with pytest.raises(Conflict):
        store.delete_run(identity)
    fence = store.claim(identity)
    source = Source(url="https://company.example/", company_domain="company.example", title="Deletion fixture",
                    text="Private observed software passage", content_hash=hashlib.sha256(b"fixture").hexdigest())
    store.cache_source(identity, fence, source.url, source)
    attempt = store.reserve(identity, fence, "fixture", "fetch", "fetch:" + source.url)
    store.outcome(attempt, "succeeded", run_id=identity, fence=fence, payload={"private": source.text})
    record = validate_extraction({"name": "Fixture", "findings": [{"criterion_id": "software", "status": "unknown",
                                  "reason": "Fixture has insufficient evidence"}]}, profile, source.company_domain, (source,))
    store.save_record(identity, fence, record)
    store.checkpoint(identity, fence, "complete", {"sources": [source.model_dump(mode="json")]}, "partial")
    client = TestClient(create_app(Settings(db_path=store.path)))
    assert client.delete(f"/api/runs/{identity}").status_code == 204
    assert client.delete(f"/api/runs/{identity}").status_code == 204
    assert client.get(f"/api/runs/{identity}").status_code == 404
    assert client.get(f"/api/runs/{identity}/export").status_code == 404
    assert client.get("/api/runs").json() == []
    assert store.pending_runs() == []
    assert store.claim(identity) is None
    with pytest.raises(Conflict):
        store.create_run(profile, "delete-once")
    with store.connection() as db:
        tombstone = db.execute("SELECT profile,checkpoint,error FROM runs WHERE id=?", (identity,)).fetchone()
        assert tuple(tombstone) == ("{}", "{}", None)
        assert db.execute("SELECT count(*) FROM records").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM source_cache").fetchone()[0] == 0
        result = db.execute("SELECT payload,request_hash FROM attempt_results").fetchone()
        assert tuple(result) == (None, "")
        assert db.execute("SELECT count(*) FROM attempts").fetchone()[0] == 1
    assert client.delete("/api/runs/missing").status_code == 404


def test_deleted_confirmation_cannot_restart_research(tmp_path):
    store = Store(tmp_path / "draft.sqlite3")
    identity = store.create_draft("https://seller.example/", "draft-key")
    store.checkpoint(identity, store.claim(identity), "confirmation", {"seller_url": "https://seller.example/"},
                     "awaiting_confirmation")
    store.delete_run(identity)
    with pytest.raises(Conflict):
        store.create_draft("https://seller.example/", "draft-key")
    profile = Profile(seller_url="https://seller.example/", offer="Private seller offer fixture",
                      target="Business software", criteria=(Criterion(id="software", description="Offers software"),))
    with pytest.raises(KeyError):
        store.confirm_draft(identity, profile)


def test_retention_previews_only_old_inactive_content_and_cli_requires_apply(tmp_path, monkeypatch, capsys):
    from shortlist.cli import main
    settings = Settings(db_path=tmp_path / "retention.sqlite3")
    store = Store(settings.db_path)
    old = store.create_draft("https://old.example/", "old")
    active = store.create_draft("https://active.example/", "active")
    recent = store.create_draft("https://recent.example/", "recent")
    for identity in (old, recent):
        store.checkpoint(identity, store.claim(identity), "confirmation", {"seller_url": "https://fixture.example/"},
                         "awaiting_confirmation")
    with store.connection() as db:
        db.execute("UPDATE runs SET updated_at=? WHERE id IN (?,?)",
                   ((utcnow() - timedelta(days=40)).isoformat(), old, active))
    assert store.retention_candidates(utcnow() - timedelta(days=30)) == [old]
    monkeypatch.setattr("shortlist.cli.Settings.load", lambda: settings)
    monkeypatch.setattr("sys.argv", ["shortlist", "retention", "--older-than-days", "30"])
    main()
    assert '"dry_run": true' in capsys.readouterr().out
    assert store.get_run(old)["status"] == "awaiting_confirmation"
    monkeypatch.setattr("sys.argv", ["shortlist", "retention", "--older-than-days", "30", "--apply"])
    main()
    assert '"dry_run": false' in capsys.readouterr().out
    with pytest.raises(KeyError):
        store.get_run(old)
    assert {run["id"] for run in store.list_runs()} == {active, recent}
    assert store.retention_candidates(utcnow() - timedelta(days=30)) == []
