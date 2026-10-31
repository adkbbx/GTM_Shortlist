"""A finished board as CSV for a sales team's own tools: one row per decided company, with the quotes behind it."""
import csv
import io
import re

from shortlist.agent.models import CompanyResult, RunResult

COLUMNS = ["company", "website", "verdict", "reason", "check_before_outreach", "why_now", "opening_line",
           "opening_line_checked", "supporting_quotes", "found_by"]
ORDER = {"shortlisted": 0, "needs_look": 1, "rejected": 2}
LABELS = {"shortlisted": "Shortlisted", "needs_look": "Needs a look", "rejected": "Rejected"}
# Quotes are untrusted page text; a cell a spreadsheet would run as a formula is kept as text.
FORMULA = re.compile(r"^[=+\-@\t\r]")


def cell(value: str) -> str:
    value = " ".join(value.split())
    return "'" + value if FORMULA.match(value) else value


def quotes(company: CompanyResult) -> str:
    decisions = {d.evidence_id: d.decision for d in company.decisions}
    return " | ".join(f'"{e.quote.text}" ({e.quote.url})' for e in company.evidence
                      if decisions.get(e.id) == "supports")


def row(company: CompanyResult) -> list[str]:
    verdict, pitch = company.verdict, company.pitch
    reason = "; ".join(verdict.missing) if verdict.kind == "needs_look" else verdict.summary
    if verdict.disqualifier:
        reason += f' ("{verdict.disqualifier.quote.text}" {verdict.disqualifier.quote.url})'
    return [company.name or company.domain, company.url, LABELS[verdict.kind], reason, "; ".join(verdict.unconfirmed),
            pitch.why_now if pitch else "", pitch.opener if pitch else "",
            ("yes" if pitch.checked else "no") if pitch else "", quotes(company), company.found_via or ""]


def shortlist_csv(run: RunResult) -> str:
    decided = sorted((c for c in run.companies if c.verdict), key=lambda c: ORDER[c.verdict.kind])
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(COLUMNS)
    for company in decided:
        writer.writerow([cell(value) for value in row(company)])
    return out.getvalue()
