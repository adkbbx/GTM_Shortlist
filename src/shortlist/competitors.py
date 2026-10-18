"""Policy 5: same-category sellers, using primary company descriptions only."""
import re
from urllib.parse import unquote, urlsplit

from shortlist.domain import Profile, Source
from shortlist.market import offer_terms
from shortlist.relevance import grounding_text, primary_source_issue, service_business

PEER_REASON = "Offers what you sell; likely a competitor or peer, not a buyer"
GENERIC = frozenset({"ai", "b2b", "saas", "customer", "customers", "team", "teams", "enterprise", "digital",
                     "intelligent", "unified", "agentic", "experience", "solution", "solutions", "technology",
                     "technologies", "global", "leading", "scale", "scaling", "growth", "powered"})
DELIVERY = re.compile(r"\b(?:software|platform|training|certification|courses?|consultants?|consultancy|agency|services?)\b", re.IGNORECASE)
PROGRAMME = re.compile(r"\b(?:partners?|channel)[- /]+(?:program(?:me)?s?|portal|enablement|network)\b", re.IGNORECASE)


def category_terms(text: str) -> set[str]:
    text = grounding_text(text).casefold()
    text = re.sub(r"\bcustomer[- ]acquisition\b|\bdigital marketing\b", "marketing", text)
    text = re.sub(r"\blearning\b", "training", text)
    return set(offer_terms(text)) - GENERIC


def competitor_issue(profile: Profile, domain: str, primary: Source | None = None, *,
                     competitors=(), policy: int = 5) -> str | None:
    if policy < 5:
        return None
    if domain in competitors:
        return PEER_REASON
    if primary is None or primary.company_domain != domain:
        return None
    if (urlsplit(primary.url).hostname or "").removeprefix("www.") != domain or primary_source_issue(primary, strict=True):
        return None
    # A partner programme describes how the company works with partners, not its saleable category.
    if PROGRAMME.search(unquote(urlsplit(primary.url).path)) or PROGRAMME.search(primary.title):
        return None
    seller = category_terms(profile.offer)
    head = category_terms(re.split(r"[.!?]|\bfor\b", profile.offer, maxsplit=1, flags=re.IGNORECASE)[0])
    opening = "\n".join(primary.text.splitlines()[:12])[:600]
    for line in (primary.title, *opening.splitlines()):
        # Customer audiences and invitations are not the company's self-description.
        line = re.split(r"\b(?:for|to)\b", line, maxsplit=1, flags=re.IGNORECASE)[0]
        if re.search(r"\b(?:you|your|our partners|our customers|our clients|we use|we chose|not|no|never|without)\b", line, re.IGNORECASE) or PROGRAMME.search(line):
            continue
        overlap = category_terms(line) & seller
        if DELIVERY.search(line) and len(overlap) >= 2 and overlap & head:
            return PEER_REASON
        # A marketing consultant and an acquisition service share a category even without the same job title.
        if ("marketing" in overlap and "marketing" in head and service_business(line)
                and re.search(r"\b(?:service|consulting|consultancy|agency)\b", profile.offer, re.IGNORECASE)):
            return PEER_REASON
    return None
