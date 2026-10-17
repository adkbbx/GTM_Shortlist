"""Classify saved discovery URLs without fetching pages, invoking models or writing the database."""
import argparse
import json
import sqlite3
from pathlib import Path

from shortlist.domain import Candidate, Research, Source
from shortlist.relevance import candidate_issue, company_page_issue, primary_source_issue, record_issue


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path("data/shortlist.sqlite3"))
    parser.add_argument("--run", help="exact saved run ID")
    args = parser.parse_args()
    report = []
    with sqlite3.connect(args.database.resolve().as_uri() + "?mode=ro", uri=True) as database:
        for identity, raw in database.execute("SELECT id,checkpoint FROM runs WHERE deleted_at IS NULL ORDER BY created_at"):
            if args.run and identity != args.run:
                continue
            checkpoint = json.loads(raw)
            candidates = []
            for raw_candidate in checkpoint.get("candidates", []):
                candidate = Candidate.model_validate(raw_candidate)
                issue = candidate_issue(candidate)
                pages = checkpoint.get("sources", {}).get(candidate.domain, [])
                if not issue and pages:
                    issue = primary_source_issue(Source.model_validate(pages[0]), strict=True)
                candidates.append({"domain": candidate.domain, "url": candidate.url,
                                   "decision": "skip" if issue else "eligible_for_research", "reason": issue})
            records = []
            for (research,) in database.execute("SELECT research FROM records WHERE run_id=?", (identity,)):
                record = Research.model_validate_json(research)
                issue = record_issue(record, strict=True)
                records.append({"domain": record.domain, "reason": issue, "decision": "withhold" if issue else "retain"})
            market = [{"domain": value["domain"], "reason": candidate_issue(Candidate.model_validate(value)) or
                       company_page_issue(value["url"], value["name"], strict=True)}
                      for value in checkpoint.get("market_candidates", [])]
            report.append({"run_id": identity, "candidates": candidates, "records": records, "market": market})
    if args.run and not report:
        parser.error("Saved run not found")
    print(json.dumps({"runs": report, "provider_calls": 0, "database_writes": 0}, indent=2))


if __name__ == "__main__":
    main()
