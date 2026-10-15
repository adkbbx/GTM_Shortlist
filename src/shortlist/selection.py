"""Auditable discovery prioritization. Search clues never establish buying intent."""
import re
from datetime import datetime
from urllib.parse import urlsplit

from pydantic import Field

from shortlist.domain import Candidate, Profile, Source, Value
from shortlist.fetch import domain_of
from shortlist.signals import CompanySignal, company_signals


def discussion_page(url: str) -> bool:
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    return (host == "reddit.com" or host.endswith(".reddit.com")) and parsed.path.startswith(("/r/", "/comments/", "/user/"))

STOP = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "business", "businesses", "by", "company", "companies",
    "for", "from", "in", "is", "it", "of", "on", "or", "our", "the", "their", "to", "with", "that", "this",
    "offers", "provides", "offering", "provide", "services", "service",
})
PATTERNS = {
    "Hiring": r"\b(?:we(?:'re| are) hiring|hiring (?:a |an |new )|open positions|join our team)\b",
    "Funding": r"\b(?:raised \$|secured (?:funding|\$)|series [a-d] funding|seed funding|funding round)\b",
    "Product launch": r"\b(?:we(?:'ve| have)? launched|announc(?:e|ed|ing) our|launching (?:our|a new)|introducing our)\b",
    "Expansion": r"\b(?:expanding (?:our|into)|opened (?:a |our )?new|opening (?:a |our )?new)\b",
}


class SearchClue(Value):
    label: str
    passage: str = Field(max_length=3000)
    source_url: str
    observed_at: datetime


class Selection(Value):
    domain: str
    position: int = Field(ge=1)
    target_terms: tuple[str, ...]
    clues: tuple[SearchClue, ...]
    explanation: str
    signals: tuple[CompanySignal, ...] = ()


def terms(text):
    return set(re.findall(r"[\w]+", text.casefold())) - STOP


def prioritize(profile: Profile, candidates: list[Candidate]) -> tuple[list[Candidate], list[Selection]]:
    """Target overlap first, then distinct public event clues; stable on ties.

    Excerpts are untrusted search observations. No freshness, event ownership,
    qualification, or purchase probability is inferred from these matches.
    """
    target = terms(profile.target)
    scored = []
    for candidate in candidates:
        overlap = tuple(sorted(target & terms(candidate.name + " " + candidate.excerpt)))
        clues = []
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", candidate.excerpt):
            if re.search(r"\b(?:not|no|never|isn't|aren't|wasn't|without)\b", sentence, re.IGNORECASE):
                continue
            for label, pattern in PATTERNS.items():
                if label not in {clue.label for clue in clues} and re.search(pattern, sentence, re.IGNORECASE):
                    clues.append(SearchClue(label=label, passage=sentence, source_url=candidate.url,
                                            observed_at=candidate.discovered_at))
        # Events are a tie-breaker only for candidates with an actual target match.
        scored.append((len(overlap), len(clues) if overlap else 0, candidate, overlap, tuple(clues)))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    selections = [Selection(domain=c.domain, position=index + 1, target_terms=overlap, clues=clues,
                            explanation=("Search text mentions " + ", ".join(overlap[:8]) + "."
                                         if overlap else "No direct target wording found in search text; fit needs research."))
                  for index, (_, _, c, overlap, clues) in enumerate(scored)]
    return [item[2] for item in scored], selections


def prioritize_pages(profile: Profile, candidates: list[Candidate], sources: dict[str, tuple[Source, ...]],
                     discovery_terms: str | None = None, preferences=()) -> tuple[list[Candidate], list[Selection]]:
    target = terms(discovery_terms or profile.target)
    rows = []
    for candidate in candidates:
        pages = tuple(page for page in sources.get(candidate.domain, ())
                      if page.company_domain == candidate.domain and domain_of(page.url) == candidate.domain)
        overlap = tuple(sorted(target & terms(candidate.name + " " + " ".join(page.text for page in pages))))
        signals = company_signals(candidate.domain, pages, profile.confirmed_at.date(), preferences)
        relevant = len({signal.label for signal in signals if signal.campaign_relevant})
        rows.append(((bool(pages), min(len(overlap), 2), relevant, len(overlap)), candidate, overlap, signals))
    rows.sort(key=lambda item: item[0], reverse=True)
    selections = [Selection(domain=c.domain, position=i + 1, target_terms=overlap, clues=(), signals=signals,
                  explanation=(f"Saved company pages mention {', '.join(overlap[:8])}. " if overlap else "Target wording needs verification. ")
                  + f"{sum(s.campaign_relevant for s in signals)} dated company statements match the campaign signal types.")
                  for i, (_, c, overlap, signals) in enumerate(rows)]
    return [row[1] for row in rows], selections
