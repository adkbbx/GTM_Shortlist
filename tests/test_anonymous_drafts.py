"""Drafts before signup: switch, bot check, visitor limits, claim scoping and the one-fetch, one-model-call worker step.
Database functions, privileges and claiming are exercised against PostgreSQL in test_postgres.py."""
import hashlib
import json
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from shortlist import postgres
from shortlist.api import create_app
from shortlist.config import Settings
from shortlist.domain import Criterion, Source
from shortlist.fetch import FetchError
from shortlist.providers import ProviderError, SellerDraft
from shortlist.turnstile import verify_turnstile
from shortlist.worker import execute_draft

HOSTED = {"mode": "hosted", "supabase_url": "https://auth.example", "app_url": "https://app.example",
          "supabase_publishable_key": "sb_publishable_fixture", "database_url": "postgresql://fixture"}
SWITCHED_ON = {**HOSTED, "anonymous_drafts": True, "turnstile_site_key": "0x4AAAAlabelled",
               "turnstile_secret_key": "labelled-turnstile-secret", "client_address_header": "CF-Connecting-IP"}


class Drafts:
    """Stands in for the claim-scoped database functions."""
    outcome = "created"

    def __init__(self):
        self.created, self.saved = [], {}

    def __call__(self, dsn, workspace_id, **flags):
        assert flags == {"anonymous": True} and workspace_id is None
        return self

    def create_anonymous_draft(self, draft_id, claim_hash, website, visitors, daily_cap):
        self.created.append((draft_id, claim_hash, website, visitors, daily_cap))
        if self.outcome == "created":
            self.saved[str(draft_id)] = claim_hash
        return self.outcome

    def read_anonymous_draft(self, draft_id, claim_hash):
        if self.saved.get(str(draft_id)) != claim_hash:
            return None
        return {"status": "running", "website": "https://eygentic.com/", "draft": None, "error": None,
                "events": json.dumps([{"label": "Reading eygentic.com", "state": "started",
                                       "created_at": "2026-10-18T10:00:00+00:00"}])}


@pytest.fixture
def drafts(monkeypatch):
    fake = Drafts()
    monkeypatch.setattr(postgres, "PostgresStore", fake)
    return fake


def client(settings, monkeypatch, passed=True):
    checks = []
    monkeypatch.setattr("shortlist.api.verify_turnstile", lambda secret, token, address: checks.append(address) or passed)
    return TestClient(create_app(Settings(**settings)), base_url="https://app.example"), checks


def body(website="eygentic.com"):
    return {"website": website, "browser_id": str(uuid4()), "turnstile_token": "labelled-turnstile-token"}


def test_switch_needs_hosted_mode_and_both_turnstile_keys():
    with pytest.raises(ValidationError, match="TURNSTILE_SITE_KEY"):
        Settings(**{**SWITCHED_ON, "turnstile_secret_key": ""})
    with pytest.raises(ValidationError, match="hosted mode"):
        Settings(anonymous_drafts=True, turnstile_site_key="0x4AAAAlabelled", turnstile_secret_key="labelled-secret")


def test_switched_off_drafts_are_refused_and_not_advertised(drafts, monkeypatch):
    app, checks = client(HOSTED, monkeypatch)
    assert app.get("/api/auth/setup").json()["draft_site_key"] is None
    assert app.post("/api/drafts", json=body()).status_code == 404
    assert not checks and not drafts.created


def test_draft_needs_a_website_and_a_passing_browser_check(drafts, monkeypatch):
    app, checks = client(SWITCHED_ON, monkeypatch, passed=False)
    assert app.get("/api/auth/setup").json()["draft_site_key"] == "0x4AAAAlabelled"
    assert app.post("/api/drafts", json=body("Eygentic")).status_code == 422  # A company name would need a search.
    assert app.post("/api/drafts", json=body("http://127.0.0.1")).status_code == 422
    refused = app.post("/api/drafts", json=body(), headers={"CF-Connecting-IP": "203.0.113.9"})
    assert refused.status_code == 403 and checks == ["203.0.113.9"] and not drafts.created


def test_created_draft_keeps_only_keyed_hashes_and_is_read_with_its_claim_token(drafts, monkeypatch):
    app, _ = client(SWITCHED_ON, monkeypatch)
    sent = body()
    created = app.post("/api/drafts", json=sent, headers={"CF-Connecting-IP": "203.0.113.9"})
    assert created.status_code == 201
    draft_id, token = created.json()["id"], created.json()["claim_token"]
    _, claim, website, visitors, cap = drafts.created[0]
    assert claim == hashlib.sha256(token.encode()).hexdigest() and website == "https://eygentic.com/" and cap == 50
    assert len(visitors) == 2 and len(set(visitors)) == 2
    stored = json.dumps(drafts.created[0], default=str)
    assert "203.0.113.9" not in stored and sent["browser_id"] not in stored and token not in stored
    view = app.get(f"/api/drafts/{draft_id}", headers={"X-Draft-Claim": token}).json()
    assert view["status"] == "running" and view["events"][0]["label"] == "Reading eygentic.com"
    assert app.get(f"/api/drafts/{draft_id}", headers={"X-Draft-Claim": "another-browsers-claim-token"}).status_code == 404
    assert app.get(f"/api/drafts/{draft_id}").status_code == 422


