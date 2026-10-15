"""Synthetic providers; abruptly exit after a real SQLite outcome commit."""
import argparse
import hashlib
import json
import os
from pathlib import Path

from shortlist.config import Settings
from shortlist.domain import Candidate, Source
from shortlist.providers import validate_extraction
from shortlist.store import Store
from shortlist.verification import Judgment, Verification, assessments
from shortlist.worker import execute_run

parser = argparse.ArgumentParser()
parser.add_argument("db", type=Path)
parser.add_argument("run_id")
parser.add_argument("--crash", choices=("search", "fetch", "model", "verify"))
parser.add_argument("--company-facts", action="store_true")
args = parser.parse_args()
settings = Settings(db_path=args.db)
store = Store(args.db)
calls = args.db.with_suffix(".calls.jsonl")


def count(kind):
    with calls.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"kind": kind}) + "\n")


class Search:
    name = "labelled_crash_fixture"

    def search(self, query, seller_url):
        count("search")
        return [Candidate(domain="fixture.example", name="Labelled crash fixture", url="https://fixture.example",
                          query=query, provider=self.name)]


def fetch(url, expected_domain=None):
    count("fetch")
    text = "Labelled fixture: We offer AI software to businesses as a hosted subscription."
    return Source(url=url, company_domain=expected_domain, title="Synthetic crash fixture", text=text,
                  content_hash=hashlib.sha256(text.encode()).hexdigest())


class Model:
    name = "labelled_crash_fixture"

    def verify(self, profile, record):
        count("verify")
        return Verification(judgments=[Judgment(assessment_id=a["assessment_id"], verdict="entailed",
            reason="Labelled synthetic fixture judgment") for a in assessments(profile, record)])

    def research(self, profile, candidate, sources):
        count("model")
        return validate_extraction({"name": "Labelled crash fixture", "findings": [
            {"status": "supported", "criterion_id": c.id, "evidence": [
                {"source_id": sources[0].id, "passage": sources[0].text, "claim": "AI hosted software"}]}
            for c in profile.criteria],
            "company_facts": [{"kind": "description", "evidence": {"source_id": sources[0].id,
                "passage": sources[0].text, "claim": "AI hosted software for businesses."}}]
                if args.company_facts else []}, profile, candidate.domain, sources)


original = store.outcome


def outcome(attempt_id, state, **kwargs):
    original(attempt_id, state, **kwargs)
    with store.connection() as db:
        kind = db.execute("SELECT kind, operation_key FROM attempts WHERE id=?", (attempt_id,)).fetchone()
    if ("verify" if kind[1].startswith("verify:") else kind[0]) == args.crash:
        os._exit(91)  # No Python cleanup; outcome has already committed.


store.outcome = outcome
execute_run(store, settings, args.run_id, search=Search(), model=Model(), fetch=fetch)
