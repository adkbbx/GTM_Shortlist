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
# Sites whose pages are never a candidate company's own: video and social platforms, job boards, review and
# comparison sites, market-research publishers, and company or startup databases. Observed in saved searches.
NON_COMPANY_SITES = frozenset({
    "youtube.com", "youtu.be", "vimeo.com", "tiktok.com", "instagram.com", "facebook.com", "x.com", "twitter.com",
    "pinterest.com", "quora.com", "medium.com", "substack.com", "slideshare.net", "scribd.com",
    "indeed.com", "ziprecruiter.com", "glassdoor.com", "monster.com", "simplyhired.com", "careerbuilder.com",
    "startup.jobs", "workingnomads.com", "remoteok.com", "weworkremotely.com",
    "gartner.com", "forrester.com", "trustradius.com", "getapp.com", "softwareadvice.com", "sourceforge.net",
    "alternativeto.net", "saasworthy.com", "clutch.co", "goodfirms.co", "upwork.com", "fiverr.com", "trustpilot.com",
    "statista.com", "mordorintelligence.com", "grandviewresearch.com", "marketsandmarkets.com",
    "businessresearchinsights.com", "fortunebusinessinsights.com", "precedenceresearch.com", "researchandmarkets.com",
    "gminsights.com", "alliedmarketresearch.com", "imarcgroup.com", "expertmarketresearch.com", "verifiedmarketresearch.com",
    "pitchbook.com", "cbinsights.com", "dealroom.co", "owler.com", "zoominfo.com", "rocketreach.co", "growthlist.co",
    "topstartups.io", "vcbacked.co", "openvc.app", "startupik.com", "businessofapps.com", "influencermarketinghub.com",
    "datamation.com", "techtarget.com", "saastr.com", "forbes.com", "businessinsider.com", "entrepreneur.com", "inc.com",
})
CONTENT_SECTIONS = frozenset({"blog", "blogs", "article", "articles", "news", "newsroom", "insights",
                              "resources", "learn", "tips", "reports", "whitepapers", "press", "podcast",
                              "podcasts", "guides", "wiki", "dictionary", "definition", "lists", "community",
                              "academy", "case-studies", "customer-stories", "job", "jobs", "careers", "events",
                              "feed", "feeds", "rss", "cgi-sys",
                              "glossary", "post", "posts", "p", "watch", "video", "videos", "webinar", "webinars",
                              "library", "libraries", "tech-hub", "knowledge-base", "kb", "market-reports",
                              "industry-reports", "statistics", "directory", "list", "investor-lists",
                              "funded-startups", "executive-biography", "biography", "courses", "course", "latest",
                              "whatis", "matrices", "topics", "tag", "tags", "category", "author", "authors",
                              "research", "episodes"})
# Count-led lists ("25,000+ Funded Startups", "16 of the Best ...") and research or job listings are about other companies.
LISTING_TITLE = re.compile(
    r"^\d[\d,]*\+?\s+(?:[\w&-]+\s+){0,4}(?:companies|startups|businesses|agencies|firms|tools|apps|platforms|vendors|"
    r"websites|programs|investors|ideas|examples|alternatives|brands)\b|\b\d+\s+of\s+the\s+best\b|\blist of\b|"
    r"\bmarket (?:size|forecast|report)\b|\bmarket\s+\d{4}\b|\bglossary\b|\bjob postings\b|\bcareer opportunities\b|"
    r"\b(?:now hiring|apply today)\b", re.IGNORECASE)
PUBLIC_SECTOR = re.compile(
    r"\b(?:government|public sector|municipal|county|counties|city|cities|federal|state agenc\w*|agenc(?:y|ies)|"
    r"council|ministr\w*|school|universit\w*|college|education\w*|campus|nonprofit|non-profit|ngo|charit\w*|"
    r"hospital|health system|central bank|intergovernmental)\b", re.IGNORECASE)
# Titles that name a public body rather than a company ("Solid Waste Agency of ... County", "City of ...").
PUBLIC_BODY_TITLE = re.compile(
    r"\b(?:county|city of|municipality|ministry of|department of|agency of|school district|public schools|university)\b",
    re.IGNORECASE)
PUBLIC_HOST = re.compile(r"(?:^|\.)(?:gov|mil|edu|int)(?:\.[a-z]{2})?$|(?:^|\.)(?:gov|ac|edu)\.[a-z]{2}$|(?:^|\.)europa\.eu$")
TRACKING_PARAMETERS = re.compile(r"^(?:utm_\w+|ref|source|gclid|fbclid|msclkid|hl|lang)$", re.IGNORECASE)
BUSINESS_SECTIONS = frozenset({"product", "products", "platform", "solutions", "services", "about", "company",
                               "pricing", "features", "industries", "team", "leadership", "contact"})
