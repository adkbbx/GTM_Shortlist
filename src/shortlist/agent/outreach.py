"""Stage E: for a Shortlisted company, why now and an opening line, written only from quotes the skeptic supported.

Muse Spark writes; Muse Spark Open, which never sees the web, checks that every sentence states only what those quotes
show. A pitch that claims more is dropped and logged, never shown. Company only: no names, roles or people.
"""
import json
from typing import Literal

from pydantic import Field

from shortlist.agent.answers import Answer
from shortlist.agent.llm import UNTRUSTED, AgentOutputError, Calls
from shortlist.agent.models import CompanyResult, DroppedClaim, Pitch, SellerProfile
from shortlist.agent.providers import AgentProviderError
from shortlist.agent.telemetry import BudgetReached

MAX_QUOTES = 8

INSTRUCTIONS = f"""You write a short, specific reason to contact ONE company now, for a B2B seller. {UNTRUSTED}
Use only the numbered quotes in the data. Every fact you state must be in one of those quotes; do not add numbers,
dates, names, products or reasons that are not there. Describe the company, never a person: no names, no "Hi <name>".
- why_now: one sentence, at most 35 words, on what the company is doing now that makes the seller relevant.
- opener: the first one or two sentences of a cold email from the seller to the company's team, at most 50 words.
  Start from the company's own situation in the quotes, then connect it to the seller's offer in plain words.
  No flattery, no hype, no questions about "a quick call".
Reply with only JSON: {{"why_now": "...", "opener": "...", "quote_ids": ["q1", "..."]}}"""

CHECK = f"""You check a short sales note against quotes. You have no web access; judge only the text given. {UNTRUSTED}
The note is supported only if every factual statement about the company in it is stated or directly implied by the
quotes. Statements about the seller's own offer are allowed if they match seller_offer. Anything else, including
invented numbers, dates, names, products, pains or intentions, makes it unsupported.
Reply with only JSON: {{"decision": "supported|unsupported", "reason": "one sentence"}}"""


class PitchAnswer(Answer):
    why_now: str = ""
    opener: str = ""
    quote_ids: list[str] = Field(default_factory=list)


class PitchCheck(Answer):
    decision: Literal["supported", "unsupported"] = "unsupported"
    reason: str = ""


def write_pitch(company: CompanyResult, profile: SellerProfile, calls: Calls, *, use_skeptic: bool,
                dropped: list[DroppedClaim]) -> Pitch | None:
    """None when there is nothing current to say, the writer fails, or the check finds an unsupported claim."""
    supported = {d.evidence_id for d in company.decisions if d.decision == "supports"}
    items = [e for e in company.evidence if e.id in supported and e.claim_type in ("need", "timing", "fit")]
    items.sort(key=lambda e: e.claim_type == "fit")  # need and timing first: they are the reason to write now
    items = items[:MAX_QUOTES]
    if not any(e.claim_type in ("need", "timing") for e in items):
        return None
    quotes = {f"q{index + 1}": item for index, item in enumerate(items)}
    data = {"seller_offer": profile.offer.value if profile.offer else "",
            "seller_buyer": profile.buyer.value if profile.buyer else "",
            "company": company.name or company.domain,
            "quotes": [{"id": key, "kind": item.claim_type, "quote": item.quote.text, "source": item.quote.source_type,
                        "date": item.quote.published_date.isoformat() if item.quote.published_date else None}
                       for key, item in quotes.items()]}
    try:
        answer, _ = calls.investigator_json("pitch", PitchAnswer, instructions=INSTRUCTIONS, max_output_tokens=2000,
                                            input=[{"role": "user", "content": "<data>\n" + json.dumps(data) + "\n</data>"}])
    except (AgentOutputError, AgentProviderError):
        return None
    why_now, opener = answer.why_now.strip()[:400], answer.opener.strip()[:600]
    used = [quotes[key].id for key in dict.fromkeys(answer.quote_ids) if key in quotes]
    if not why_now or not opener or not used:
        return None
    if not use_skeptic or calls.skeptic is None:
        return Pitch(why_now=why_now, opener=opener, evidence_ids=used, checked=False)
    note = {"seller_offer": data["seller_offer"], "quotes": [quotes[key].quote.text for key in quotes
                                                              if quotes[key].id in used],
            "note": f"{why_now}\n{opener}"}
    try:
        check = calls.skeptic_json("pitch_check", PitchCheck, [
            {"role": "system", "content": CHECK},
            {"role": "user", "content": "<data>\n" + json.dumps(note) + "\n</data>"}], company=company.domain,
            max_tokens=1500)
    except (AgentOutputError, AgentProviderError):
        return None
    if check.decision != "supported":
        dropped.append(DroppedClaim(stage="pitch", company=company.domain, claim_type="pitch",
                                    quote=f"{why_now} | {opener}"[:1500],
                                    reason=f"Skeptic: {check.reason.strip()}"[:600] or "Skeptic found an unsupported claim"))
        return None
    return Pitch(why_now=why_now, opener=opener, evidence_ids=used, checked=True, reason=check.reason.strip()[:600])


def pitch_or_none(company: CompanyResult, profile: SellerProfile, calls: Calls, *, use_skeptic: bool,
                  dropped: list[DroppedClaim]) -> Pitch | None:
    """write_pitch, where a budget stop simply means no pitch."""
    try:
        return write_pitch(company, profile, calls, use_skeptic=use_skeptic, dropped=dropped)
    except BudgetReached:
        return None
