"""Public demo app and its file store, over the SYNTHETIC providers. No provider keys, no network."""
import hashlib
import hmac
import time
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from shortlist.agent.files import INTERRUPTED, FileAgentRuns
from shortlist.agent.models import AgentEvent, RunResult, Telemetry
from shortlist.agent.public import PublicSettings, create_public_app
from shortlist.agent.settings import AgentSettings
from shortlist.agent.synthetic import synthetic_providers
from shortlist.domain import utcnow

SECRET = "public-demo-test-secret-0123456789abcdef"
ORIGIN = "https://demo.example"


def public_settings(tmp_path, **changes):
    dist = tmp_path / "dist"
    dist.mkdir(parents=True, exist_ok=True)
    (dist / "index.html").write_text("<html><head><title>Demo</title></head><body></body></html>", encoding="utf-8")
    return PublicSettings(app_url=ORIGIN, secret=SECRET, data_dir=tmp_path / "runs", dist_dir=dist, **changes)


def make_client(tmp_path, **changes):
    app = create_public_app(public_settings(tmp_path, **changes), agent_settings=lambda: AgentSettings(),
                            providers=lambda settings: synthetic_providers())
    client = TestClient(app, base_url=ORIGIN)
    client.service, client.policy = app.state.agent_service, app.state.public_policy
    return client


@pytest.fixture
def client(tmp_path):
    with make_client(tmp_path) as test_client:
        yield test_client


def finished(client, run_id):
    client.service.wait(run_id, 20)
    for _ in range(100):
        body = client.get(f"/api/agent/runs/{run_id}").json()
        if body["status"] not in ("queued", "running"):
            return body
        time.sleep(0.05)
    raise AssertionError("Run did not finish")


def token_for(run_id):
    return hmac.new(SECRET.encode(), ("edit:" + run_id).encode(), hashlib.sha256).hexdigest()


def saved_run(status="complete", cost=0.0):
    return RunResult(website="https://seller.example/", status=status, telemetry=Telemetry(budget_usd=1.0, cost_usd=cost))


def test_start_caps_companies_returns_edit_token_and_lists_nothing(client):
    response = client.post("/api/agent/runs", json={"website": "seller.example", "overrides": {"company_count": 20}})
    assert response.status_code == 201
    started = response.json()
    assert started["edit_token"] == token_for(started["id"])
    body = finished(client, started["id"])
    assert body["status"] == "complete" and body["run"]["company_count"] == 5 and body["run"]["synthetic"]
    assert client.get("/api/agent/runs").json() == []
    health = client.get("/api/health").json()
    assert health["mode"] == "public" and health["max_companies"] == 5 and health["turnstile_site_key"] is None


def test_shared_link_reads_but_only_the_starter_can_correct(client):
    started = client.post("/api/agent/runs", json={"website": "seller.example"}).json()
    finished(client, started["id"])
    path = f"/api/agent/runs/{started['id']}"
    assert client.get(path).status_code == 200
    refused = client.post(path + "/overrides", json={"exclusions": ["trailgear.example"]})
    assert refused.status_code == 403 and "Only the browser that started" in refused.json()["detail"]
    wrong = client.post(path + "/overrides", json={"exclusions": ["trailgear.example"]}, headers={"X-Agent-Edit-Token": "0" * 64})
    assert wrong.status_code == 403
    allowed = client.post(path + "/overrides", json={"exclusions": ["trailgear.example"]},
                          headers={"X-Agent-Edit-Token": started["edit_token"]})
    assert allowed.status_code == 202
    finished(client, started["id"])


def test_hourly_limit_per_visitor(tmp_path):
    with make_client(tmp_path, runs_per_hour=2, max_active=10) as client:
        ids = [client.post("/api/agent/runs", json={"website": "seller.example"}).json()["id"] for _ in range(2)]
        limited = client.post("/api/agent/runs", json={"website": "seller.example"})
        assert limited.status_code == 429 and "2 searches an hour" in limited.json()["detail"]
        for run_id in ids:
            finished(client, run_id)
        now = time.monotonic()
        client.policy.clock = lambda: now + 3601
        assert client.post("/api/agent/runs", json={"website": "seller.example"}).status_code == 201


