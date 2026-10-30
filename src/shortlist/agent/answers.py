"""Shapes the investigator answers in, and the grounding step that turns its quotes into checked Quotes.

A model quote becomes a Quote only when it is found verbatim in a page we fetched. Anything else is logged in the
run's dropped list and never shown.
"""
from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, Field, model_validator

from shortlist.agent.models import DroppedClaim, Quote, SourceType
from shortlist.agent.pages import Page, ground
from shortlist.fetch import FetchError, canonical_url


class Answer(BaseModel):
    model_config = ConfigDict(extra="ignore")


class QuoteAnswer(Answer):
    quote: str = ""
    url: str = ""

    @model_validator(mode="before")
    @classmethod
    def plain_text(cls, value):
        # A model may give a bare string instead of {"quote", "url"}; it is still checked against the pages.
        return {"quote": value} if isinstance(value, str) else value


class StatementAnswer(Answer):
    value: str = ""
    quotes: list[QuoteAnswer] = Field(default_factory=list)


class CriterionAnswer(Answer):
    id: str = ""
    text: str = ""
    required: bool = True
    quotes: list[QuoteAnswer] = Field(default_factory=list)


class SignalAnswer(Answer):
    id: str = ""
    text: str = ""
    quotes: list[QuoteAnswer] = Field(default_factory=list)


class CustomerAnswer(Answer):
    name: str = ""
    domain: str | None = None
    quotes: list[QuoteAnswer] = Field(default_factory=list)


class LimitAnswer(Answer):
    kind: str = ""
    value: str = ""
    quotes: list[QuoteAnswer] = Field(default_factory=list)


class InterpretationAnswer(Answer):
    offer: str = ""
    buyer: str = ""
    quotes: list[QuoteAnswer] = Field(default_factory=list)


class SellerAnswer(Answer):
    name: str = ""
    offer: StatementAnswer | None = None
    buyer: StatementAnswer | None = None
    existing_customers: list[CustomerAnswer] = Field(default_factory=list)
    fit_criteria: list[CriterionAnswer] = Field(default_factory=list)
    need_signals: list[SignalAnswer] = Field(default_factory=list)
    timing_signals: list[SignalAnswer] = Field(default_factory=list)
    stated_limits: list[LimitAnswer] = Field(default_factory=list)
    target_size: StatementAnswer | None = None
    interpretations: list[InterpretationAnswer] = Field(default_factory=list)


class CandidateAnswer(Answer):
    name: str = ""
    domain: str = ""
    url: str = ""
    found_via: str = ""


class CandidatesAnswer(Answer):
    candidates: list[CandidateAnswer] = Field(default_factory=list)


class ClassificationAnswer(Answer):
    domain: str = ""
    name: str = ""
    classification: str = "not_competitor"
    same_job_quote: str | None = None
    same_buyer_quote: str | None = None
    reason: str = ""


class ClassificationsAnswer(Answer):
    competitors: list[ClassificationAnswer] = Field(default_factory=list)


class CompaniesAnswer(Answer):
    companies: list[CandidateAnswer] = Field(default_factory=list)


class EvidenceAnswer(Answer):
    claim_type: str = ""
    criterion_id: str = ""
    claim: str = ""
    quote: str = ""
    url: str = ""
    source_type: str = ""
    published_date: str | None = None


class InvestigationAnswer(Answer):
    company_name: str = ""
    evidence: list[EvidenceAnswer] = Field(default_factory=list)


def page_for(url: str, pages: dict[str, Page]) -> Page | None:
    try:
        key = canonical_url(url)
    except FetchError:
        return None
    if key in pages:
        return pages[key]
    trimmed = key.rstrip("/")
    return next((page for address, page in pages.items() if address.rstrip("/") == trimmed), None)


def ground_quotes(answers: Iterable[QuoteAnswer], pages: dict[str, Page], *, stage: str, dropped: list[DroppedClaim],
                  claim_type: str, source_type: SourceType, company: str | None = None, limit: int = 4) -> list[Quote]:
    """Quotes found in the named page, or else in any page of this set (a model may cite the wrong page)."""
    quotes = []
    for answer in answers:
        named = page_for(answer.url, pages) if answer.url else None
        candidates = [named] if named else []
        candidates += [page for page in pages.values() if page is not named]
        found = None
        for page in candidates:
            if (located := ground(answer.quote, page)) is not None:
                found = (page, *located)
                break
        if found is None:
            dropped.append(DroppedClaim(stage=stage, company=company, claim_type=claim_type, quote=answer.quote[:1500],
                                        url=answer.url[:2048], reason="Quote not found in the fetched page"))
            continue
        page, text, location = found
        quote = Quote(text=text, url=page.url, source_type=source_type, fetched_at=page.fetched_at, location=location)
        if all(existing.text != quote.text for existing in quotes):
            quotes.append(quote)
        if len(quotes) >= limit:
            break
    return quotes


def page_block(page: Page, limit: int) -> str:
    text = page.source.text if len(page.source.text) <= limit else page.source.text[:limit] + "\n[... shortened]"
    return f'<page url="{page.url}">\n{text}\n</page>'
