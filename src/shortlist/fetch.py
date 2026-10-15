"""Bounded HTTPS fetching. Resolve once and connect to that validated address.

The original hostname is retained for TLS certificate verification and Host.
Every redirect repeats validation. No cookies, credentials, proxy or compressed bodies.
"""
import hashlib
import http.client
import ipaddress
import re
import socket
import ssl
import time
from concurrent.futures import Future
from threading import BoundedSemaphore, Thread
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

import certifi
from bs4 import BeautifulSoup

from shortlist.domain import Source

MAX_BYTES = 1_000_000
MAX_TEXT = 40_000
DNS_SLOTS = BoundedSemaphore(4)


class FetchError(ValueError):
    pass


def canonical_url(url: str) -> str:
    if len(url) > 2048 or any(ord(c) < 33 for c in url) or "\\" in url:
        raise FetchError("Invalid URL")
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise FetchError("Invalid URL") from exc
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise FetchError("Use a public HTTPS website without credentials")
    if port not in (None, 443):
        raise FetchError("Only HTTPS port 443 is supported")
    try:
        host = parsed.hostname.encode("idna").decode("ascii").lower().rstrip(".")
    except UnicodeError as exc:
        raise FetchError("Invalid website hostname") from exc
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", host):
        raise FetchError("Invalid website hostname")
    if len(host) > 253 or "." not in host or any(
        not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", part) for part in host.split(".")
    ):
        raise FetchError("Use a public website domain")
    if host.endswith((".local", ".internal", ".localhost")) or host == "localhost":
        raise FetchError("Private website is not permitted")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise FetchError("Use a website domain, not an IP address")
    # Reject abbreviated/encoded address forms such as 127.1 and 0x7f000001.
    if host.split(".")[-1].isdigit():
        raise FetchError("Numeric website hostname is not permitted")
    path = quote(parsed.path or "/", safe="/%:@!$&'()*+,;=-._~")
    query = quote(parsed.query, safe="%:@!$&'()*+,;=/?-._~")
    return urlunsplit(("https", host, path, query, ""))


def domain_of(url: str) -> str:
    host = urlsplit(canonical_url(url)).hostname
    return host.removeprefix("www.")


def activity_links(url: str, soup: BeautifulSoup) -> tuple[str, ...]:
    """One observed first-party activity page; no recursive crawl or guessed path."""
    owner = domain_of(url)
    priorities = {"news": 0, "newsroom": 0, "announcements": 0, "press": 1,
                  "careers": 2, "jobs": 2, "blog": 3}
    selected = {}
    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href")
        if not isinstance(href, str):
            continue
        try:
            destination = canonical_url(urljoin(url, href))
            parsed = urlsplit(destination)
            parts = [part.casefold() for part in parsed.path.split("/") if part]
            if domain_of(destination) != owner or parsed.query or destination == canonical_url(url):
                continue
            if not 1 <= len(parts) <= 3 or parts[0] not in priorities:
                continue
            selected[destination] = priorities[parts[0]]
        except ValueError:
            continue
    return tuple(sorted(selected, key=lambda link: (selected[link], link))[:1])


def research_links(url: str, soup: BeautifulSoup) -> tuple[str, ...]:
    """Select two observed company/team/product links, never invented paths."""
    owner = domain_of(url)
    priorities = {"about": 0, "about-us": 0, "company": 0, "team": 1, "leadership": 1,
                  "our-team": 1, "management": 1, "product": 2, "products": 2, "platform": 2, "pricing": 3}
    selected = {}
    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href")
        if not isinstance(href, str):
            continue
        try:
            destination = canonical_url(urljoin(url, href))
            parsed = urlsplit(destination)
            if domain_of(destination) != owner or parsed.query or destination == canonical_url(url):
                continue
            parts = [part.lower() for part in parsed.path.split("/") if part]
            # Keep static informational pages; avoid arbitrary paths merely containing a keyword.
            if not 1 <= len(parts) <= 2 or not any(part in priorities for part in parts):
                continue
            selected[destination] = min(priorities[part] for part in parts if part in priorities)
        except ValueError:
            continue
    return tuple(sorted(selected, key=lambda link: (selected[link], link))[:2])


