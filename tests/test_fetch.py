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
