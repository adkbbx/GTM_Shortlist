"""Offline policy 3/4 admission comparison. Saved SQLite evidence is opened read-only.

Search journals contain already-filtered candidates, not raw provider responses. Counts describe only saved evidence;
query groups are observational, never a prediction of results for an unexecuted query. Duplicate databases share runs.
"""
import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path

from scripts.evaluate_discovery import FIXTURE, outcome
from shortlist.domain import Candidate
from shortlist.relevance import candidate_issue, product_target, service_business


def labelled(path: Path = FIXTURE) -> dict:
    results = json.loads(path.read_text(encoding="utf-8"))["results"]
    report = {}
    for policy in (3, 4):
        admitted = [row for row in results if outcome(row, 2, policy)[0] == "research"]
        report[str(policy)] = {
            "admitted": len(admitted),
            "admitted_labelled_service_providers": sum(row.get("service_provider", False) for row in admitted),
            "admitted_labelled_target_companies": sum(row.get("target_company", False) for row in admitted),
            "lost_labelled_target_companies": [row["url"] for row in results if row.get("target_company") and row not in admitted],
        }
    return report


def saved(paths: list[str]) -> dict:
    seen_runs, seen_searches, seen_candidates = set(), set(), set()
    rows, queries = [], []
    for path in paths:
        with sqlite3.connect(f"file:{Path(path).resolve().as_posix()}?mode=ro", uri=True) as db:
            db.row_factory = sqlite3.Row
            for run in db.execute("SELECT id,profile,checkpoint FROM runs WHERE deleted_at IS NULL"):
                if run["id"] in seen_runs:
                    continue
                seen_runs.add(run["id"])
                profile = json.loads(run["profile"] or "{}")
                checkpoint = json.loads(run["checkpoint"] or "{}")
                target = profile.get("target", "")
                if "eygentic.com" not in profile.get("seller_url", checkpoint.get("seller_url", "")) or not product_target(target):
                    continue
                journals = db.execute("SELECT a.operation_key,r.payload FROM attempts a JOIN attempt_results r ON r.attempt_id=a.id "
                                      "WHERE a.run_id=? AND a.kind='search' AND a.operation_key LIKE 'search:%'", (run["id"],)).fetchall()
                groups = [(entry["operation_key"], json.loads(entry["payload"] or "[]")) for entry in journals]
                if not groups:
                    by_query = {}
                    for candidate in checkpoint.get("discovered", checkpoint.get("candidates", [])):
                        by_query.setdefault(candidate.get("query", ""), []).append(candidate)
                    groups = [("checkpoint", values) for values in by_query.values()]
                for operation, values in groups:
                    counts = Counter()
                    query = ""
                    for raw in values:
                        candidate = Candidate.model_validate(raw)
                        query = candidate.query
                        before = candidate_issue(candidate, target=target, policy=3)
                        after = candidate_issue(candidate, target=target, policy=4)
                        counts["saved_results"] += 1
                        counts["admitted_before"] += before is None
                        counts["admitted_after"] += after is None
                        counts["refused:" + (after or "admitted")] += 1
                        key = (target, candidate.query, candidate.url, candidate.name, candidate.excerpt)
                        if key not in seen_candidates:
                            seen_candidates.add(key)
                            rows.append({"domain": candidate.domain, "title": candidate.name, "target": target,
                                         "service_description": service_business(candidate.name, candidate.excerpt),
                                         "before": before, "after": after})
                    key = (query, tuple(value.get("url") for value in values))
                    if key not in seen_searches:
                        seen_searches.add(key)
                        queries.append({"query": query, "operation": operation, "counts": dict(counts)})
    return {"unique_saved_candidates": len(rows),
            "admitted_service_descriptions_before": sum(row["service_description"] and row["before"] is None for row in rows),
            "admitted_service_descriptions_after": sum(row["service_description"] and row["after"] is None for row in rows),
            "queries": queries, "rows": rows,
            "query_change": "None. No saved results for the same generic target under alternative queries establish an improvement."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("databases", nargs="*")
    args = parser.parse_args()
    print(json.dumps({"labelled": labelled(), "saved": saved(args.databases)}, indent=2))


if __name__ == "__main__":
    main()
