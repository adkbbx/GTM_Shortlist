"""Labelled SQLite fixtures for the offline failure audit."""
import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest


@pytest.fixture
def auditor():
    spec = importlib.util.spec_from_file_location("audit_failures", Path(__file__).resolve().parents[1] / "scripts/audit_failures.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("reason,category", [
    ("C1_1: quoted passage could not be found in source", "quoted passage could not be found"),
    ("Exclusion quoted passage could not be found in source", "quoted passage could not be found"),
    ("software: the claim is an inference ('suggests'), not stated", "the claim is an inference"),
    ("Exclusion claim is an inference ('likely')", "the claim is an inference"),
    ("Semantic verification missing", "semantic verification missing"),
    ("Semantic verification unsupported: Fixture contradiction", "Semantic verification unsupported/uncertain"),
    ("Semantic verification uncertain: Fixture ambiguity", "Semantic verification unsupported/uncertain"),
    ("software: Semantic verification uncertain: Fixture ambiguity", "Semantic verification unsupported/uncertain"),
    ("Semantic verification unsupported: quoted passage could not be found", "Semantic verification unsupported/uncertain"),
    ("No supported observation returned", "no supported observation returned"),
    ("No supported exclusion assessment returned", "no supported exclusion assessment returned"),
    ("Company identity passage was not found in the saved page", "Company identity"),
    ("Official company identity was not independently verified; record withheld", "Company identity"),
    ("Company name cannot be tied to the source website owner", "Company identity"),
    ("Website returned HTTP 403", "Fetch errors"),
    ("Website connection failed", "Fetch errors"),
    ("Website page exceeds byte limit", "Fetch errors"),
    ("Page purpose is not established as an official company, product or service page", "Page-gate refusals"),
    ("Article, guide, news or directory page; an official company or product page is required", "Page-gate refusals"),
    ("Directory or reference website; not an official candidate company page", "Page-gate refusals"),
    ("C1_1: citation belongs to an unavailable or different company source", "Unavailable/different-company citation"),
    ("Company research did not match the required schema", "Model output/schema errors"),
    ("Not run: labelled fixture search disabled", "Discovery deliberately not run"),
    ("Labelled fixture has no ownership evidence", "Other reason"),
])
def test_audit_group_reason_has_stable_categories(auditor, reason, category):
    assert auditor.group_reason(reason) == category


@pytest.fixture
def labelled_database(tmp_path):
    path = tmp_path / "labelled-failures.sqlite3"
    checkpoint = {
        "candidate_failures": {
            "fixture.example": {"url": "https://fixture.example/", "reason": "Company identity passage was not found in the saved page"},
            "refused.example": {"reason": "Page purpose is not established as an official company, product or service page"}},
        "page_failures": {"fixture.example": {"https://fixture.example/about": "Website connection failed"}, "empty.example": {}},
        "activity_failures": {"fixture.example": {"url": "https://fixture.example/news", "reason": "Website returned HTTP 403"}},
        "discovery_failures": {"2": "Not run: labelled fixture search disabled"},
        "rejected_quotes": {"fixture.example": [{"subject": "software", "passage": "Labelled fixture unsaved quote",
                                                  "issue": "quoted passage could not be found in source"}]}}
    record = {"domain": "fixture.example", "findings": [
        {"criterion_id": "software", "status": "unknown", "reason": "software: quoted passage could not be found in source"},
        {"criterion_id": "ownership", "status": "unknown", "reason": "Labelled fixture has no ownership evidence"},
        {"criterion_id": "ignored", "status": "supported"}]}
    with sqlite3.connect(path) as db:
        db.executescript("CREATE TABLE runs(id TEXT,checkpoint TEXT); CREATE TABLE records(run_id TEXT,research TEXT);")
        db.execute("INSERT INTO runs VALUES (?,?)", ("labelled-one", json.dumps(checkpoint)))
        db.execute("INSERT INTO runs VALUES (?,?)", ("labelled-empty", "{}"))
        db.execute("INSERT INTO records VALUES (?,?)", ("labelled-one", json.dumps(record)))
    return path


def test_audit_reads_all_runs_and_stages_without_writing(auditor, labelled_database, monkeypatch, capsys):
    before = labelled_database.read_bytes()
    connect = sqlite3.connect
    opened = []

    def read_only(url, **kwargs):
        assert url == "file:" + str(labelled_database) + "?mode=ro" and kwargs == {"uri": True}
        opened.append(url)
        return connect(url, **kwargs)

    monkeypatch.setattr(auditor.sqlite3, "connect", read_only)
    report = auditor.audit([labelled_database, labelled_database])
    assert report["databases"] == 2 and report["runs"] == 4 and report["records"] == 2
    assert report["occurrences"] == 16
    assert report["stages"] == {"candidate_failures": 4, "page_failures": 2, "activity_failures": 2,
                                "discovery_failures": 2, "rejected_quotes": 2, "unknown_findings": 4}
    assert report["categories"]["Fetch errors"]["count"] == 4
    assert report["categories"]["quoted passage could not be found"]["count"] == 4
    example = report["categories"]["Company identity"]["example"]
    assert example == {"database": str(labelled_database), "run_id": "labelled-one", "stage": "candidate_failures",
                       "subject": "fixture.example", "reason": "Company identity passage was not found in the saved page"}
    assert report["categories"]["Other unknown finding"]["count"] == 2
    monkeypatch.setattr("sys.argv", ["audit_failures.py", str(labelled_database), str(labelled_database)])
    auditor.main()
    assert json.loads(capsys.readouterr().out) == report
    assert len(opened) == 4 and labelled_database.read_bytes() == before


def test_audit_missing_database_is_not_created(auditor, tmp_path):
    missing = tmp_path / "missing.sqlite3"
    with pytest.raises(sqlite3.OperationalError, match="unable to open database"):
        auditor.audit([missing])
    assert not missing.exists()
