import csv
import io
import json


def export_run(run: dict, format: str, accepted_only: bool = False) -> str:
    records = [r for r in run["records"] if not accepted_only or r["review"] and r["review"]["decision"] == "accepted"]
    payload = {"run_id": run["id"], "profile": run["profile"], "status": run["status"],
               "records": records, "discovery": run["checkpoint"].get("candidates", []),
               "candidate_failures": run["checkpoint"].get("candidate_failures", {}),
               "page_failures": run["checkpoint"].get("page_failures", {}),
               "note": "Human acceptance is not buying intent. Findings are model assessments requiring review."}
    if format == "json":
        return json.dumps(payload, ensure_ascii=False, indent=2)
    if format != "csv":
        raise ValueError("Choose CSV or JSON")
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(["company", "domain", "qualification", "research_status", "review", "findings_json",
                     "sources_json", "hypotheses_json", "unknowns_json", "exclusion_findings_json", "confirmed_profile_json"])
    for record in records:
        research = record["research"]
        cells = [research["name"], research["domain"], research["qualification"], research["status"],
                 record["review"]["decision"] if record["review"] else "unreviewed",
                 *[json.dumps(research[key], ensure_ascii=False) for key in ("findings", "sources", "hypotheses", "unknowns")],
                 json.dumps(research.get("exclusion_findings", []), ensure_ascii=False),
                 json.dumps(run["profile"], ensure_ascii=False)]
        writer.writerow(["'" + cell if cell.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else cell for cell in cells])
    return buffer.getvalue()
