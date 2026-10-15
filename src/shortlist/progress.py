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