@pytest.mark.parametrize("outcome,message", [("visitor_limit", "already drafted"), ("daily_limit", "paused for today")])
def test_visitor_and_daily_limits_ask_for_sign_in(drafts, monkeypatch, outcome, message):
    drafts.outcome = outcome
    app, _ = client(SWITCHED_ON, monkeypatch)
    refused = app.post("/api/drafts", json=body())
    assert refused.status_code == 429 and message in refused.json()["detail"] and "Sign in" in refused.json()["detail"]


def test_local_workspaces_have_no_drafts_before_signup(tmp_path):
    app = TestClient(create_app(Settings(db_path=tmp_path / "local.sqlite3")))
    assert app.post("/api/drafts", json=body()).status_code == 404
    assert app.get(f"/api/drafts/{uuid4()}", headers={"X-Draft-Claim": "x" * 30}).status_code == 404
    assert app.post(f"/api/drafts/{uuid4()}/claim", headers={"X-Draft-Claim": "x" * 30}).status_code == 404


class Leased:
    def __init__(self, website="https://eygentic.com/"):
        self.website, self.saves = website, []

    def lease_anonymous_draft(self, draft_id):
        return self.website

    def save_anonymous_draft(self, draft_id, **fields):
        self.saves.append(json.loads(json.dumps(fields, default=str)))


def page(url, expected_domain=None):
    text = "Labelled fixture page. We review customer onboarding for B2B software teams."
    return Source(url=url, company_domain="eygentic.com", title="Labelled fixture", text=text,
                  content_hash=hashlib.sha256(text.encode()).hexdigest())


class Model:
    name = "labelled-fixture-model"

    def __init__(self, error=None):
        self.error, self.calls = error, 0

    def seller(self, source):
        self.calls += 1
        if self.error:
            raise self.error
        return SellerDraft(offer="Onboarding reviews for B2B software teams", target="B2B software companies",
                           criteria=[Criterion(id="software", description="Sells software to businesses")])

    def search(self, *args):
        raise AssertionError("A draft before signup never searches")


def test_draft_step_fetches_once_drafts_once_and_saves_progress():
    store, model = Leased(), Model()
    assert execute_draft(store, Settings(), "draft-1", model=model, fetch=page)
    final = store.saves[-1]
    assert final["status"] == "ready" and model.calls == 1
    assert json.loads(final["draft"])["offer"].startswith("Onboarding reviews")
    assert json.loads(final["source"])["company_domain"] == "eygentic.com"
    assert [event["state"] for event in final["events"]] == ["started", "succeeded", "started", "succeeded"]
    assert len(store.saves) == 4  # Progress is visible while the page is read and the draft is written.


def test_unreadable_page_and_failed_model_both_end_as_failed_drafts():
    def unreadable(url, expected_domain=None):
        raise FetchError("Labelled unreadable page")
    store = Leased()
    execute_draft(store, Settings(), "draft-2", model=Model(), fetch=unreadable)
    assert store.saves[-1]["status"] == "failed" and store.saves[-1]["source"] is None
    assert "couldn't read that website" in store.saves[-1]["error"]
    store = Leased()
    execute_draft(store, Settings(), "draft-3", model=Model(ProviderError("Labelled model outage")), fetch=page)
    assert store.saves[-1]["status"] == "failed" and json.loads(store.saves[-1]["source"])["url"] == "https://eygentic.com/"
    assert "Labelled model outage" not in store.saves[-1]["error"]  # Provider detail stays out of the public view.


def test_a_draft_another_worker_holds_is_left_alone():
    store = SimpleNamespace(lease_anonymous_draft=lambda draft_id: None)
    assert not execute_draft(store, Settings(), "draft-4", model=Model(AssertionError("dispatched")), fetch=page)


@pytest.mark.parametrize("response,expected", [
    (httpx.Response(200, json={"success": True}), True),
    (httpx.Response(200, json={"success": False, "error-codes": ["invalid-input-response"]}), False),
    (httpx.Response(200, json={"success": "true"}), False),
    (httpx.Response(500), False),
    (httpx.Response(200, text="not json"), False),
])
def test_turnstile_counts_only_an_explicit_success(response, expected):
    seen = []

    def endpoint(request):
        seen.append(request.content.decode())
        return response
    assert verify_turnstile(Settings(**SWITCHED_ON).turnstile_secret_key, "labelled-token", "203.0.113.9",
                            transport=httpx.MockTransport(endpoint)) is expected
    assert "remoteip=203.0.113.9" in seen[0] and "response=labelled-token" in seen[0]


def test_turnstile_timeout_fails_closed():
    def endpoint(request):
        raise httpx.ConnectTimeout("labelled timeout")
    assert not verify_turnstile(Settings(**SWITCHED_ON).turnstile_secret_key, "labelled-token",
                                transport=httpx.MockTransport(endpoint))
