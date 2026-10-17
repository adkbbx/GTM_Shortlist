"""Conservative page-type gates, not claims that a company fits a target."""
import re
from urllib.parse import unquote, urlsplit

from shortlist.domain import Candidate, CompanyIdentity, Research, Source


class CompanyPageError(ValueError):
    """A rejected company identity must never become a partial company record."""

DIRECTORIES = frozenset({"linkedin.com", "crunchbase.com", "g2.com", "capterra.com", "ycombinator.com",
                         "techcrunch.com", "wellfound.com", "producthunt.com", "tracxn.com", "github.com",
                         "wikipedia.org", "wikidata.org", "definitions.net", "thefreedictionary.com",
                         "freedict.com", "vocabulary.com", "builtin.com", "builtinla.com", "builtinnyc.com",
                         "builtinboston.com", "builtinaustin.com", "builtinseattle.com", "builtinchicago.org",
                         "50pros.com", "getonbrd.com", "getonbrd.com.ar"})
CONTENT_SECTIONS = frozenset({"blog", "blogs", "article", "articles", "news", "newsroom", "insights",
                              "resources", "learn", "tips", "reports", "whitepapers", "press", "podcast",
                              "podcasts", "guides", "wiki", "dictionary", "definition", "lists", "community",
                              "academy", "case-studies", "customer-stories", "job", "jobs", "careers", "events",
                              "feed", "feeds", "rss", "cgi-sys"})
BUSINESS_SECTIONS = frozenset({"product", "products", "platform", "solutions", "services", "about", "company",
                               "pricing", "features", "industries", "team", "leadership", "contact"})
EDITORIAL_TITLE = re.compile(
    r"^(?:how|why|what|your guide|the ultimate guide)\b|\b(?:top|best)\s+\d+\b|"
    r"\b\d+\s+(?:top|best)\b|\b(?:playbook|framework|report|definition|roundup|explained)\b", re.IGNORECASE)
EDITORIAL_SLUG = re.compile(r"(?:^|[-_])(?:guide|playbook|framework|report|definition|examples|roundup|best|top)(?:[-_]|$)", re.IGNORECASE)


def company_page_issue(url: str, title: str = "", *, strict: bool = False) -> str | None:
    """An editorial page is a source about a topic, not a company identity.

    Do not ban an entire business domain because it also publishes a blog. Its
    homepage and genuine product/service pages may still be valid candidates.
    Secondary editorial sources remain available for dated company statements.
    """
    parts = [part.casefold() for part in unquote(urlsplit(url).path).split("/") if part]
    host = (urlsplit(url).hostname or "").casefold()
    if host.startswith(("jobs.", "careers.")):
        return "Recruitment website; this is not the employer's official company page"
    if parts and parts[-1].endswith((".pdf", ".xml", ".rss", ".csv", ".xls", ".xlsx")):
        return "Document, feed or data listing; not a company identity page"
    if any(part in CONTENT_SECTIONS for part in parts):
        return "Article, guide, news or directory page; an official company or product page is required"
    business_page = bool(parts and parts[0] in BUSINESS_SECTIONS)
    if parts and not business_page and (EDITORIAL_SLUG.search(parts[-1]) or EDITORIAL_TITLE.search(title)):
        return "Editorial title or article URL; this page does not establish the publisher as a target company"
    if strict:
        # Unmarked third-party reviews often have no /blog/ prefix. Require a
        # recognisable business entry page instead of assuming an arbitrary slug is official.
        if parts and re.fullmatch(r"[a-z]{2}(?:-[a-z]{2})?", parts[0]):
            parts = parts[1:]
        if parts and parts[0] not in BUSINESS_SECTIONS | {"home", "index.html", "index.htm", "index.php", "about-us"}:
            return "Page purpose is not established as an official company, product or service page"
    return None


def primary_source_issue(source: Source, *, strict: bool = False) -> str | None:
    owner = (urlsplit(source.url).hostname or "").removeprefix("www.")
    if any(owner == domain or owner.endswith("." + domain) for domain in DIRECTORIES):
        return "Third-party directory or job board; not the employer's own website"
    issue = company_page_issue(source.url, source.title, strict=strict)
    if issue:
        return issue
    title = " ".join(source.title.casefold().split())
    opening = " ".join(source.text.casefold().split())[:500]
    unavailable = r"account suspended|website suspended|site suspended|this account has been suspended|domain (?:is )?for sale|website is parked|404 (?:not found|page)|access denied|just a moment|checking your browser"
    if re.search(unavailable, title) or re.match(r"(?:error\s*[:.-]?\s*)?(?:" + unavailable + r")", opening):
        return "Suspended, unavailable, parked or challenge page; no company identity can be established"
    if re.search(r"\b(?:job board|find (?:tech |startup )?jobs|search (?:tech |startup )?jobs|job listings)\b", title + " " + opening):
        return "Job-board listing page; employers mentioned here are different entities"
    return None


def identity_issue(identity: CompanyIdentity, sources: tuple[Source, ...], domain: str) -> str | None:
    if identity.domain != domain:
        return "Model identified a company on a different website"
    page = next((source for source in sources if source.id == identity.source_id), None)
    if page is None or page.company_domain != domain:
        return "Company identity lacks a saved first-party source"
    if issue := primary_source_issue(page, strict=True):
        return issue
    if (urlsplit(page.url).hostname or "").removeprefix("www.") != domain:
        return "Identity source belongs to another website"
    if " ".join(identity.passage.split()) not in " ".join(page.text.split()):
        return "Company identity passage was not found in the saved page"
    name = " ".join(identity.name.casefold().split())
    if name not in " ".join(identity.passage.casefold().split()):
        return "Company identity passage does not name the proposed company"
    brand = domain.split(".")[0].replace("-", "").casefold()
    words = re.findall(r"[a-z0-9]+", name)
    aliases = [word for word in words if len(word) >= 3] + ["".join(word[0] for word in words)]
    if not any(len(alias) >= 3 and (alias == brand or len(alias) >= 4 and alias in brand) for alias in aliases):
        return "Company name cannot be tied to the source website owner"
    return None


def record_issue(record: Research, *, strict: bool = False) -> str | None:
    """Final write boundary, shared by SQLite and hosted delivery before billing."""
    if record.sources:
        if issue := primary_source_issue(record.sources[0], strict=strict):
            return issue
        owner = (urlsplit(record.sources[0].url).hostname or "").removeprefix("www.")
        if owner != record.domain or record.sources[0].company_domain != record.domain:
            return "Primary source belongs to another company"
    named_domains = re.findall(r"\b[a-z0-9][a-z0-9-]*\.(?:com|io|ai|org|net|co)\b", record.name.casefold())
    if named_domains and record.domain not in named_domains:
        return "The named company is different from the source website owner"
    if record.company_identity:
        return identity_issue(record.company_identity, record.sources, record.domain)
    return None


def candidate_issue(candidate: Candidate) -> str | None:
    if any(candidate.domain == domain or candidate.domain.endswith("." + domain) for domain in DIRECTORIES):
        return "Directory or reference website; not an official candidate company page"
    return company_page_issue(candidate.url, candidate.name)


def seller_marketing_criterion(text: str) -> bool:
    """Reject obvious seller voice/statistics; this is not a semantic fit classifier."""
    return bool(re.search(r"^(?:our\b|we\b|the platform\b|the seller\b)|\btrusted by\b", text, re.IGNORECASE))
