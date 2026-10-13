import pytest

from shortlist.fetch import FetchError, canonical_url, domain_of, resolve_public


@pytest.mark.parametrize("url", [
    "http://example.com", "https://127.0.0.1", "https://127.1", "https://2130706433",
    "https://0x7f000001", "https://[::1]", "https://localhost", "https://metadata.google.internal",
    "https://10.0.0.1", "https://169.254.169.254", "https://user:pass@example.com",
    "https://example.com:8080", "file:///etc/passwd", "https://example.com\\@127.0.0.1",
    "https://example.com/\nsecret", "https://a..com", "https://012.0.0.1", "https://[::ffff:127.0.0.1]",
])
def test_unsafe_urls(url):
    with pytest.raises(FetchError):
        canonical_url(url)


def test_canonical_identity():
    assert canonical_url("https://WWW.Example.com:443/page#fragment") == "https://www.example.com/page"
    assert domain_of("https://www.example.com/") == "example.com"


@pytest.mark.parametrize("address", ["127.0.0.1", "10.1.2.3", "169.254.169.254", "::1", "::ffff:127.0.0.1"])
def test_dns_private_addresses_rejected(monkeypatch, address):
    monkeypatch.setattr("socket.getaddrinfo", lambda *args, **kwargs: [(None, None, None, None, (address, 443))])
    with pytest.raises(FetchError):
        resolve_public("public-looking.example")


def test_mixed_public_private_dns_rejected(monkeypatch):
    monkeypatch.setattr("socket.getaddrinfo", lambda *args, **kwargs: [
        (None, None, None, None, ("8.8.8.8", 443)), (None, None, None, None, ("127.0.0.1", 443))])
    with pytest.raises(FetchError):
        resolve_public("example.com")


def test_unicode_path_is_encoded_once():
    url = canonical_url("https://example.com/日本?name=日本")
    assert "%E6%97%A5" in url
    assert canonical_url(url) == url


def test_tls_connect_pins_validated_ip_and_keeps_original_hostname(monkeypatch):
    from shortlist.fetch import PinnedHTTPSConnection
    connected = []
    raw = object()
    monkeypatch.setattr("socket.create_connection", lambda address, timeout: connected.append(address) or raw)
    connection = PinnedHTTPSConnection("example.com", "8.8.8.8", 10)
    class TLSContext:
        def wrap_socket(self, socket, server_hostname):
            assert socket is raw
            assert server_hostname == "example.com"
            return raw
    connection._context = TLSContext()
    connection.connect()
    assert connected == [("8.8.8.8", 443)]


def test_redirect_and_byte_limit_use_actual_fetch_path(monkeypatch):
    from shortlist.fetch import MAX_BYTES, fetch_page
    monkeypatch.setattr("shortlist.fetch.resolve_public", lambda host: "8.8.8.8")
    class Stream:
        def settimeout(self, timeout):
            pass
    class Response:
        status = 302
        def getheader(self, key, default=None):
            return {"Location": "https://127.1/secret", "Content-Type": "text/html"}.get(key, default)
        def read1(self, size):
            return b"x" * size
    class Connection:
        stream_socket = Stream()
        def __init__(self, *args):
            pass
        def request(self, *args, **kwargs):
            pass
        def getresponse(self):
            return Response()
        def close(self):
            pass
    monkeypatch.setattr("shortlist.fetch.PinnedHTTPSConnection", Connection)
    with pytest.raises(FetchError, match="Numeric"):
        fetch_page("https://example.com")
    Response.status = 200
    with pytest.raises(FetchError, match="byte limit"):
        fetch_page("https://example.com")
    assert MAX_BYTES == 1_000_000
