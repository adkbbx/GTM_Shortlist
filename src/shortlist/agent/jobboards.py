"""A company's own job board, read through the boards' public job lists: no key and no model call.

Hiring is the most common public sign that a company needs something now, and the live runs lost it twice: job sites
blocked the fetch (HTTP 403) or had dropped a posting (404, 410) that was still open on the company's own Lever
board. Boards are found only from links on the company's own site, never by guessing from its name: Greenhouse's
"socket" board belongs to Socket Labs, not socket.dev.
"""
import html
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from urllib.parse import urlsplit

import httpx

from shortlist.agent.pages import Page, page_from_document
from shortlist.fetch import FetchError

SLUG = r"([A-Za-z0-9][A-Za-z0-9_.-]{0,80})"
BOARD_PATTERNS = (
    ("lever", re.compile(r"https?://jobs\.lever\.co/" + SLUG, re.IGNORECASE)),
    ("lever", re.compile(r"https?://api\.lever\.co/v0/postings/" + SLUG, re.IGNORECASE)),
    ("greenhouse", re.compile(r"https?://boards\.greenhouse\.io/embed/job_board(?:/js)?\?for=" + SLUG, re.IGNORECASE)),
    ("greenhouse", re.compile(r"https?://(?:job-)?boards\.greenhouse\.io/(?!embed\b)" + SLUG, re.IGNORECASE)),
    ("greenhouse", re.compile(r"https?://boards-api\.greenhouse\.io/v1/boards/" + SLUG, re.IGNORECASE)),
    ("ashby", re.compile(r"https?://jobs\.ashbyhq\.com/" + SLUG, re.IGNORECASE)),
    ("ashby", re.compile(r"https?://api\.ashbyhq\.com/posting-api/job-board/" + SLUG, re.IGNORECASE)),
)
BOARD_PAGE = {"lever": "https://jobs.lever.co/{}", "greenhouse": "https://job-boards.greenhouse.io/{}",
              "ashby": "https://jobs.ashbyhq.com/{}"}
POSTING_HOSTS = {"lever": ("jobs.lever.co",), "greenhouse": ("job-boards.greenhouse.io", "boards.greenhouse.io"),
                 "ashby": ("jobs.ashbyhq.com",)}
CAREERS_PATH = re.compile(r"/(?:careers?|jobs|join(?:-us)?|work-with-us|hiring|open-positions)(?:/|$)", re.IGNORECASE)
MAX_OPENINGS = 25  # shown to the investigator
# AHEAD's Lever list (148 postings with descriptions) is 4 MB; a 3 MB cap read it as no board, so its open posting
# showed as "not confirmed open". A single posting is read on its own (ONE_POSTING) whenever the board allows it.
MAX_BYTES = 12_000_000
ONE_POSTING = {"lever": (re.compile(r"^/([^/]+)/([0-9a-f-]{36})$", re.IGNORECASE),
                         "https://api.lever.co/v0/postings/{}/{}?mode=json"),
               "greenhouse": (re.compile(r"^/([^/]+)/jobs/(\d{1,20})$"),
                              "https://boards-api.greenhouse.io/v1/boards/{}/jobs/{}")}


@dataclass(frozen=True)
class Opening:
    title: str
    url: str
    location: str = ""
    posted: date | None = None
    body: str = field(default="", compare=False, repr=False)  # the posting's own HTML from the board's job list


@dataclass(frozen=True)
class Board:
    platform: str
    slug: str
    openings: tuple[Opening, ...]
    text: str = ""  # the postings' own words, to check whose board this is

    @property
    def url(self) -> str:
        return BOARD_PAGE[self.platform].format(self.slug)

    @property
    def label(self) -> str:
        return {"lever": "Lever", "greenhouse": "Greenhouse", "ashby": "Ashby"}[self.platform]


def board_refs(text: str) -> list[tuple[str, str]]:
    """Job boards linked or embedded in a page, in the order they appear."""
    found: list[tuple[int, str, str]] = []
    for platform, pattern in BOARD_PATTERNS:
        found += [(match.start(), platform, match.group(1).rstrip(".").lower()) for match in pattern.finditer(text or "")]
    refs: list[tuple[str, str]] = []
    for _, platform, slug in sorted(found):
        if (platform, slug) not in refs:
            refs.append((platform, slug))
    return refs


def _date(value) -> date | None:
    try:
        if isinstance(value, int | float):
            return datetime.fromtimestamp(value / 1000, UTC).date()
        if isinstance(value, str) and value:
            return datetime.fromisoformat(value).date()
    except (ValueError, OverflowError, OSError):
        return None
    return None