def test_forwarded_address_counts_only_behind_a_trusted_proxy(tmp_path):
    with make_client(tmp_path, runs_per_hour=1, max_active=10, trust_proxy=True) as client:
        for address in ("203.0.113.5", "203.0.113.6"):
            response = client.post("/api/agent/runs", json={"website": "seller.example"}, headers={"X-Forwarded-For": address})
            assert response.status_code == 201
        again = client.post("/api/agent/runs", json={"website": "seller.example"}, headers={"X-Forwarded-For": "203.0.113.5, 10.0.0.1"})
        assert again.status_code == 429
    with make_client(tmp_path / "direct", runs_per_hour=1, max_active=10) as client:
        assert client.post("/api/agent/runs", json={"website": "seller.example"}, headers={"X-Forwarded-For": "203.0.113.7"}).status_code == 201
        spoofed = client.post("/api/agent/runs", json={"website": "seller.example"}, headers={"X-Forwarded-For": "203.0.113.8"})
        assert spoofed.status_code == 429


def test_daily_budget_and_busy_limits(tmp_path):
    with make_client(tmp_path, daily_usd=1.5, max_active=1) as client:
        client.service.store.save(saved_run(cost=0.6))
        refused = client.post("/api/agent/runs", json={"website": "seller.example"})
        assert refused.status_code == 503 and "budget is used up" in refused.json()["detail"]
    with make_client(tmp_path / "busy", max_active=1) as client:
        client.service.store.save(saved_run(status="running"))
        busy = client.post("/api/agent/runs", json={"website": "seller.example"})
        assert busy.status_code == 503 and "busy" in busy.json()["detail"]


def test_turnstile_is_checked_before_any_work(tmp_path):
    with make_client(tmp_path, turnstile_site_key="site-key", turnstile_secret="turnstile-secret") as client:
        checked = []
        client.policy.verify = lambda secret, token, address: checked.append(token) or token == "good"
        assert client.get("/api/health").json()["turnstile_site_key"] == "site-key"
        assert client.post("/api/agent/runs", json={"website": "seller.example"}).status_code == 403
        assert client.post("/api/agent/runs", json={"website": "seller.example", "turnstile": "bad"}).status_code == 403
        good = client.post("/api/agent/runs", json={"website": "seller.example", "turnstile": "good"})
        assert good.status_code == 201 and checked == ["bad", "good"]
        finished(client, good.json()["id"])


def test_origin_host_and_run_ids_are_checked(client, tmp_path):
    crossed = client.post("/api/agent/runs", json={"website": "seller.example"}, headers={"Origin": "https://evil.example"})
    assert crossed.status_code == 403
    for bad in ("not-a-run", "A" * 32, "0" * 31):
        assert client.get(f"/api/agent/runs/{bad}").status_code == 404
    assert client.get("/api/agent/runs/" + "0" * 32).status_code == 404
    with TestClient(client.app, base_url="https://other.example") as stranger:
        assert stranger.get("/api/health").status_code == 400


def test_ui_page_is_marked_agent_only(client):
    page = client.get("/?agent=" + "0" * 32)
    assert page.status_code == 200 and '<meta name="shortlist-start-flow" content="agent-only">' in page.text
    assert page.headers["x-frame-options"] == "DENY"


def test_settings_refuse_weak_or_mismatched_configuration(tmp_path):
    with pytest.raises(ValidationError):
        PublicSettings(app_url=ORIGIN, secret="short")
    with pytest.raises(ValidationError):
        PublicSettings(app_url="http://demo.example", secret=SECRET)
    with pytest.raises(ValidationError):
        PublicSettings(app_url=ORIGIN + "/path", secret=SECRET)
    with pytest.raises(ValidationError):
        PublicSettings(app_url=ORIGIN, secret=SECRET, turnstile_site_key="only-half")
    assert PublicSettings(app_url="http://127.0.0.1:8020", secret=SECRET).app_url == "http://127.0.0.1:8020"


