from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from shortlist.api import create_app
from shortlist.config import Settings
from shortlist.fetch import FetchError
from shortlist.site_icons import SiteIcons, declared_icon
from shortlist.store import Store


@pytest.mark.parametrize(("html", "expected"), [
    ('<link rel="icon" href="assets/eygentic_logo.png">', 'https://eygentic.com/assets/eygentic_logo.png'),
    ('<link rel="shortcut icon" href="/icon.svg?v=2">', 'https://eygentic.com/icon.svg?v=2'),
    ('<base href="/assets/"><link rel="icon" href="icon.png">', 'https://eygentic.com/assets/icon.png'),
    ('<link rel="apple-touch-icon" href="/touch.png"><link rel="icon" href="/small.ico">', 'https://eygentic.com/small.ico'),
    ('<link rel="icon" href="https://cdn.example/icon.png">', 'https://cdn.example/icon.png'),
    ('<link rel="icon" href="data:image/svg+xml,bad"><link rel="icon" href="/safe.png">', 'https://eygentic.com/safe.png'),
    ('<link rel="stylesheet" href="/main.css">', None),
    ('<link rel="icon" href="http://example.com/a.png">', None),
    ('<link rel="icon" href="https://127.0.0.1/a.png">', None),
    ('<link rel="icon" href="https://user:secret@example.com/a.png">', None),
])
def test_declared_icons_resolve_relative_paths_and_reject_unsafe_urls(monkeypatch, html, expected):
    monkeypatch.setattr('shortlist.site_icons.resolve_public', lambda *args, **kwargs: '8.8.8.8')
    assert declared_icon('https://eygentic.com/', f'<html><head>{html}</head></html>'.encode()) == expected


def test_private_dns_icon_is_not_returned(monkeypatch):
    def private(*args, **kwargs):
        raise FetchError('Non-public destination')
    monkeypatch.setattr('shortlist.site_icons.resolve_public', private)
    assert declared_icon('https://eygentic.com/', b'<head><link rel="icon" href="https://private.example/icon.png"></head>') is None


def test_cached_lookup_is_bounded_and_never_records_provider_work(monkeypatch):
    calls = []
    def homepage(url, **kwargs):
        calls.append((url, kwargs))
        return url, b'<head><link rel="icon" href="assets/eygentic_logo.png"></head>'
    monkeypatch.setattr('shortlist.site_icons.fetch_html', homepage)
    monkeypatch.setattr('shortlist.site_icons.resolve_public', lambda *args, **kwargs: '8.8.8.8')
    icons = SiteIcons()
    for _ in range(2):
        assert icons.get('eygentic.com') == 'https://eygentic.com/assets/eygentic_logo.png'
    assert calls == [('https://eygentic.com/', {'timeout': 8, 'max_bytes': 262_144})]
    assert icons.slots.acquire(False) and icons.slots.acquire(False)
    try:
        assert icons.get('different.example') is None
        assert len(calls) == 1
    finally:
        icons.slots.release()
        icons.slots.release()


def test_site_icon_api_restricts_domains_to_saved_run_and_preserves_data(tmp_path, monkeypatch):
    settings = Settings(db_path=tmp_path / 'icons.sqlite3')
    store = Store(settings.db_path)
    run_id = store.create_draft('https://eygentic.com/', 'saved-icon-fixture')
    before = store.get_run(run_id)
    calls = []
    def get_icon(self, domain):
        calls.append(domain)
        return 'https://eygentic.com/assets/eygentic_logo.png'
    monkeypatch.setattr(SiteIcons, 'get', get_icon)
    with TestClient(create_app(settings)) as client:
        assert client.get(f'/api/runs/{run_id}/site-icon/eygentic.com').json() == {'url': 'https://eygentic.com/assets/eygentic_logo.png'}
        for domain in ('unrelated.example', '127.0.0.1', 'eygentic.com:443', 'eygentic.com?bust=1'):
            assert client.get(f'/api/runs/{run_id}/site-icon/{quote(domain, safe="")}').status_code == 404
        assert client.get('/api/runs/missing/site-icon/eygentic.com').status_code == 404
    assert calls == ['eygentic.com']
    assert store.get_run(run_id) == before


def test_suggestion_icon_reads_only_plain_public_domains_without_changing_data(tmp_path, monkeypatch):
    settings = Settings(db_path=tmp_path / 'suggestions.sqlite3')
    calls = []
    def get_icon(self, domain):
        calls.append(domain)
        return 'https://eygentic.com/assets/eygentic_logo.png'
    monkeypatch.setattr(SiteIcons, 'get', get_icon)
    with TestClient(create_app(settings)) as client:
        assert client.get('/api/site-icon/eygentic.com').json() == {'url': 'https://eygentic.com/assets/eygentic_logo.png'}
        for domain in ('127.0.0.1', 'localhost', 'eygentic.com:443', 'eygentic.com?bust=1', 'EYGENTIC.COM', 'user@eygentic.com', 'a..b.com'):
            assert client.get(f'/api/site-icon/{quote(domain, safe="")}').status_code == 404
        assert client.get('/api/runs').json() == []
    assert calls == ['eygentic.com']


def test_hosted_suggestion_icon_requires_authentication_before_any_lookup(monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError('An unauthenticated request must not read site metadata')
    monkeypatch.setattr(SiteIcons, 'get', unexpected)
    settings = Settings(mode='hosted', app_url='https://app.example', supabase_url='https://auth.example',
                        supabase_publishable_key='sb_publishable_fixture', database_url='postgresql://unused')
    with TestClient(create_app(settings), base_url='https://app.example') as client:
        assert client.get('/api/site-icon/eygentic.com').status_code == 401


def test_failed_homepage_is_cached_without_retry(monkeypatch):
    calls = []
    def fail(*args, **kwargs):
        calls.append(1)
        raise FetchError('Unavailable')
    monkeypatch.setattr('shortlist.site_icons.fetch_html', fail)
    icons = SiteIcons()
    assert icons.get('missing.example') is None
    assert icons.get('missing.example') is None
    assert len(calls) == 1


def test_hosted_icon_route_requires_authentication_before_any_lookup(monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError('An unauthenticated request must not read site metadata')
    monkeypatch.setattr(SiteIcons, 'get', unexpected)
    settings = Settings(mode='hosted', app_url='https://app.example', supabase_url='https://auth.example',
                        supabase_publishable_key='sb_publishable_fixture', database_url='postgresql://unused')
    with TestClient(create_app(settings), base_url='https://app.example') as client:
        assert client.get('/api/runs/other-owner/site-icon/eygentic.com').status_code == 401
