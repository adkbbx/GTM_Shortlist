import csv
import io
import json

from shortlist.customer_export import HEADERS, customer_tables
from shortlist.domain import Research
from shortlist.market import reviewed_market
from shortlist.relevance import record_issue
from shortlist.workbook import workbook_bytes


def export_run(run: dict, format: str, accepted_only: bool = False) -> str | bytes:
    withheld = [{"reason": reason, "record": r} for r in run["records"]
                if (reason := record_issue(Research.model_validate(r["research"]), strict=True))]
    excluded = {item["record"]["research"]["id"] for item in withheld}
    records = [r for r in run["records"] if r["research"]["id"] not in excluded
               and (not accepted_only or r["review"] and r["review"]["decision"] == "accepted")]
    offer = (run.get("profile") or run["checkpoint"].get("draft") or {}).get("offer", "")
    seller_url = (run.get("profile") or {}).get("seller_url") or run["checkpoint"].get("seller_url", "https://seller.example/")
    reviewed = reviewed_market(run["checkpoint"].get("market"), seller_url, offer)
    market = reviewed.model_dump(mode="json") if reviewed else None
    payload = {"run_id": run["id"], "profile": run["profile"], "status": run["status"],
               "termination": run["checkpoint"].get("termination"),
               "records": records, "withheld_records": withheld, "discovery": run["checkpoint"].get("candidates", []),
               "candidate_failures": run["checkpoint"].get("candidate_failures", {}),
               "page_failures": run["checkpoint"].get("page_failures", {}),
               "activity_failures": run["checkpoint"].get("activity_failures", {}),
               "market": market, "saved_market": run["checkpoint"].get("market"), "campaign_name": run["checkpoint"].get("campaign_name"),
               "selection": run["checkpoint"].get("selection", []), "seller_source": run["checkpoint"].get("seller_source"),
               "discovery_terms": run["checkpoint"].get("discovery_terms"),
               "discovery_failures": run["checkpoint"].get("discovery_failures", {}),
               "used_saved_discovery": run["checkpoint"].get("use_saved_discovery", False),
               "candidate_sources": run["checkpoint"].get("sources", {}),
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
        sheets = [
            ("Shortlist", notes, HEADERS, summary, [24, 30, 25, 45, 50, 35, 22, 35, 40, 40, 45, 28, 28, 36]),
            ("Evidence", ["Evidence and open questions", "Exact saved passages; hypotheses are unverified. Dates are UTC."],
             ["Company", "Type", "Criterion", "Assessment", "Explanation / claim", "Source passage / assumptions",
              "Source URL", "Retrieved (UTC)", "Published (UTC)", "Domain"], details,
             [24, 22, 45, 20, 55, 65, 45, 24, 24, 30]),
        ]
        drafts = []
        for record in records:
            draft = record.get("email_draft")
            if draft:
                research = record["research"]
                person = next((p for p in research.get("people", []) if p["id"] == draft["person_id"]), None)
                sources = {source["id"]: source for source in research["sources"]}
                urls = list(dict.fromkeys(sources[e["source_id"]]["url"] for e in draft["basis"]
                                          if e["source_id"] in sources))
                drafts.append([research["name"], person["name"] + " · " + person["role"] if person else "Company team",
                               draft["subject"], draft["body"], "User edited" if draft["edited"] else "Starting template",
                               "; ".join(urls), draft["updated_at"]])
        if drafts:
            sheets.append(("Email drafts", ["Email drafts · nothing sent",
                "Starting sources do not verify user edits. Add your signature and review before use.",
                "No email address or deliverability claim is supplied."],
                ["Company", "Draft for", "Subject", "Message", "Draft status", "Starting source links", "Updated (UTC)"],
                drafts, [25, 30, 40, 75, 25, 45, 24]))
        if market:
            rows = [[c["domain"], "Potential competitor", c.get("excerpt", "")[:240],
                     "Search observation; offer similarity unverified", c["url"], c["discovered_at"]]
                    for c in market["competitors"]]
            rows.extend([c["name"], "Campaign hypothesis", c["target"][:240], c["rationale"][:240], "", ""]
                        for c in market["campaigns"])
            sheets.append(("Market research", ["Market observations and campaign hypotheses",
                "Search clues are unverified; campaign suggestions need your judgment.",
                "Excerpts shortened for readability. Complete passages and suggestions are in JSON.",
                "Selected direction: " + (run["checkpoint"].get("campaign_name") or "Custom target")],
                ["Company / campaign", "Type", "Excerpt / target", "Context / rationale", "Source URL", "Observed (UTC)"],
                rows, [28, 25, 55, 55, 45, 24]))
        return workbook_bytes(sheets)
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
