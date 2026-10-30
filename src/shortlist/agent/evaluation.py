"""Score agent verdicts against labelled companies: agreement, shortlist precision, disqualifier recall, cost and
latency. Labels are CSV rows: domain, expected_verdict (shortlisted|needs_look|rejected), reason, competitor_used."""
import csv
import math
from pathlib import Path

from pydantic import BaseModel, Field

from shortlist.agent.competitors import clean_domain
from shortlist.agent.models import RunResult
from shortlist.agent.skeptic import judge
from shortlist.agent.verdict import decide

VERDICTS = ("shortlisted", "needs_look", "rejected")


class Label(BaseModel):
    domain: str
    expected_verdict: str
    reason: str = ""
    competitor_used: str | None = None


class Row(BaseModel):
    domain: str
    expected: str
    predicted: str | None
    agree: bool
    competitor_used: str | None = None
    rejected_for_competitor: bool | None = None
    latency_ms: int = 0
    cost_usd: float = 0.0


class Report(BaseModel):
    labels: int
    companies: int
    skeptic: bool
    synthetic: bool
    agreement: float | None
    shortlisted_precision: float | None
    disqualifier_recall: float | None
    cost_per_company_usd: float | None
    latency_p50_ms: int | None
    latency_p95_ms: int | None
    total_cost_usd: float
    model_calls: int
    rows: list[Row] = Field(default_factory=list)


def read_labels(path: Path) -> list[Label]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        missing = {"domain", "expected_verdict", "reason"} - set(reader.fieldnames or ())
        if missing:
            raise ValueError("Labels need the columns domain, expected_verdict, reason and optional competitor_used")
        labels = []
        for number, row in enumerate(reader, start=2):
            domain = clean_domain(row.get("domain") or "")
            verdict = (row.get("expected_verdict") or "").strip()
            if domain is None or verdict not in VERDICTS:
                raise ValueError(f"Row {number}: needs a website domain and one of {', '.join(VERDICTS)}")
            used = clean_domain(row.get("competitor_used") or "") if (row.get("competitor_used") or "").strip() else None
            labels.append(Label(domain=domain, expected_verdict=verdict, reason=(row.get("reason") or "").strip(),
                                competitor_used=used))
    if not labels:
        raise ValueError("The labels file has no rows")
    return labels


def batches(labels: list[Label], size: int) -> list[list[Label]]:
    """A run researches at most MAX_COMPANIES companies, so a longer labelled list is researched in batches."""
    return [labels[start:start + size] for start in range(0, len(labels), size)]


def combine(results: list[RunResult]) -> RunResult:
    """One result for scoring from several batch runs: every company, and telemetry summed across the runs. Each
    batch re-reads the seller, so the profile shown is the first batch's."""
    combined = results[0].model_copy(deep=True)
    for part in results[1:]:
        combined.companies += [c for c in part.companies if c.domain not in {k.domain for k in combined.companies}]
        t, extra = combined.telemetry, part.telemetry
        t.calls += extra.calls
        for field in ("cost_usd", "budget_usd", "input_tokens", "output_tokens", "searches", "model_calls",
                      "pages_fetched", "elapsed_ms"):
            setattr(t, field, round(getattr(t, field) + getattr(extra, field), 6))
        t.budget_reached = t.budget_reached or extra.budget_reached
        combined.dropped += part.dropped
        combined.set_aside += part.set_aside
    return combined


def percentile(values: list[int], share: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(share * len(ordered)) - 1)]


def without_skeptic(result: RunResult, today=None) -> RunResult:
    """The ablation over saved evidence: every grounded quote is accepted as supporting, then the same verdict code
    runs. No model calls are made."""
    ablated = result.model_copy(deep=True)
    ablated.skeptic = False
    day = today or (result.finished_at or result.created_at).date()
    for company in ablated.companies:
        if result.profile is None or company.status not in ("done", "budget_reached"):
            continue
        company.decisions = judge(company, ablated.profile, ablated.disqualifiers, None, use_skeptic=False)
        company.verdict = decide(company, ablated.profile, ablated.disqualifiers, day, ablated.overrides.exclusions)
    return ablated


def score(result: RunResult, labels: list[Label]) -> Report:
    companies = {company.domain: company for company in result.companies}
    rows = []
    for label in labels:
        company = companies.get(label.domain)
        predicted = company.verdict.kind if company and company.verdict else None
        rejected_for = None
        if label.competitor_used:
            rule = company.verdict.disqualifier.criterion_id if company and company.verdict and company.verdict.disqualifier else ""
            rejected_for = predicted == "rejected" and rule.endswith(":" + label.competitor_used)
        rows.append(Row(domain=label.domain, expected=label.expected_verdict, predicted=predicted,
                        agree=predicted == label.expected_verdict, competitor_used=label.competitor_used,
                        rejected_for_competitor=rejected_for, latency_ms=company.latency_ms if company else 0,
                        cost_usd=company.cost_usd if company else 0.0))
    shortlisted = [row for row in rows if row.predicted == "shortlisted"]
    competitor_rows = [row for row in rows if row.expected == "rejected" and row.competitor_used]
    researched = [c for c in result.companies if c.status in ("done", "budget_reached")]
    latencies = [c.latency_ms for c in researched]
    return Report(
        labels=len(labels), companies=len(researched), skeptic=result.skeptic, synthetic=result.synthetic,
        agreement=round(sum(row.agree for row in rows) / len(rows), 4) if rows else None,
        shortlisted_precision=round(sum(row.expected == "shortlisted" for row in shortlisted) / len(shortlisted), 4)
        if shortlisted else None,
        disqualifier_recall=round(sum(bool(row.rejected_for_competitor) for row in competitor_rows) / len(competitor_rows), 4)
        if competitor_rows else None,
        cost_per_company_usd=round(result.telemetry.cost_usd / len(researched), 6) if researched else None,
        latency_p50_ms=percentile(latencies, 0.5), latency_p95_ms=percentile(latencies, 0.95),
        total_cost_usd=result.telemetry.cost_usd, model_calls=result.telemetry.model_calls, rows=rows)


def describe(report: Report) -> str:
    def share(value):
        return "n/a" if value is None else f"{value * 100:.0f}%"
    lines = [f"Labelled companies: {report.labels} (researched {report.companies})"
             + (" [SYNTHETIC]" if report.synthetic else "") + ("" if report.skeptic else " [no skeptic]"),
             f"Agreement: {share(report.agreement)}",
             f"Shortlisted precision: {share(report.shortlisted_precision)}",
             f"Disqualifier recall: {share(report.disqualifier_recall)}",
             "Cost per company: " + ("n/a" if report.cost_per_company_usd is None else f"${report.cost_per_company_usd:.4f}"),
             f"Latency p50/p95: {report.latency_p50_ms} ms / {report.latency_p95_ms} ms",
             f"Model calls: {report.model_calls}, total cost ${report.total_cost_usd:.4f}"]
    lines += [f"  {row.domain}: expected {row.expected}, got {row.predicted or 'not researched'}"
              + ("" if row.agree else "  <- differs") for row in report.rows]
    return "\n".join(lines)
