"""Conservative dated company statements from saved first-party pages.

These are source claims, never proof of purchasing intent. An explicit date must
occur in the same sentence; retrieval time and copyright years cannot date events.
"""
import re
from datetime import date, datetime
from typing import Literal

from pydantic import Field

from shortlist.domain import Source, Value
from shortlist.fetch import domain_of

PATTERNS = {
    "Hiring": r"\bwe(?: are|'re) hiring\b",
    "Funding": r"\bwe(?: have|'ve)? (?:raised|secured) (?:[$€£]\s?\d|\d[\d,.]* (?:million|billion)\b|funding\b|investment\b|seed funding\b)",
    "Product launch": r"\bwe(?: have|'ve| are|'re)? (?:launched|launching|introduced|introducing)\b",
    "Expansion": r"\bwe(?: have|'ve| are|'re)? (?:(?:expanded|expanding) (?:into|our|to)\b|(?:opened|opening) (?:\w+ ){0,3}(?:office|branch|location|headquarters|facility|store)\b)",
}
MONTHS = {name.casefold(): i for i, name in enumerate(
    ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"), 1)}
MONTH_PATTERN = "(?:" + "|".join(MONTHS) + ")"
DATE_PATTERN = re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b" + MONTH_PATTERN + r" \d{1,2},? \d{4}\b|\b\d{1,2} " + MONTH_PATTERN + r" \d{4}\b", re.IGNORECASE)


class CompanySignal(Value):
    label: Literal["Hiring", "Funding", "Product launch", "Expansion"]
    passage: str = Field(min_length=15, max_length=1500)
    source_id: str
    source_url: str
    event_date: date
    observed_at: datetime
    basis: Literal["Dated company statement"] = "Dated company statement"
    campaign_relevant: bool


def explicit_date(text):
    matches = list(DATE_PATTERN.finditer(text))
    if len(matches) != 1:
        return None  # Ambiguous comparisons and multiple events need human review.
    value = matches[0].group()
    try:
        return date.fromisoformat(value)
    except ValueError:
        pass
    parts = value.replace(",", "").casefold().split()
    try:
        day, month, year = (int(parts[0]), MONTHS[parts[1]], int(parts[2])) if parts[0].isdigit() else (int(parts[1]), MONTHS[parts[0]], int(parts[2]))
        return date(year, month, day)
    except (ValueError, KeyError, IndexError):
        return None


def campaign_labels(preferences):
    words = " ".join(preferences).casefold()
    vocabulary = {"Hiring": ("hiring", "job", "recruit", "sales team"),
                  "Funding": ("funding", "investment", "financing", "raised"),
                  "Product launch": ("launch", "introduced", "new product"),
                  "Expansion": ("expan", "new region", "new market", "new office")}
    return {label for label, needles in vocabulary.items() if any(needle in words for needle in needles)}


def company_signals(domain: str, sources: tuple[Source, ...], as_of: date, preferences=()) -> tuple[CompanySignal, ...]:
    preferred = campaign_labels(preferences) if preferences else set(PATTERNS)
    found = []
    seen = set()
    for source in sources:
        if source.company_domain != domain or domain_of(source.url) != domain:
            continue
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", source.text):
            if not 15 <= len(sentence) <= 1500 or re.search(r"\b(?:not|never|no|isn't|aren't|without)\b|[\"“”]", sentence, re.IGNORECASE):
                continue
            if re.search(r"(?:^|[\s:(])['‘][^'’]*\bwe\b", sentence, re.IGNORECASE):
                continue
            happened = explicit_date(sentence)
            if happened is None or not 0 <= (as_of - happened).days <= 180:
                continue
            for label, pattern in PATTERNS.items():
                match = re.search(pattern, sentence, re.IGNORECASE)
                if not match or re.search(r"\b(?:said|says|according|customer|client|partner)\b", sentence[:match.start()], re.IGNORECASE):
                    continue
                key = (label, happened, sentence)
                if key in seen:
                    continue
                seen.add(key)
                found.append(CompanySignal(label=label, passage=sentence, source_id=source.id, source_url=source.url,
                    event_date=happened, observed_at=source.retrieved_at, campaign_relevant=label in preferred))
                if len(found) == 8:
                    return tuple(found)
    return tuple(found)