EDITORIAL_TITLE = re.compile(
    r"^(?:how|why|what|your guide|the ultimate guide)\b|\b(?:top|best)\s+\d+\b|"
    r"\b\d+\s+(?:top|best)\b|\b(?:playbook|framework|report|definition|roundup|explained)\b|"
    r"\b(?:guides?|strategies|statistics|trends|tips|ideas|benchmarks|checklist|mistakes)\b", re.IGNORECASE)
EDITORIAL_SLUG = re.compile(r"(?:^|[-_])(?:guide|playbook|framework|report|definition|examples|roundup|best|top|case-study|models|calculator)(?:[-_]|$)", re.IGNORECASE)


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
    if host.startswith(("blog.", "news.", "community.", "forum.", "forums.", "learn.", "academy.", "resources.")):
        return "Article, guide, news or directory page; an official company or product page is required"
    if parts and parts[-1].endswith((".pdf", ".xml", ".rss", ".csv", ".xls", ".xlsx")):
        return "Document, feed or data listing; not a company identity page"
    if any(part in CONTENT_SECTIONS or re.match(r"(?:blog|news|insight|article)s?[-_]", part) for part in parts):
        return "Article, guide, news or directory page; an official company or product page is required"
    business_page = bool(parts and parts[0] in BUSINESS_SECTIONS)
    if parts and not business_page and (EDITORIAL_SLUG.search(parts[-1]) or EDITORIAL_TITLE.search(title)):
        return "Editorial title or article URL; this page does not establish the publisher as a target company"
    if parts and LISTING_TITLE.search(title):  # A homepage is never refused by its title alone.
        return "List, market report or job listing; it describes other companies rather than establishing one"
    if strict:
        # Unmarked third-party reviews often have no /blog/ prefix. Require a
        # recognisable business entry page instead of assuming an arbitrary slug is official.
        if parts and re.fullmatch(r"[a-z]{2}(?:-[a-z]{2})?", parts[0]):
            parts = parts[1:]
        # Homepages often redirect to a named home document (lumen.com -> /en-us/home.html, live 18 October).
        if parts and parts[0] not in BUSINESS_SECTIONS | {"home", "index.html", "index.htm", "index.php", "about-us", "home.html",
                                                          "home.htm", "home.aspx", "home.php", "default.aspx", "index.aspx"}:
            return "Page purpose is not established as an official company, product or service page"
    return None


def research_entry(url: str, title: str = "") -> str:
    """Where research starts for a company found through one of its own pages. A recognisable company page is used as
    found; any other deep page (a product area, a market landing page) starts from the site's homepage instead of
    being fetched and then refused. Content pages never reach this point: admission rejects them."""
    if company_page_issue(url, title) is None and company_page_issue(url, title, strict=True):
        return f"https://{urlsplit(url).hostname}/"
    return url


def listed_site(host: str, sites: frozenset[str]) -> bool:
    host = host.casefold().removeprefix("www.")
    return any(host == site or host.endswith("." + site) for site in sites)


def primary_source_issue(source: Source, *, strict: bool = False) -> str | None:
    owner = (urlsplit(source.url).hostname or "").removeprefix("www.")
    if listed_site(owner, DIRECTORIES | NON_COMPANY_SITES):
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
    if listed_site(candidate.domain, DIRECTORIES):
        return "Directory or reference website; not an official candidate company page"
    if listed_site(candidate.domain, NON_COMPANY_SITES):
        return "Video, social, job, review, research or company-database site; not a candidate company's own page"
    parsed = urlsplit(candidate.url)
    host = (parsed.hostname or "").casefold()
    # Government, education and intergovernmental sites are candidates only when the search is about that sector.
    if (PUBLIC_HOST.search(host) or PUBLIC_BODY_TITLE.search(candidate.name)) and not PUBLIC_SECTOR.search(candidate.query):
        return "Public-sector or education website outside a public-sector search"
    if parsed.query and parsed.path.strip("/") == "" and any(
            not TRACKING_PARAMETERS.match(name.split("=")[0]) for name in parsed.query.split("&") if name):
        return "Filtered listing view rather than a company's own page"
    return company_page_issue(candidate.url, candidate.name)


def seller_marketing_criterion(text: str) -> bool:
    """Reject obvious seller voice/statistics; this is not a semantic fit classifier."""
    return bool(re.search(r"^(?:our\b|we\b|the platform\b|the seller\b)|\btrusted by\b", text, re.IGNORECASE))
