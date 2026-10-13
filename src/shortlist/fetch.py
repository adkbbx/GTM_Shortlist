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
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from shortlist.domain import Source

MAX_BYTES = 1_000_000
MAX_TEXT = 40_000


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


def resolve_public(host: str) -> str:
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
    except OSError as exc:
        raise FetchError("Website DNS is unavailable") from exc
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise FetchError("Website resolves to a non-public address")
    return min(addresses)


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, address: str, timeout: float):
        super().__init__(host, timeout=timeout, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        raw = socket.create_connection((self.address, 443), self.timeout)
        try:
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
        address = resolve_public(parsed.hostname)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise FetchError("Website fetch deadline exceeded")
        connection = PinnedHTTPSConnection(parsed.hostname, address, min(10, remaining))
        try:
            connection.request("GET", urlunsplit(("", "", parsed.path, parsed.query, "")), headers={
                "User-Agent": "GTMShortlist/0.1 (+https://github.com/adkbbx/GTM_Shortlist)",
                "Accept": "text/html,text/plain", "Accept-Encoding": "identity",
            })
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
            for tag in soup(["script", "style", "noscript", "nav", "footer", "svg", "form"]):
                tag.decompose()
            text = "\n".join(line.strip() for line in soup.get_text("\n").splitlines() if line.strip())[:MAX_TEXT]
            if len(text) < 30:
                raise FetchError("Website has insufficient readable text")
            return Source(url=current, company_domain=owner, title=title[:500], text=text,
                          content_hash=hashlib.sha256(body).hexdigest())
        except (OSError, http.client.HTTPException) as exc:
            raise FetchError("Website connection failed") from exc
        finally:
            connection.close()
    raise FetchError("Website exceeded redirect limit")
