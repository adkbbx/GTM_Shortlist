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
        try:
            candidates.append((priority, canonical_url(urljoin(base, link["href"]))))
        except ValueError:
            continue
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
                keep = 86400 if icon else 900  # a homepage that declares no icon rarely changes soon
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
