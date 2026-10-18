"""Count saved failure occurrences across read-only SQLite databases. No provider calls."""
import argparse
import json
import re
from contextlib import closing
from pathlib import Path

from shortlist.saved_runs import read_only_database


def group_reason(reason: str) -> str:
    text = re.sub(r"^(?:[\w-]+:\s*|exclusion\s+)", "", reason.casefold().strip(), count=1)
    for prefix in ("quoted passage could not be found", "the claim is an inference", "claim is an inference",
                   "semantic verification missing", "no supported observation returned",
                   "no supported exclusion assessment returned"):
        if text.startswith(prefix):
            return "the claim is an inference" if prefix == "claim is an inference" else prefix
    if text.startswith(("semantic verification unsupported", "semantic verification uncertain")):
        return "Semantic verification unsupported/uncertain"
    if "company identity" in text or text.startswith(("company name cannot", "identity source", "official company identity")):
        return "Company identity"
    if text.startswith(("website", "unsafe", "url", "redirect", "fetched source", "research link", "activity link")):
        return "Fetch errors"
    if any(text.startswith(prefix) for prefix in (
            "page purpose", "article, guide", "directory or reference", "video, social", "public-sector",
            "filtered listing", "recruitment website", "document, feed", "the named company", "primary source",
            "suspended", "company page")):
        return "Page-gate refusals"
    if "citation belongs to" in text:
        return "Unavailable/different-company citation"
    if "required schema" in text or "model output" in text:
        return "Model output/schema errors"
    if text.startswith("not run:"):
        return "Discovery deliberately not run"
    return "Other reason"


def audit(paths: list[Path]) -> dict:
    categories = {}
    stages = dict.fromkeys(("candidate_failures", "page_failures", "activity_failures", "discovery_failures",
                            "rejected_quotes", "unknown_findings"), 0)
    runs = records = 0

    def add(stage, reason, path, run_id, subject):
        category = group_reason(reason)
        if category == "Other reason":
            category = "Other unknown finding" if stage == "unknown_findings" else "Other " + stage
        row = categories.setdefault(category, {"count": 0, "example": {
            "database": str(path), "run_id": run_id, "stage": stage, "subject": subject, "reason": reason}})
        row["count"] += 1
        stages[stage] = stages.get(stage, 0) + 1

    for path in paths:
        with closing(read_only_database(path)) as db:
            for run_id, payload in db.execute("SELECT id,checkpoint FROM runs ORDER BY rowid"):
                runs += 1
                checkpoint = json.loads(payload)
                for stage in ("candidate_failures", "activity_failures", "discovery_failures"):
                    for subject, value in checkpoint.get(stage, {}).items():
                        add(stage, value["reason"] if isinstance(value, dict) else value, path, run_id, subject)
                for domain, failures in checkpoint.get("page_failures", {}).items():
                    for url, reason in failures.items():
                        add("page_failures", reason, path, run_id, domain + ": " + url)
                for domain, quotes in checkpoint.get("rejected_quotes", {}).items():
                    for quote in quotes:
                        add("rejected_quotes", quote["issue"], path, run_id, domain + ": " + quote["subject"])
                for (payload,) in db.execute("SELECT research FROM records WHERE run_id=? ORDER BY rowid", (run_id,)):
                    records += 1
                    record = json.loads(payload)
                    for finding in record.get("findings", []):
                        if finding["status"] == "unknown":
                            add("unknown_findings", finding["reason"], path, run_id,
                                record["domain"] + ": " + finding["criterion_id"])
    return {"databases": len(paths), "runs": runs, "records": records, "occurrences": sum(stages.values()),
            "stages": stages, "categories": dict(sorted(categories.items(), key=lambda item: (-item[1]["count"], item[0])))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("databases", type=Path, nargs="+")
    args = parser.parse_args()
    print(json.dumps(audit(args.databases), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
