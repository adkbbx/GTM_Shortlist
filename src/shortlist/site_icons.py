"""Read declared icons without research providers or changes to saved research."""
import re
import time
from collections import OrderedDict
from threading import BoundedSemaphore, Lock
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
from pydantic import BaseModel

from shortlist.fetch import FetchError, canonical_url, domain_of, fetch_html, resolve_public

PUBLIC_HOST = re.compile(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}")


class SiteIconInfo(BaseModel):
    url: str | None = None
    # The homepage declares only a site builder's blank stand-in: its /favicon.ico is that blank too, so the page
    # shows the company's letter instead of an empty box.
    placeholder: bool = False


# Site builders' stand-in icons that draw nothing: Wix serves a 16x16 icon of white pixels at 1/255 opacity to every
# site without its own icon (mitticafe.org, 2 November).
PLACEHOLDER_ICONS = frozenset({"https://static.parastorage.com/client/pfavico.ico"})
PLACEHOLDER = ""  # declared_icon's answer when the homepage declares only placeholders


def icon_info(icon: str | None) -> SiteIconInfo:
    return SiteIconInfo(url=icon or None, placeholder=icon == PLACEHOLDER)


def declared_icon(page_url: str, body: bytes) -> str | None:
    soup = BeautifulSoup(body, "html.parser")
    head = soup.head
    if head is None:
        return None
    base = page_url
    tag = head.find("base", href=True)
    if tag:
        try:
            candidate = canonical_url(urljoin(page_url, tag["href"]))
            if domain_of(candidate) == domain_of(page_url):
                base = candidate
        except ValueError:
            pass
    candidates = []
    for link in head.find_all("link", href=True, limit=64):
        rel = {str(token).lower() for token in link.get("rel", [])}
        priority = 0 if "icon" in rel else 1 if rel & {"apple-touch-icon", "apple-touch-icon-precomposed"} else None
        if priority is None:
            continue
        # An SVG icon comes last: many restyle themselves for dark mode (ascerta.com's strokes turn white), which
        # leaves them invisible on a light page. The PNG touch icon is drawn for any background.
        svg = "svg" in str(link.get("type", "")).lower() or urlsplit(str(link["href"])).path.lower().endswith(".svg")
        if priority == 0 and svg:
            priority = 2
        try:
            candidates.append((priority, canonical_url(urljoin(base, link["href"]))))
        except ValueError:
            continue
    if candidates and all(destination in PLACEHOLDER_ICONS for _, destination in candidates):
        return PLACEHOLDER
    candidates = [item for item in candidates if item[1] not in PLACEHOLDER_ICONS]
    # An unsafe first declaration must not prevent a later valid icon.
    for _, destination in sorted(candidates, key=lambda item: item[0])[:8]:
        try:
            resolve_public(urlsplit(destination).hostname, timeout=1)
            return destination
        except FetchError:
            continue
    return None


class SiteIcons:
    """Bound cached metadata and simultaneous homepage requests per API process."""

    def __init__(self):
        self.entries: OrderedDict[str, tuple[float, str | None]] = OrderedDict()
        self.lock = Lock()
        self.slots = BoundedSemaphore(2)

    def get(self, domain: str) -> str | None:
        root = canonical_url(f"https://{domain}/")
        with self.lock:
            entry = self.entries.get(root)
            if entry and entry[0] > time.monotonic():
                self.entries.move_to_end(root)
                return entry[1]
        # A page of logos asks for many at once: wait briefly for a slot rather than answer "no icon" at once.
        if not self.slots.acquire(timeout=2):
            return None
        try:
            try:
                final_url, body = fetch_html(root, timeout=8, max_bytes=262_144)
                icon = declared_icon(final_url, body)
                keep = 86400 if icon is not None else 900  # a homepage that declares no icon rarely changes soon
            except FetchError:
                # A failed read (a slow site, busy DNS) is often brief: the live demo remembered every new domain as
                # iconless for 15 minutes, so eygentic.com and stripe.com both showed a letter.
                icon, keep = None, 60
            with self.lock:
                self.entries[root] = (time.monotonic() + keep, icon)
                self.entries.move_to_end(root)
                while len(self.entries) > 256:
                    self.entries.popitem(last=False)
            return icon
        finally:
            self.slots.release()
