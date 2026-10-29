"""Fetched pages, quote grounding, source types and dates. Page text is untrusted data throughout.

Every network fetch goes through shortlist.fetch (fetch_html, the same TLS-pinned, public-address-checked path as
fetch_page) and page_from_html, which builds the same readable text fetch_page saves. The raw document is kept as
well so the competitor scan can read script sources, badges and "powered by" lines the readable text drops.
"""
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from shortlist.agent.models import Attribute, PageSignature, SourceType
from shortlist.domain import Source
from shortlist.fetch import FetchError, canonical_url, domain_of, fetch_html, page_from_html
from shortlist.relevance import grounding_text, listed_site, verbatim_quote


@dataclass(frozen=True)
class Page:
    source: Source
    html: str
    full_text: str
    dates: tuple[date, ...] = ()
    links: tuple[str, ...] = ()

    @property
    def url(self) -> str:
        return self.source.url

    @property
    def domain(self) -> str:
        return self.source.company_domain

    @property
    def fetched_at(self) -> datetime:
        return self.source.retrieved_at


Fetcher = Callable[[str, str | None], Page]

DATE_KEYS = ("datePosted", "datePublished")
DATE_META = {"article:published_time", "og:published_time", "datepublished", "date", "publish-date", "pubdate",
             "dc.date", "dcterms.date"}


def _iso_date(value) -> date | None:
    if not isinstance(value, str):
        return None
    match = re.match(r"\s*(\d{4})-(\d{2})-(\d{2})", value)
    if not match:
        return None
    try:
        return date(int(match[1]), int(match[2]), int(match[3]))
    except ValueError:
        return None


def _json_dates(value, found: list[date], depth: int = 0):
    if depth > 6:
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if key in DATE_KEYS and (parsed := _iso_date(item)):
                found.append(parsed)
            else:
                _json_dates(item, found, depth + 1)
    elif isinstance(value, list):
        for item in value[:50]:
            _json_dates(item, found, depth + 1)


def page_dates(soup: BeautifulSoup) -> tuple[date, ...]:
    """Publication dates the page itself declares in metadata, time elements or JSON-LD."""
    found: list[date] = []
    for meta in soup.find_all("meta"):
        key = str(meta.get("property") or meta.get("name") or meta.get("itemprop") or "").casefold()
        if key in DATE_META and (parsed := _iso_date(meta.get("content"))):
            found.append(parsed)
    for element in soup.find_all("time"):
        if parsed := _iso_date(element.get("datetime")):
            found.append(parsed)
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            _json_dates(json.loads(script.string or ""), found)
        except ValueError:
            continue
    return tuple(sorted(set(found), reverse=True))


def observed_links(url: str, soup: BeautifulSoup) -> tuple[str, ...]:
    owner = domain_of(url)
    links = []
    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href")
        if not isinstance(href, str):
            continue
        try:
            destination = canonical_url(urljoin(url, href))
        except FetchError:
            continue
        if domain_of(destination) == owner and destination not in links and destination != canonical_url(url):
            links.append(destination)
    return tuple(links[:300])


def page_from_document(current: str, body: bytes, expected_domain: str | None = None) -> Page:
    source = page_from_html(current, body, expected_domain)
    soup = BeautifulSoup(body, "html.parser")
    dates = page_dates(soup)
    links = observed_links(source.url, soup)
    for tag in soup(["script", "style", "noscript", "svg", "template"]):
        tag.decompose()
    full_text = "\n".join(line.strip() for line in soup.get_text("\n").splitlines() if line.strip())[:60_000]
    return Page(source=source, html=body.decode("utf-8", "replace"), full_text=full_text, dates=dates, links=links)


def fetch_document(url: str, expected_domain: str | None = None) -> Page:
    current, body = fetch_html(url, expected_domain)
    return page_from_document(current, body, expected_domain)


