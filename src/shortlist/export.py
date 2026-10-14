import csv
import io
import json

from shortlist.customer_export import HEADERS, customer_tables
from shortlist.workbook import workbook_bytes


def export_run(run: dict, format: str, accepted_only: bool = False) -> str | bytes:
    records = [r for r in run["records"] if not accepted_only or r["review"] and r["review"]["decision"] == "accepted"]
    payload = {"run_id": run["id"], "profile": run["profile"], "status": run["status"],
               "termination": run["checkpoint"].get("termination"),
               "records": records, "discovery": run["checkpoint"].get("candidates", []),
               "candidate_failures": run["checkpoint"].get("candidate_failures", {}),
               "page_failures": run["checkpoint"].get("page_failures", {}),
               "note": "Human acceptance is not buying intent. Findings are model assessments requiring review."}
    if format == "json":
        return json.dumps(payload, ensure_ascii=False, indent=2)
    summary, details = customer_tables(run, records)
    if format == "xlsx":
        profile = run.get("profile") or {}
        notes = ["GTM Shortlist", "Target: " + profile.get("target", "Not confirmed"),
                 f'{len(records)} companies · {"accepted only" if accepted_only else "all saved records"}',
                 "Human acceptance is not buying intent. Unknown means unverified, not a failed criterion."]
        if run["checkpoint"].get("termination"):
            notes.append("Run stopped by user; completed research retained.")
        return workbook_bytes([
            ("Shortlist", notes, HEADERS, summary, [24, 30, 25, 45, 50, 35, 22, 35, 40, 40]),
            ("Evidence", ["Evidence and open questions", "Exact saved passages; hypotheses are unverified. Dates are UTC."],
             ["Company", "Type", "Criterion", "Assessment", "Explanation / claim", "Source passage / assumptions",
              "Source URL", "Retrieved (UTC)", "Published (UTC)", "Domain"], details,
             [24, 22, 45, 20, 55, 65, 45, 24, 24, 30]),
        ])
    if format != "csv":
        raise ValueError("Choose Excel, CSV or JSON")
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(HEADERS)
    for row in summary:
        cells = row
        cells = ["'" + cell if cell.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else cell for cell in cells]
        # CSV has no row sizing or alignment. Embedded source-link/review-note
        # newlines make Excel expand whole rows, so use one physical line per company.
        cells = ["; ".join(cell.replace("\r\n", "\n").replace("\r", "\n").split("\n")) for cell in cells]
        writer.writerow(cells)
    return "\ufeff" + buffer.getvalue()  # Excel detects UTF-8 names instead of guessing a legacy code page.
