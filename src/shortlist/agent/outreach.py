"""Stage E: for a Shortlisted company, why now and an opening line, written only from quotes the skeptic supported.

Muse Spark writes; Muse Spark Open, which never sees the web, checks that every sentence states only what those quotes
show. A pitch that claims more is dropped and logged, never shown. Company only: no names, roles or people.
"""
import json
from typing import Literal

from pydantic import Field

from shortlist.agent.answers import Answer
from shortlist.agent.llm import UNTRUSTED, AgentOutputError, Calls
from shortlist.agent.models import (
    CompanyResult,
    DroppedClaim,
    EvidenceItem,
    OutreachEmail,
    Pitch,
    SellerProfile,
)
from shortlist.agent.providers import AgentProviderError
from shortlist.agent.telemetry import BudgetReached

MAX_QUOTES = 8

INSTRUCTIONS = f"""You write a short, specific reason to contact ONE company now, for a B2B seller. {UNTRUSTED}
Use only the numbered quotes in the data. Every fact you state must be in one of those quotes; do not add numbers,
dates, names, products or reasons that are not there. Describe the company, never a person: no names, no "Hi <name>".
- why_now: one sentence, at most 35 words, on what the company is doing now that makes the seller relevant.
- opener: the first one or two sentences of a cold email from the seller to the company's team, at most 50 words.
  Start from the need or timing quote (what the company is doing now), then connect it to the seller's offer in
  plain words. Do not restate the company's product claims or numbers. No flattery, no hype, no "quick call".
A quote whose source is job_post is an open job post: it shows the company is hiring for that role.
Reply with only JSON: {{"why_now": "...", "opener": "...", "quote_ids": ["q1", "..."]}}"""

CHECK = f"""You check a short sales note against quotes. You have no web access; judge only the text given. {UNTRUSTED}
The note is supported only if every factual statement about the company in it is stated or directly implied by the
quotes. A quote from a job_post source is an open job post, so it shows the company is hiring for that role. Statements about the seller's own offer are allowed if they match seller_offer. Anything else, including
invented numbers, dates, names, products, pains or intentions, makes it unsupported.
Reply with only JSON: {{"decision": "supported|unsupported", "reason": "one sentence"}}"""


class PitchAnswer(Answer):
    why_now: str = ""
    opener: str = ""
    quote_ids: list[str] = Field(default_factory=list)


class PitchCheck(Answer):
    decision: Literal["supported", "unsupported"] = "unsupported"
    reason: str = ""


EMAIL = f"""You write a short cold email from a B2B seller to ONE company's team. {UNTRUSTED}
Use only the numbered quotes in the data. Every fact you state about the company must be in one of those quotes; do not
add numbers, dates, names, products or reasons that are not there. Write to the team, never a person: greet
"Hi <company> team,".
- subject: at most 8 words, about what the company is doing now (a need or timing quote). Plain and specific: no
  clickbait, no "quick question", no exclamation marks.
- body: 60 to 110 words in three short paragraphs. 1) What you noticed, from the need or timing quote. 2) How the
  seller's offer helps with exactly that, in plain words. 3) One small ask the team can answer by replying. No
  flattery, no hype, no invented customers or results. End with "Best," and the seller's name on its own line.
- short_message: the same message for LinkedIn, at most 280 characters so it fits a connection note: what you noticed and
  how the seller helps, in one or two sentences, ending with a short question. No greeting and no name, held to the
  same quotes.
A quote whose source is job_post is an open job post: it shows the company is hiring for that role.
Reply with only JSON: {{"subject": "...", "body": "...", "short_message": "...", "quote_ids": ["q1", "..."]}}"""


class EmailAnswer(Answer):
    subject: str = ""
    body: str = ""
    short_message: str = ""
    quote_ids: list[str] = Field(default_factory=list)


LINKEDIN_MAX = 300  # LinkedIn's limit for a connection note


def supported_quotes(company: CompanyResult) -> dict[str, EvidenceItem] | None:
    """Up to MAX_QUOTES supported need, timing and fit quotes, need and timing first; None without a current reason."""
    supported = {d.evidence_id for d in company.decisions if d.decision == "supports"}
    items = [e for e in company.evidence if e.id in supported and e.claim_type in ("need", "timing", "fit")]
    items.sort(key=lambda e: e.claim_type == "fit")  # need and timing first: they are the reason to write now
    items = items[:MAX_QUOTES]
    if not any(e.claim_type in ("need", "timing") for e in items):
        return None
    return {f"q{index + 1}": item for index, item in enumerate(items)}