# Same-domain pages that explain a seller: one of each kind, in this order, at most five.
SELLER_PAGE_KINDS = (
    ("pricing", {"pricing", "plans", "price"}),
    ("product", {"product", "products", "features", "platform", "solutions", "how-it-works", "solution"}),
    ("customers", {"customers", "case-studies", "case-study", "stories", "customer-stories", "testimonials"}),
    ("about", {"about", "about-us", "company", "who-we-are"}),
    ("integrations", {"integrations", "integration", "apps", "marketplace", "partners", "ecosystem"}),
)
COMPARISON = re.compile(r"(?:^|[-_/])(?:vs|versus|compare|comparison|alternatives?)(?:[-_/]|$)", re.IGNORECASE)
INTEGRATION_PATH = re.compile(r"integrat|partner|marketplace|/apps\b|ecosystem", re.IGNORECASE)
JOB_PATH = re.compile(r"(?:^|/)(?:careers?|jobs?|join-us|vacanc(?:y|ies)|positions|openings|hiring)(?:/|$)", re.IGNORECASE)


def _parts(url: str) -> list[str]:
    return [part.casefold() for part in urlsplit(url).path.split("/") if part]


def seller_links(page: Page, limit: int = 5) -> list[str]:
    chosen = []
    for _, words in SELLER_PAGE_KINDS:
        for link in page.links:
            parts = _parts(link)
            if 1 <= len(parts) <= 2 and parts[0] in words and not urlsplit(link).query:
                if link not in chosen:
                    chosen.append(link)
                break
    return chosen[:limit]


def comparison_links(page: Page, limit: int = 5) -> list[str]:
    return [link for link in page.links if COMPARISON.search(urlsplit(link).path)][:limit]


def page_kind(url: str, homepage: bool = False) -> str:
    if homepage or urlsplit(url).path in ("", "/"):
        return "homepage"
    return "integrations" if INTEGRATION_PATH.search(urlsplit(url).path) else "other"


def place_name(url: str) -> str:
    """How a checked page is described to a person, e.g. "homepage code" or "integrations page"."""
    kind = page_kind(url)
    if kind == "homepage":
        return "homepage code"
    if kind == "integrations":
        return "integrations page"
    if JOB_PATH.search(urlsplit(url).path):
        return "job post"
    parts = _parts(url)
    return f"{parts[-1].replace('-', ' ')} page" if parts else "page"


POWERED = re.compile(r"\b(?:powered by|built (?:with|on)|support by|chat by|runs on|secured by|protected by)\b",
                     re.IGNORECASE)
SCANNED_ATTRIBUTES = {"script": ("src",), "link": ("href",), "iframe": ("src",), "img": ("src", "alt", "title"),
                      "a": ("href", "title"), "source": ("src",), "embed": ("src",)}


def signature(page: Page, homepage: bool = False) -> PageSignature:
    soup = BeautifulSoup(page.html, "html.parser")
    attributes, seen = [], set()
    owner = page.domain
    for element in soup.find_all(list(SCANNED_ATTRIBUTES)):
        for attr in SCANNED_ATTRIBUTES[element.name]:
            value = element.get(attr)
            if not isinstance(value, str) or not value.strip() or len(value) > 2048:
                continue
            value = value.strip()
            if attr in ("src", "href"):
                host = (urlsplit(urljoin(page.url, value)).hostname or "").casefold()
                if not host or host == owner or host.endswith("." + owner):
                    continue  # First-party code and links cannot name a third-party tool by address.
            elif len(value) > 300:
                continue
            key = (element.name, attr, value)
            if key not in seen:
                seen.add(key)
                attributes.append(Attribute(tag=element.name, attr=attr, value=value))
    lines = page.full_text.splitlines()
    kind = page_kind(page.url, homepage)
    return PageSignature(url=page.url, kind=kind, fetched_at=page.fetched_at, attributes=attributes[:400],
                         powered_by=[line[:300] for line in lines if POWERED.search(line)][:20],
                         lines=[line[:300] for line in lines][:300] if kind == "integrations" else [])


MIN_QUOTE = 12


def ground(quote: str, page: Page) -> tuple[str, str] | None:
    """The page's own characters for a quote, and where they were found, or None when the page lacks it."""
    quote = (quote or "").strip()
    if len(grounding_text(quote)) < MIN_QUOTE:
        return None
    exact = verbatim_quote(quote, page.source.text) or verbatim_quote(quote, page.full_text)
    if exact:
        return exact, "text"
    if quote in page.html:
        return quote, "html"
    return None