def _posting_url(platform: str, url) -> str | None:
    if not isinstance(url, str):
        return None
    parts = urlsplit(url)
    return url if parts.scheme == "https" and parts.hostname in POSTING_HOSTS[platform] else None


def lever_body(item: dict) -> str:
    """A Lever posting's description, its lists (responsibilities, requirements) and closing text, as HTML."""
    lists = "".join(f"<h3>{html.escape(str(entry.get('text') or ''))}</h3><ul>{entry.get('content') or ''}</ul>"
                    for entry in item.get("lists") or [] if isinstance(entry, dict))
    return (item.get("description") or "") + lists + (item.get("additional") or "")


def _text(value) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", html.unescape(value))) if isinstance(value, str) else ""


class JobBoards:
    """Reads public job lists from Lever, Greenhouse and Ashby. Every answer is untrusted data, like page text."""

    def __init__(self, transport: httpx.BaseTransport | None = None, timeout: float = 10):
        self.transport = transport
        self.timeout = timeout

    def _get(self, url: str):
        try:
            with httpx.Client(timeout=self.timeout, trust_env=False, follow_redirects=False,
                              transport=self.transport) as client:
                response = client.get(url, headers={"Accept": "application/json"})
            if response.status_code != 200 or len(response.content) > MAX_BYTES:
                return None
            return response.json()
        except (httpx.HTTPError, ValueError):
            return None

    def _redirect(self, url: str) -> str:
        """Where a same-site https link redirects, from its Location header only."""
        if urlsplit(url).scheme != "https":
            return ""
        try:
            with httpx.Client(timeout=self.timeout, trust_env=False, follow_redirects=False,
                              transport=self.transport) as client:
                response = client.get(url)
        except httpx.HTTPError:
            return ""
        return response.headers.get("location", "")[:500] if response.is_redirect else ""

    def read(self, platform: str, slug: str) -> Board | None:
        """The board's open postings, or None when there is no such board or it cannot be read."""
        if platform == "lever":
            data = self._get(f"https://api.lever.co/v0/postings/{slug}?mode=json")
            items = data if isinstance(data, list) else None
        elif platform == "greenhouse":
            data = self._get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true")
            items = data.get("jobs") if isinstance(data, dict) else None
        elif platform == "ashby":
            data = self._get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
            items = [j for j in data.get("jobs") or [] if isinstance(j, dict) and j.get("isListed", True)] \
                if isinstance(data, dict) else None
        else:
            return None
        return self._board(platform, slug, items)

    def read_one(self, url: str) -> tuple[Board, Opening] | None:
        """One posting read on its own from a Lever or Greenhouse posting URL: a small answer whatever the board's
        size, and None once the posting is closed (the API answers 404) or the board has no such endpoint."""
        refs = board_refs(url)
        if not refs or refs[0][0] not in ONE_POSTING:
            return None
        platform, slug = refs[0]
        pattern, endpoint = ONE_POSTING[platform]
        match = pattern.match(urlsplit(url).path.rstrip("/"))
        if match is None or match.group(1).lower() != slug:
            return None
        data = self._get(endpoint.format(slug, match.group(2)))
        board = self._board(platform, slug, [data] if isinstance(data, dict) else None)
        return (board, board.openings[0]) if board and board.openings else None

    @staticmethod
    def _board(platform: str, slug: str, items: list | None) -> Board | None:
        if platform == "lever":
            fields = lambda j: (j.get("text"), j.get("hostedUrl"), (j.get("categories") or {}).get("location"),
                                j.get("createdAt"), (j.get("descriptionPlain") or "") + " " + (j.get("additionalPlain") or ""),
                                lever_body(j))
        elif platform == "greenhouse":
            fields = lambda j: (j.get("title"), j.get("absolute_url"), (j.get("location") or {}).get("name"),
                                j.get("first_published") or j.get("updated_at"), j.get("content"),
                                html.unescape(j.get("content") or ""))
        else:
            fields = lambda j: (j.get("title"), j.get("jobUrl"), j.get("location"), j.get("publishedAt"),
                                j.get("descriptionPlain"), j.get("descriptionHtml") or html.escape(j.get("descriptionPlain") or ""))
        if not isinstance(items, list):
            return None
        openings, words = [], []
        for item in items:
            if not isinstance(item, dict):
                continue
            title, url, location, posted, text, body = fields(item)
            url = _posting_url(platform, url)
            if not isinstance(title, str) or not title.strip() or url is None:
                continue
            openings.append(Opening(title=title.strip()[:200], url=url, posted=_date(posted),
                                    location=location.strip()[:120] if isinstance(location, str) else "",
                                    body=body[:60000] if isinstance(body, str) else ""))
            words.append(_text(text)[:4000])
        return Board(platform=platform, slug=slug, openings=tuple(openings[:300]), text=" ".join(words)[:40000])

    def own(self, home: Page, fetch: Callable[[str], Page]) -> Board | None:
        """The board the company's own homepage, or else its careers page, links to or embeds."""
        refs = board_refs(home.html)
        if not refs:
            careers = next((link for link in home.links if CAREERS_PATH.search(urlsplit(link).path)), None)
            if careers is None:
                return None
            try:
                refs = board_refs(fetch(careers).html)
            except FetchError:  # an unreadable careers page means no board, never a failed investigation
                # letterdrop.com/jobs redirects to its board, which the page fetcher refuses as another site. The
                # redirect's target is read, never fetched, and kept only when it is a job board.
                refs = board_refs(self._redirect(careers))
        for platform, slug in refs[:3]:
            board = self.read(platform, slug)
            if board is not None:
                return board
        return None

    def listed(self, url: str) -> tuple[Board | None, Opening | None]:
        """The board a posting URL belongs to and that posting while it is still open: read on its own when the board
        allows, else found in the board's whole list."""
        one = self.read_one(url)
        if one is not None:
            return one
        refs = board_refs(url)
        board = self.read(*refs[0]) if refs else None
        if board is None:
            return None, None
        key = url.split("?")[0].rstrip("/").lower()
        return board, next((o for o in board.openings if o.url.split("?")[0].rstrip("/").lower() == key), None)

    def page_for(self, url: str) -> Page | None:
        """A posting page built from the board's own job list, for a posting the page fetcher could not read: Ashby
        renders its pages with script (Decagon's posting had "insufficient readable text"). Only a posting still
        listed on its board; the posting date comes from the board."""
        opening = self.listed(url)[1]
        if opening is None or not opening.body.strip():
            return None
        posted = json.dumps({"@type": "JobPosting", "datePosted": opening.posted.isoformat()}) if opening.posted else ""
        document = (f"<html><head><title>{html.escape(opening.title)}</title>"
                    + (f'<script type="application/ld+json">{posted}</script>' if posted else "")
                    + f"</head><body><h1>{html.escape(opening.title)}</h1><p>{html.escape(opening.location)}</p>"
                    + f"{opening.body}</body></html>")
        try:
            return page_from_document(opening.url, document.encode("utf-8"), None)
        except FetchError:
            return None

    def posting(self, url: str, names: list[str], role: str = "") -> tuple[Board, Opening] | None:
        """The board behind a posting URL and that posting, when it is still listed and the board's postings name
        the company. A bare board URL (the vanta.com run got "https://jobs.lever.co/qloo") gives the open role whose
        title best matches role. None: no longer listed, no matching role, or another company's board."""
        board, opening = self.listed(url)
        if board is None:
            return None
        if opening is None and len([p for p in urlsplit(url).path.split("/") if p]) <= 1:
            opening = best_role(board.openings, role)
        named = any(re.search(r"(?<![\w-])" + re.escape(name.casefold()) + r"(?![\w-])", board.text.casefold())
                    for name in names if len(name) >= 3)
        return (board, opening) if opening and named else None


WORD = re.compile(r"[a-z0-9]{3,}")
COMMON = frozenset({"job", "post", "posting", "lever", "greenhouse", "ashby", "the", "and", "for", "with", "remote",
                    "oct", "sep", "nov", "2026", "senior", "manager", "lead"})


def best_role(openings: tuple[Opening, ...], role: str) -> Opening | None:
    """The opening sharing the most distinctive words with the lead's description, needing at least two."""
    wanted = set(WORD.findall(role.casefold())) - COMMON
    scored = [(len(wanted & (set(WORD.findall(o.title.casefold())) - COMMON)), o) for o in openings]
    score, opening = max(scored, key=lambda pair: pair[0], default=(0, None))
    return opening if score >= 2 else None


def posting_page(url: str) -> str:
    """Greenhouse moved postings from boards.greenhouse.io to job-boards.greenhouse.io and redirects the old links,
    which the page fetcher refuses as a change of site (vanta.com run). Ask for the new address directly."""
    parts = urlsplit(url)
    if parts.hostname == "boards.greenhouse.io" and not parts.path.startswith("/embed"):
        return url.replace("://boards.greenhouse.io/", "://job-boards.greenhouse.io/", 1)
    return url
