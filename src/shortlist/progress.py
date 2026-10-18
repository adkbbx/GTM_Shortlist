"""Saved observations of actual worker steps, separate from qualification."""
from datetime import datetime
from typing import Literal

from pydantic import Field

from shortlist.domain import Value


class ProgressUpdate(Value):
    phase: Literal["seller", "market", "campaigns", "confirmation", "discovery", "research", "review"]
    label: str = Field(min_length=3, max_length=400)
    state: Literal["started", "succeeded", "failed", "reused", "waiting"]
    detail: str | None = Field(default=None, max_length=400)


class ProgressEvent(ProgressUpdate):
    id: int
    created_at: datetime


class RunProgress(Value):
    worker_online: bool
    candidates: int = Field(ge=0)
    sources: int = Field(ge=0)
    companies: int = Field(ge=0)
    events: tuple[ProgressEvent, ...] = Field(max_length=100)


def low_yield_explanation(run: dict) -> str | None:
    """Use saved discovery facts only. Provider-side filtered results have no saved count."""
    checkpoint = run["checkpoint"]
    if run["status"] not in {"ready", "partial"} or checkpoint.get("termination") or not run.get("profile"):
        return None
    limit = checkpoint.get("company_limit", 3)
    if len(run.get("records", [])) >= limit or "candidates" not in checkpoint:
        return None
    candidates = {candidate["domain"] for candidate in checkpoint["candidates"]}
    if len(candidates) >= limit:
        return None
    searches = [attempt for attempt in run.get("attempts", []) if attempt["kind"] == "search"]
    if not checkpoint.get("completed_queries") and not searches:
        return None
    count = len(candidates)
    message = f"Discovery saved {count} company {'candidate' if count == 1 else 'candidates'} for this target."
    failures = checkpoint.get("candidate_failures", {})
    reasons = [failure.get("reason", "") for failure in failures.values()]
    content = sum(reason.startswith(("Article,", "Editorial title", "List, market report", "Directory or reference",
                                    "Filtered listing", "Video, social")) for reason in reasons)
    services = sum(reason == "Sells services to this market rather than being in it" for reason in reasons)
    details = []
    if content:
        details.append(f"{content} {'page was' if content == 1 else 'pages were'} set aside as articles, lists or reference pages")
    if services:
        details.append(f"{services} service {'provider was' if services == 1 else 'providers were'} set aside")
    previous = len(set(checkpoint.get("previously_researched", [])))
    if previous:
        details.append(f"{previous} already researched {'company was' if previous == 1 else 'companies were'} set aside")
    if details:
        message += " " + "; ".join(details).capitalize() + "."
    elif checkpoint.get("discovery_failures"):
        message += " Some discovery searches could not finish."
    return message


def step_label(kind: str, operation: str, domain: str | None = None) -> str:
    if operation == "market:search":
        return "Exploring potential competitors"
    if operation == "market:campaigns":
        return "Proposing customer campaigns from your offer"
    if operation == "seller:identity":
        return "Looking up your company's website"
    if operation == "seller:fetch":
        return "Reading your company website"
    if operation == "seller:model":
        return "Understanding your offer and proposing a target"
    if kind == "search":
        return "Searching for companies · query " + str(int(operation.split(":")[1]) + 1)
    company = domain or operation.split(":")[1]
    if kind == "fetch":
        if operation.endswith(":activity"):
            return "Reading company news or careers for " + company
        return ("Reading another source page for " if ":page:" in operation else "Reading ") + company
    if operation.startswith("repair:"):
        return "Repairing a structured research response for " + company
    if operation.startswith("verify:"):
        return "Checking that the evidence supports each finding for " + company
    return "Assessing company fit for " + company


def public_events(run: dict, records: list[dict] | None = None) -> tuple[dict, ...]:
    """Explain saved schema failures without exposing model output or changing history."""
    checkpoint = run["checkpoint"]
    diagnostics = {
        step_label("model", "seller:model"): checkpoint.get("seller_model_output"),
        step_label("model", "market:campaigns"): checkpoint.get("market_model_output"),
    }
    for domain, output in checkpoint.get("model_outputs", {}).items():
        diagnostics[step_label("model", "model:" + domain)] = output
        diagnostics[step_label("model", "repair:" + domain)] = output.get("repair_failure")
    eligible = [record for record in (records if records is not None else run.get("records", [])) if not record.get("source_issue")]
    reviewed = sum(bool(record.get("review")) for record in eligible)
    result = []
    for event in run["events"]:
        projected = dict(event)
        diagnostic = diagnostics.get(event["label"])
        if event["state"] == "failed" and event["detail"] == "Gemma output failed validation" and diagnostic:
            issues = diagnostic.get("issues", [])
            if not diagnostic.get("content") and any(issue.get("type") == "json_object_required" for issue in issues):
                projected["detail"] = "The model returned an empty response instead of the required structured output."
            elif any(issue.get("type") == "output_truncated" for issue in issues):
                projected["detail"] = "The model ran out of output space before finishing. This assessment was not completed."
            elif any(issue.get("type") == "missing" for issue in issues):
                projected["detail"] = "The model response was missing required research fields. This assessment was not completed."
        if event.get("phase") == "review" and event["state"] == "waiting" and reviewed:
            projected.update(label=f"Reviewed {reviewed} of {len(eligible)} companies",
                             state="succeeded" if reviewed == len(eligible) else "waiting", detail=None)
        result.append(projected)
    return tuple(result)