JOB_HOSTS = frozenset({"greenhouse.io", "lever.co", "ashbyhq.com", "workable.com", "bamboohr.com", "smartrecruiters.com",
                       "recruitee.com", "teamtailor.com", "personio.de", "personio.com", "jobvite.com", "icims.com",
                       "myworkdayjobs.com", "indeed.com", "glassdoor.com", "wellfound.com", "ziprecruiter.com",
                       "welcometothejungle.com", "breezy.hr", "jobs.lever.co", "workforcenow.adp.com"})
# Applicant-tracking systems take a posting's page down when the role closes, so one read during the run is open now
# even without a stated date (fourth live run: an SDR posting on Greenhouse had no date). Job aggregators keep stale
# copies and are not in this list.
ATS_HOSTS = frozenset({"greenhouse.io", "lever.co", "ashbyhq.com", "workable.com", "bamboohr.com", "smartrecruiters.com",
                       "recruitee.com", "teamtailor.com", "personio.de", "personio.com", "jobvite.com", "icims.com",
                       "myworkdayjobs.com", "breezy.hr", "workforcenow.adp.com"})
CLOSED_POSTING = re.compile(
    r"no longer (?:open|available|accepting applications)|(?:position|role|job) (?:has been|is|was) filled|"
    r"(?:job|posting|position|vacancy|role) (?:has )?(?:expired|closed)|applications? (?:are |is )?(?:now )?closed",
    re.IGNORECASE)


def open_posting(page: Page) -> bool:
    """A job posting on an applicant-tracking system that does not say it is closed."""
    try:
        host = domain_of(page.url)
    except FetchError:
        return False
    return listed_site(host, ATS_HOSTS) and not CLOSED_POSTING.search(page.full_text)


REVIEW_HOSTS = frozenset({"g2.com", "capterra.com", "trustradius.com", "getapp.com", "softwareadvice.com",
                          "trustpilot.com", "gartner.com", "peerspot.com"})
NEWS_HOSTS = frozenset({"techcrunch.com", "reuters.com", "bloomberg.com", "businesswire.com", "prnewswire.com",
                        "globenewswire.com", "forbes.com", "venturebeat.com", "theverge.com", "wsj.com", "ft.com"})


def source_type(url: str, company_domain: str, competitor_domains=(), hint: str | None = None) -> SourceType:
    """Decided by code from the URL, not by the model: whether a page is the company's own matters for the rules."""
    try:
        host = domain_of(url)
    except FetchError:
        return "other"
    if host == company_domain or host.endswith("." + company_domain):
        path = urlsplit(url).path
        hostname = urlsplit(url).hostname or ""
        return "job_post" if JOB_PATH.search(path) or hostname.startswith(("jobs.", "careers.")) else "own_site"
    if any(host == domain or host.endswith("." + domain) for domain in competitor_domains):
        return "competitor_site"
    if listed_site(host, JOB_HOSTS):
        return "job_post"
    if listed_site(host, REVIEW_HOSTS):
        return "review"
    if listed_site(host, NEWS_HOSTS):
        return "news"
    return hint if hint in ("news", "review", "job_post") else "other"


def verified_date(claimed: date | None, page: Page) -> date | None:
    """A model's date is kept only when the page states it; otherwise the page's single declared date is used."""
    if claimed is None:
        return page.dates[0] if len(page.dates) == 1 else None
    if claimed in page.dates:
        return claimed
    month, short = claimed.strftime("%B"), claimed.strftime("%b")
    forms = {claimed.isoformat(), f"{month} {claimed.day}, {claimed.year}", f"{short} {claimed.day}, {claimed.year}",
             f"{claimed.day} {month} {claimed.year}", f"{claimed.day} {short} {claimed.year}",
             f"{short}. {claimed.day}, {claimed.year}"}
    haystack = grounding_text(page.source.text + "\n" + page.full_text).casefold()
    return claimed if any(grounding_text(form).casefold() in haystack for form in forms) else None


def parse_date(value) -> date | None:
    if isinstance(value, date):
        return value
    return _iso_date(value) if isinstance(value, str) else None


def excerpt(page: Page, limit: int = 6000) -> str:
    text = page.source.text
    return text if len(text) <= limit else text[:limit] + "\n[... page text shortened]"