def test_file_store_round_trip_usage_and_restart_recovery(tmp_path):
    writes = []
    store = FileAgentRuns(tmp_path, after_write=lambda: writes.append(1))
    done, working = saved_run(cost=0.25), saved_run(status="running", cost=0.1)
    store.create(done)
    store.save(working)
    with pytest.raises(ValueError):
        store.create(done)
    for message in ("one", "two", "three"):
        store.append_event(done.id, AgentEvent(stage="run", message=message))
    status, events = store.events(done.id, after=1)
    assert status == "complete" and [(e.seq, e.message) for e in events] == [(2, "two"), (3, "three")]
    assert store.get(done.id)["result"].telemetry.cost_usd == 0.25
    spent, active = store.usage_since(utcnow() - timedelta(hours=1))
    assert spent == pytest.approx(0.35) and active == 1
    assert store.usage_since(utcnow() + timedelta(hours=1))[0] == 0
    assert {item["id"] for item in store.list()} == {done.id, working.id}
    assert writes and not list(tmp_path.glob("*.tmp"))

    assert FileAgentRuns(tmp_path).recover_interrupted() == 1
    recovered = store.get(working.id)
    assert recovered["status"] == "failed" and recovered["result"].error == INTERRUPTED
    assert store.get(done.id)["events"][-1].message == "three"
    with pytest.raises(KeyError):
        store.get("../" + done.id)


def test_shipped_examples_are_real_finished_searches_that_open_read_only(tmp_path):
    from shortlist.agent.public import SHOWCASE

    files = sorted(SHOWCASE.glob("*.json"))
    assert files  # real live runs, saved 1 November; see docs/PROGRESS.md
    for path in files:
        run = RunResult.model_validate_json(path.read_text(encoding="utf-8"))
        assert run.status == "complete" and not run.synthetic
        assert all(aside.previous_run is None for aside in run.set_aside)  # no links to runs the demo does not have
        for company in run.companies:
            supported = {d.evidence_id for d in company.decisions if d.decision == "supports"}
            assert company.pitch is None or (company.verdict.kind == "shortlisted"
                                             and set(company.pitch.evidence_ids) <= supported)
    with make_client(tmp_path) as client:
        examples = client.get("/api/health").json()["examples"]
        assert {e["id"] for e in examples} == {p.stem for p in files}
        example = examples[0]
        shown = client.get(f"/api/agent/runs/{example['id']}").json()
        assert shown["run"]["status"] == "complete"
        assert len(shown["events"]) > 20 and shown["events"][-1]["message"].startswith("Done: ")
        assert [e["seq"] for e in shown["events"]] == list(range(1, len(shown["events"]) + 1))
        refused = client.post(f"/api/agent/runs/{example['id']}/overrides", json={"exclusions": ["x.example"]})
        assert refused.status_code == 403


def test_a_shared_finished_board_has_a_link_preview(tmp_path):
    with make_client(tmp_path) as client:
        example = next(e for e in client.get("/api/health").json()["examples"] if e["shortlisted"] == 2)
        page = client.get(f"/?agent={example['id']}").text
        assert '<meta property="og:title" content="2 companies that need what eygentic.com sells">' in page
        description = page.split('property="og:description" content="', 1)[1].split('"', 1)[0]
        assert description.startswith("Shortlisted: ") and "checked by Muse Spark Open" in description
        assert 'name="twitter:card" content="summary"' in page
        assert "og:title" not in client.get("/?agent=" + "0" * 32).text  # unknown run: no preview
        assert "og:title" not in client.get("/?agent=../etc").text


def test_a_finished_board_downloads_as_csv_with_quotes_and_opening_lines(tmp_path):
    import csv
    import io

    from shortlist.agent.export import cell

    with make_client(tmp_path) as client:
        example = next(e for e in client.get("/api/health").json()["examples"] if e["shortlisted"] == 2)
        response = client.get(f"/api/agent/runs/{example['id']}/shortlist.csv")
        assert response.status_code == 200 and response.headers["content-type"].startswith("text/csv")
        assert response.headers["content-disposition"].startswith('attachment; filename="shortlist-eygentic.com-')
        rows = list(csv.DictReader(io.StringIO(response.text.removeprefix("\ufeff"))))
        shortlisted = [r for r in rows if r["verdict"] == "Shortlisted"]
        assert len(shortlisted) == 2 and rows[0]["verdict"] == "Shortlisted"
        assert all(r["opening_line"] and r["opening_line_checked"] == "yes" and '" (http' in r["supporting_quotes"]
                   for r in shortlisted)
        assert client.get("/api/agent/runs/" + "0" * 32 + "/shortlist.csv").status_code == 404
    assert cell("=HYPERLINK(1)") == "'=HYPERLINK(1)" and cell("@SUM") == "'@SUM" and cell("plain\ntext") == "plain text"


def test_examples_can_be_turned_off(tmp_path):
    with make_client(tmp_path, showcase_dir=None) as client:
        assert client.get("/api/health").json()["examples"] == []
