"""Labelled saved SQLite fixture for the credit-free excerpt check."""
import hashlib
import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

from shortlist.domain import Criterion, Profile, Source


def test_check_saved_excerpts_read_only_with_normalized_quotes(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("check_excerpts", Path(__file__).resolve().parents[1] / "scripts/check_excerpts.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    text = ('Labelled fixture company provides partner training.\n'
            'Channel Partnerships\nLogin\nGlobal\nProducts\nServices\nPartners\nContact\nHelp\n'
            'Our “partner‑training” programme gives every reseller practical support.\n'
            'We do not offer direct sales training to customers.')
    page = Source(id="labelled-source", url="https://fixture.example/", company_domain="fixture.example",
                  title="Labelled fixture", text=text, content_hash=hashlib.sha256(text.encode()).hexdigest())
    profile = Profile(seller_url="https://seller.example/", offer="Partner training", target="Partner training",
                      criteria=(Criterion(id="partners", description="Partner training"),))
    kept = 'Our "partner-training" programme gives every reseller practical support.'
    contradicted = "We do not offer direct sales training to customers."
    record = {"domain": "fixture.example", "findings": [
        {"criterion_id": "partners", "status": "supported", "evidence": [{"passage": kept}]},
        {"criterion_id": "menu", "status": "supported", "evidence": [{"passage": "Channel Partnerships"}]},
        {"criterion_id": "direct", "status": "contradicted", "evidence": [{"passage": contradicted}]},
        {"criterion_id": "unknown", "status": "unknown", "evidence": [{"passage": "Not saved"}]},
        {"criterion_id": "login", "status": "contradicted", "evidence": [{"passage": "Login"}]}]}
    path = tmp_path / "labelled.sqlite3"
    with sqlite3.connect(path) as db:
        db.executescript("CREATE TABLE runs(id TEXT,profile TEXT,checkpoint TEXT); CREATE TABLE records(run_id TEXT,research TEXT);")
        checkpoint = json.dumps({"sources": {"fixture.example": [page.model_dump(mode="json")]}})
        db.execute("INSERT INTO runs VALUES (?,?,?)", ("fixture-run", profile.model_dump_json(), checkpoint))
        db.execute("INSERT INTO runs VALUES (?,?,?)", ("duplicate", profile.model_dump_json(), checkpoint))
        db.execute("INSERT INTO runs VALUES (?,?,?)", ("empty-profile", "{}", "invalid checkpoint skipped"))
        db.execute("INSERT INTO records VALUES (?,?)", ("duplicate", json.dumps(record)))
    connect = sqlite3.connect

    def read_only(url, **kwargs):
        assert url.endswith("?mode=ro") and kwargs == {"uri": True}
        db = connect(url, **kwargs)
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            db.execute("DELETE FROM runs")
        return db

    monkeypatch.setattr(module.sqlite3, "connect", read_only)
    report = module.check([path, path])
    assert report["company_page_sets"] == 1
    row = report["pages"][0]
    assert len(row["runs"]) == 2
    assert row["before"]["chars"] == len(text)
    expected = text.splitlines()[0] + "\n…\n" + "\n".join(text.splitlines()[-2:])
    assert row["after"]["chars"] == len(expected)
    content = sum(len(line) for line in text.splitlines() if len(line.split()) >= 6)
    assert row["before"]["content_chars"] == row["after"]["content_chars"] == content
    assert row["after"]["content_share"] == content / len(expected)
    assert row["after"]["content_share"] > row["before"]["content_share"]
    assert row["missing"] == [
        {"criterion_id": "menu", "status": "supported", "passage": "Channel Partnerships", "sent_before": True},
        {"criterion_id": "login", "status": "contradicted", "passage": "Login", "sent_before": True}]
    assert report["totals"]["before"] == row["before"] and report["totals"]["after"] == row["after"]
    with pytest.raises(sqlite3.OperationalError, match="unable to open database"):
        module.check([tmp_path / "missing.sqlite3"])
    assert not (tmp_path / "missing.sqlite3").exists()
