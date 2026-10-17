"""Conservative page-type gates, not claims that a company fits a target."""
import re
from urllib.parse import unquote, urlsplit

from shortlist.domain import Candidate

DIRECTORIES = frozenset({"linkedin.com", "crunchbase.com", "g2.com", "capterra.com", "ycombinator.com",
                         "techcrunch.com", "wellfound.com", "producthunt.com", "tracxn.com", "github.com",
                         "wikipedia.org", "wikidata.org", "definitions.net", "thefreedictionary.com",
                         "freedict.com", "vocabulary.com"})
CONTENT_SECTIONS = frozenset({"blog", "blogs", "article", "articles", "news", "newsroom", "insights",
                              "resources", "learn", "tips", "reports", "whitepapers", "press", "podcast",
                              "podcasts", "guides", "wiki", "dictionary", "definition", "lists", "community",
                              "academy", "case-studies", "customer-stories"})
BUSINESS_SECTIONS = frozenset({"product", "products", "platform", "solutions", "services", "about", "company",
                               "pricing", "features", "industries"})
EDITORIAL_TITLE = re.compile(
    r"^(?:how|why|what|your guide|the ultimate guide)\b|\b(?:top|best)\s+\d+\b|"
    r"\b\d+\s+(?:top|best)\b|\b(?:playbook|framework|report|definition|roundup|explained)\b", re.IGNORECASE)
EDITORIAL_SLUG = re.compile(r"(?:^|[-_])(?:guide|playbook|framework|report|definition|examples|roundup|best|top)(?:[-_]|$)", re.IGNORECASE)


def company_page_issue(url: str, title: str = "") -> str | None:
    """An editorial page is a source about a topic, not a company identity.

    Do not ban an entire business domain because it also publishes a blog. Its
    homepage and genuine product/service pages may still be valid candidates.
    Secondary editorial sources remain available for dated company statements.
    """
    parts = [part.casefold() for part in unquote(urlsplit(url).path).split("/") if part]
    if any(part in CONTENT_SECTIONS for part in parts):
        return "Article, guide, news or directory page; an official company or product page is required"
    business_page = bool(parts and parts[0] in BUSINESS_SECTIONS)
    if parts and not business_page and (EDITORIAL_SLUG.search(parts[-1]) or EDITORIAL_TITLE.search(title)):
        return "Editorial title or article URL; this page does not establish the publisher as a target company"
    return None


def candidate_issue(candidate: Candidate) -> str | None:
    if any(candidate.domain == domain or candidate.domain.endswith("." + domain) for domain in DIRECTORIES):
        return "Directory or reference website; not an official candidate company page"
    return company_page_issue(candidate.url, candidate.name)


def seller_marketing_criterion(text: str) -> bool:
    """Reject obvious seller voice/statistics; this is not a semantic fit classifier."""
    return bool(re.search(r"^(?:our\b|we\b|the platform\b|the seller\b)|\btrusted by\b", text, re.IGNORECASE))
