"""Labelled synthetic SQLite fixtures for saved-run comparison, with no providers."""
import hashlib
import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

from shortlist.saved_runs import read_only_database


@pytest.fixture
def comparison():
    spec = importlib.util.spec_from_file_location("compare_research_runs", Path(__file__).resolve().parents[1] /
                                                 "scripts/compare_research_runs.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def labelled_database(tmp_path):
    path = tmp_path / "labelled-comparison.sqlite3"
    criteria = [{"id": str(i), "required": True} for i in range(8)] + [{"id": "optional", "required": False}]
    findings = [{"criterion_id": "0", "status": "supported"},
                {"criterion_id": "1", "status": "unknown", "reason": "1: quoted passage could not be found in source"},
                {"criterion_id": "2", "status": "unknown", "reason": "2: the claim is an inference ('may')"},
                {"criterion_id": "3", "status": "unknown", "reason": "Semantic verification unsupported: fixture"},
                {"criterion_id": "4", "status": "unknown", "reason": "No supported observation returned"},
                {"criterion_id": "5", "status": "unknown", "reason": "Labelled fixture unknown"},
                {"criterion_id": "6", "status": "contradicted"},
                {"criterion_id": "optional", "status": "unknown", "reason": "Semantic verification missing"}]
    checkpoint = {"discovery_policy": 3, "candidate_failures": {
        "refused.example": {"reason": "Company identity missing"},
        "prefetch.example": {"reason": "Directory website"}},
        "verification": {"record.example": {"judgments": [{"assessment_id": "criterion:0", "verdict": "entailed"}]}},
        "rejected_quotes": {"record.example": [{"subject": "1", "issue": "duplicate diagnostic"}]}}
    with sqlite3.connect(path) as db:
        db.executescript("CREATE TABLE runs(id TEXT,request_key TEXT,profile TEXT,checkpoint TEXT);"
                         "CREATE TABLE records(run_id TEXT,research TEXT);"
                         "CREATE TABLE attempts(run_id TEXT,kind TEXT,operation_key TEXT,state TEXT);")
        db.execute("INSERT INTO runs VALUES (?,?,?,?)", ("one", "labelled-first", json.dumps({"criteria": criteria}),
                                                       json.dumps(checkpoint)))
        db.execute("INSERT INTO runs VALUES (?,?,?,?)", ("two", "labelled-empty", '{"criteria": []}', '{}'))
        db.execute("INSERT INTO records VALUES (?,?)", ("one", json.dumps({"domain": "record.example",
                   "qualification": "needs_verification", "findings": findings})))
        db.executemany("INSERT INTO attempts VALUES (?,?,?,?)", [
            ("one", "fetch", "fetch:refused.example", "failed"),
            ("one", "model", "model:record.example", "completed"),
            ("one", "model", "verify:record.example", "failed"),
            ("one", "search", "search:1", "completed")])
    return path


def test_compare_research_runs_read_only_counts(comparison, labelled_database, monkeypatch, capsys):
    before = hashlib.sha256(labelled_database.read_bytes()).hexdigest()
    rows = comparison.compare([labelled_database])
    row, empty = rows
    assert row == dict(zip(comparison.COLUMNS, ["labelled-first", 3, 2, 1, 1, 0, 8, 1, 1, 1, 1, 2, 1, 1, 2, 1, 1]))
    assert empty["companies_attempted"] == 0 and empty["discovery_policy"] == 1
    assert sum(row[k] for k in comparison.COLUMNS[7:14]) == row["required_attempted"]
    monkeypatch.setattr("sys.argv", ["compare_research_runs.py", str(labelled_database)])
    comparison.main()
    assert capsys.readouterr().out.strip() == comparison.table(rows)
    assert hashlib.sha256(labelled_database.read_bytes()).hexdigest() == before
    with read_only_database(labelled_database) as db, pytest.raises(sqlite3.OperationalError, match="readonly"):
        db.execute("DELETE FROM runs")


def test_compare_research_runs_requires_verified_support(comparison):
    profile = {"criteria": [{"id": "check", "required": True}]}
    records = [{"domain": "fixture.example", "qualification": "fits", "findings": [
        {"criterion_id": "check", "status": "supported"}]}]
    row = comparison.summarize("labelled-unverified", profile, {}, records, [])
    assert row["required_established"] == 0 and row["verification_missing_unsupported"] == 1
    assert row["fits"] == 1  # Saved qualification, not a reinterpretation of history.


def test_compare_research_runs_missing_database_is_not_created(comparison, tmp_path):
    missing = tmp_path / "missing.sqlite3"
    with pytest.raises(sqlite3.OperationalError):
        comparison.compare([missing])
    assert not missing.exists()


def test_sealed_database_fallback_never_ignores_wal(tmp_path, monkeypatch):
    path = tmp_path / "labelled-sealed.sqlite3"
    path.write_bytes(b"Labelled fixture, not a real database")
    opened = []

    class Unreadable:
        def execute(self, statement):
            raise sqlite3.OperationalError("unable to open database file")

        def close(self):
            pass

    def connect(url, **kwargs):
        assert kwargs == {"uri": True} and "mode=ro" in url
        opened.append(url)
        return Unreadable()

    monkeypatch.setattr("shortlist.saved_runs.sqlite3.connect", connect)
    read_only_database(path)
    assert opened[-1].endswith("?mode=ro&immutable=1")
    Path(str(path) + "-wal").write_bytes(b"Labelled WAL fixture")
    with pytest.raises(sqlite3.OperationalError):
        read_only_database(path)
    assert not opened[-1].endswith("immutable=1")