def checked_note(operation: str, instructions: str, schema: type[Answer], text_of, company: CompanyResult,
                 profile: SellerProfile, calls: Calls, *, use_skeptic: bool, dropped: list[DroppedClaim]):
    """Write a note from the supported quotes, then have Muse Spark Open check it; a rejected note is rewritten once
    with the checker's reason. Returns (answer, quote ids used, checked, reason) or None. text_of(answer) gives the
    note's text, or "" when the answer is incomplete."""
    quotes = supported_quotes(company)
    if quotes is None:
        return None
    data = {"seller_offer": profile.offer.value if profile.offer else "",
            "seller_buyer": profile.buyer.value if profile.buyer else "",
            "seller_name": profile.name or profile.domain,
            "company": company.name or company.domain,
            "quotes": [{"id": key, "kind": item.claim_type, "quote": item.quote.text, "source": item.quote.source_type,
                        "date": item.quote.published_date.isoformat() if item.quote.published_date else None}
                       for key, item in quotes.items()]}
    feedback = ""
    for attempt in range(2):
        content = "<data>\n" + json.dumps(data) + "\n</data>" + (
            f"\nYour previous note was rejected by a checker: {feedback}\nWrite it again using only the quotes."
            if feedback else "")
        try:
            answer, _ = calls.investigator_json(operation + (":rewrite" if attempt else ""), schema,
                                                instructions=instructions, max_output_tokens=2000,
                                                input=[{"role": "user", "content": content}])
        except (AgentOutputError, AgentProviderError):
            return None
        text = text_of(answer)
        used = [quotes[key].id for key in dict.fromkeys(answer.quote_ids) if key in quotes]
        if not text or not used:
            return None
        if not use_skeptic or calls.skeptic is None:
            return answer, used, False, ""
        note = {"seller_offer": data["seller_offer"],
                "quotes": [{"quote": item.quote.text, "source": item.quote.source_type}
                           for item in quotes.values() if item.id in used],
                "note": text}
        try:
            check = calls.skeptic_json(operation + "_check", PitchCheck, [
                {"role": "system", "content": CHECK},
                {"role": "user", "content": "<data>\n" + json.dumps(note) + "\n</data>"}], company=company.domain,
                max_tokens=1500)
        except (AgentOutputError, AgentProviderError):
            return None
        if check.decision == "supported":
            return answer, used, True, check.reason.strip()[:600]
        feedback = check.reason.strip()[:600] or "an unsupported claim"
        dropped.append(DroppedClaim(stage=operation, company=company.domain, claim_type=operation,
                                    quote=text.replace("\n", " | ")[:1500], reason=f"Skeptic: {feedback}"[:600]))
    return None


def write_pitch(company: CompanyResult, profile: SellerProfile, calls: Calls, *, use_skeptic: bool,
                dropped: list[DroppedClaim]) -> Pitch | None:
    """None when there is nothing current to say, the writer fails, or the check finds an unsupported claim."""
    def text_of(answer: PitchAnswer) -> str:
        why_now, opener = answer.why_now.strip()[:400], answer.opener.strip()[:600]
        return f"{why_now}\n{opener}" if why_now and opener else ""
    done = checked_note("pitch", INSTRUCTIONS, PitchAnswer, text_of, company, profile, calls,
                        use_skeptic=use_skeptic, dropped=dropped)
    if done is None:
        return None
    answer, used, checked, reason = done
    return Pitch(why_now=answer.why_now.strip()[:400], opener=answer.opener.strip()[:600], evidence_ids=used,
                 checked=checked, reason=reason)


def write_email(company: CompanyResult, profile: SellerProfile, calls: Calls, *, use_skeptic: bool,
                dropped: list[DroppedClaim]) -> OutreachEmail | None:
    """A subject line and a short cold email, plus the same message for LinkedIn, held to the same quotes and one check
    as the opening line: the checker reads both, so a LinkedIn message is never unchecked."""
    def text_of(answer: EmailAnswer) -> str:
        subject, body = answer.subject.strip()[:120], answer.body.strip()[:1500]
        short = answer.short_message.strip()[:LINKEDIN_MAX]
        if not (subject and body):
            return ""
        return f"Subject: {subject}\n\n{body}" + (f"\n\nLinkedIn message: {short}" if short else "")
    done = checked_note("email", EMAIL, EmailAnswer, text_of, company, profile, calls,
                        use_skeptic=use_skeptic, dropped=dropped)
    if done is None:
        return None
    answer, used, checked, reason = done
    return OutreachEmail(subject=answer.subject.strip()[:120], body=answer.body.strip()[:1500],
                         short_message=answer.short_message.strip()[:LINKEDIN_MAX], evidence_ids=used, checked=checked,
                         reason=reason)


def pitch_or_none(company: CompanyResult, profile: SellerProfile, calls: Calls, *, use_skeptic: bool,
                  dropped: list[DroppedClaim]) -> Pitch | None:
    """write_pitch, where a budget stop simply means no pitch."""
    try:
        return write_pitch(company, profile, calls, use_skeptic=use_skeptic, dropped=dropped)
    except BudgetReached:
        return None
