"""Compare saved research outcomes, not a replay or provider evaluation. No provider calls."""
import argparse
import json
import re
from collections import Counter
from contextlib import closing
from pathlib import Path

from shortlist.saved_runs import read_only_database

COLUMNS = ("run_key", "discovery_policy", "companies_attempted", "companies_refused", "records_saved", "fits",
           "required_attempted", "required_established", "quote_not_found", "hedge_inference",
           "verification_missing_unsupported", "no_observation", "other_unknown", "contradicted",
           "model_calls", "fetches", "searches")


def cause(reason: str) -> str:
    text = re.sub(r"^[\w-]+:\s*", "", reason.casefold().strip(), count=1)
    if text.startswith("quoted passage could not be found"):
        return "quote_not_found"
    if text.startswith(("the claim is an inference", "claim is an inference")):
        return "hedge_inference"
    if text.startswith("semantic verification"):
        return "verification_missing_unsupported"
    if text.startswith("no supported observation returned"):
        return "no_observation"
    return "other_unknown"


def summarize(run_key: str, profile: dict, checkpoint: dict, records: list[dict], attempts: list[dict]) -> dict:
    """Count each required finding once. Refusals require saved evidence that research began."""
    domains = {record["domain"] for record in records}
    begun = set(checkpoint.get("sources", {}))
    for attempt in attempts:
        parts = attempt["operation_key"].split(":")
        if attempt["kind"] in ("fetch", "model") and len(parts) > 1:
            begun.add(parts[1])
    refused = (set(checkpoint.get("candidate_failures", {})) & begun) - domains
    required = {criterion["id"] for criterion in profile["criteria"] if criterion.get("required", True)}
    counts = Counter({key: 0 for key in COLUMNS[8:14]})
    established = 0
    for record in records:
        findings = {finding["criterion_id"]: finding for finding in record.get("findings", [])}
        judgments = {j["assessment_id"]: j["verdict"] for j in
                     checkpoint.get("verification", {}).get(record["domain"], {}).get("judgments", [])}
        for criterion in required:
            finding = findings.get(criterion)
            if finding is None:
                counts["no_observation"] += 1
            elif finding["status"] == "supported":
                if judgments.get("criterion:" + criterion) == "entailed":
                    established += 1
                else:
                    counts["verification_missing_unsupported"] += 1
            elif finding["status"] == "contradicted":
                counts["contradicted"] += 1
            else:
                counts[cause(finding.get("reason", ""))] += 1
    calls = Counter(attempt["kind"] for attempt in attempts)
    return {"run_key": run_key, "discovery_policy": checkpoint.get("discovery_policy", 1),
            "companies_attempted": len(domains | refused), "companies_refused": len(refused),
            "records_saved": len(records), "fits": sum(record["qualification"] == "fits" for record in records),
            "required_attempted": len(records) * len(required), "required_established": established, **counts,
            "model_calls": calls["model"], "fetches": calls["fetch"], "searches": calls["search"]}


def compare(paths: list[Path]) -> list[dict]:
    rows = []
    for path in paths:
        with closing(read_only_database(path)) as db:
            for run_id, key, profile, checkpoint in db.execute(
                    "SELECT id,request_key,profile,checkpoint FROM runs ORDER BY rowid"):
                records = [json.loads(row[0]) for row in db.execute(
                    "SELECT research FROM records WHERE run_id=? ORDER BY rowid", (run_id,))]
                attempts = [{"kind": kind, "operation_key": key} for kind, key in db.execute(
                    "SELECT kind,operation_key FROM attempts WHERE run_id=? ORDER BY rowid", (run_id,))]
                rows.append(summarize(key, json.loads(profile), json.loads(checkpoint), records, attempts))
    return rows


def table(rows: list[dict]) -> str:
    return "\n".join(["| " + " | ".join(COLUMNS) + " |", "|" + "---|" * len(COLUMNS),
                      *("| " + " | ".join(str(row[key]) for key in COLUMNS) + " |" for row in rows)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("databases", type=Path, nargs="+")
    print(table(compare(parser.parse_args().databases)))


if __name__ == "__main__":
    main()