def resolve_public(host: str, timeout: float = 5) -> str:
    # System DNS cannot be cancelled reliably. Quarantine at most four outstanding
    # lookups in daemon threads; timeouts do not accumulate unbounded workers.
    if timeout <= 0:
        raise FetchError("Website fetch deadline exceeded")
    if not DNS_SLOTS.acquire(blocking=False):
        raise FetchError("Website DNS capacity is busy; try a new run later")
    result = Future()

    def lookup():
        try:
            result.set_result(socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM))
        except OSError as exc:
            result.set_exception(exc)
        finally:
            DNS_SLOTS.release()

    try:
        Thread(target=lookup, name="shortlist-dns", daemon=True).start()
    except RuntimeError as exc:
        DNS_SLOTS.release()
        raise FetchError("Website DNS is unavailable") from exc
    try:
        addresses = {item[4][0] for item in result.result(timeout=timeout)}
    except TimeoutError as exc:
        raise FetchError("Website DNS deadline exceeded") from exc
    except OSError as exc:
        raise FetchError("Website DNS is unavailable") from exc
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise FetchError("Website resolves to a non-public address")
    return min(addresses)


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, address: str, timeout: float):
        # Match the public CA bundle used by our HTTPX provider clients. Windows
        # system roots can select an expired chain for an otherwise valid site.
        super().__init__(host, timeout=timeout, context=ssl.create_default_context(cafile=certifi.where()))
        self.address = address

    def connect(self):
        deadline = time.monotonic() + self.timeout
        raw = socket.create_connection((self.address, 443), self.timeout)
        try:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("TLS deadline exceeded")
            raw.settimeout(remaining)
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
            self.stream_socket = self.sock
        except BaseException:
            raw.close()
            raise


def fetch_page(url: str, expected_domain: str | None = None) -> Source:
    current = canonical_url(url)
    owner = expected_domain or domain_of(current)
    deadline = time.monotonic() + 35
    for _ in range(4):
        if domain_of(current) != owner:
            raise FetchError("Redirect changed company identity; manual verification required")
        parsed = urlsplit(current)
        address = resolve_public(parsed.hostname, timeout=min(5, deadline - time.monotonic()))
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise FetchError("Website fetch deadline exceeded")
        connection = PinnedHTTPSConnection(parsed.hostname, address, min(10, remaining))
        try:
            connection.connect()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise FetchError("Website fetch deadline exceeded")
            connection.stream_socket.settimeout(min(10, remaining))
            connection.request("GET", urlunsplit(("", "", parsed.path, parsed.query, "")), headers={
                "User-Agent": "GTMShortlist/0.1 (+https://github.com/adkbbx/GTM_Shortlist)",
                "Accept": "text/html,text/plain", "Accept-Encoding": "identity",
            })
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise FetchError("Website fetch deadline exceeded")
            connection.stream_socket.settimeout(min(10, remaining))
            response = connection.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                location = response.getheader("Location")
                if not location:
                    raise FetchError("Redirect has no destination")
                current = canonical_url(urljoin(current, location))
                continue
            if response.status != 200:
                raise FetchError(f"Website returned HTTP {response.status}")
            content_type = response.getheader("Content-Type", "").lower()
            if not any(kind in content_type for kind in ("text/html", "text/plain", "application/xhtml+xml")):
                raise FetchError("Website did not return a supported text page")
            if response.getheader("Content-Encoding", "identity").lower() != "identity":
                raise FetchError("Compressed response is not supported")
            chunks = []
            size = 0
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise FetchError("Website fetch deadline exceeded")
                connection.stream_socket.settimeout(min(10, remaining))
                chunk = response.read1(min(65536, MAX_BYTES + 1 - size))
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
                if size > MAX_BYTES:
                    raise FetchError("Website page exceeds byte limit")
            body = b"".join(chunks)
            soup = BeautifulSoup(body, "html.parser")
            title = soup.title.get_text(" ", strip=True) if soup.title else parsed.hostname
            links = research_links(current, soup)
            activity = activity_links(current, soup)
            for tag in soup(["script", "style", "noscript", "nav", "footer", "svg", "form"]):
                tag.decompose()
            text = "\n".join(line.strip() for line in soup.get_text("\n").splitlines() if line.strip())[:MAX_TEXT]
            if len(text) < 30:
                raise FetchError("Website has insufficient readable text")
            return Source(url=current, company_domain=owner, title=title[:500], text=text,
                          content_hash=hashlib.sha256(body).hexdigest(), research_links=links, activity_links=activity)
        except (OSError, http.client.HTTPException) as exc:
            raise FetchError("Website connection failed") from exc
        finally:
            connection.close()
    raise FetchError("Website exceeded redirect limit")
