"""Agent API, storage, SSE and CLI over the SYNTHETIC providers. No provider keys exist in these tests."""
import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from shortlist.agent import cli
from shortlist.agent.settings import AgentSettings
from shortlist.agent.storage import SQLiteAgentRuns
from shortlist.agent.synthetic import synthetic_providers
from shortlist.api import create_app
from shortlist.config import Settings

LABELS = Path(__file__).parent / "fixtures" / "labels.synthetic.csv"


@pytest.fixture
def client(tmp_path):
    app = create_app(Settings(db_path=tmp_path / "research.sqlite3"))
    service = app.state.agent_service
    service.settings = lambda: AgentSettings()
    service.providers = lambda settings: synthetic_providers()
    with TestClient(app) as test_client:
        test_client.service = service
        yield test_client


def finished(client, run_id):
    client.service.wait(run_id, 20)
    for _ in range(100):
        body = client.get(f"/api/agent/runs/{run_id}").json()
        if body["status"] not in ("queued", "running"):
            return body
        time.sleep(0.05)
    raise AssertionError("Run did not finish")


def test_start_read_list_and_stream(client):
    response = client.post("/api/agent/runs", json={"website": "seller.example"})
    assert response.status_code == 201
    run_id = response.json()["id"]
    body = finished(client, run_id)
    assert body["status"] == "complete" and body["run"]["synthetic"]
    assert {c["verdict"]["kind"] for c in body["run"]["companies"]} == {"shortlisted", "needs_look", "rejected"}
    assert body["events"][0]["seq"] == 1 and body["events"][-1]["stage"] == "run"
    listed = client.get("/api/agent/runs").json()
    assert listed[0]["id"] == run_id and (listed[0]["shortlisted"], listed[0]["needs_look"], listed[0]["rejected"]) == (1, 1, 1)
    with client.stream("GET", f"/api/agent/runs/{run_id}/events?after=3") as stream:
        assert stream.headers["content-type"].startswith("text/event-stream")
        text = "".join(stream.iter_text())
    ids = [int(line[4:]) for line in text.splitlines() if line.startswith("id: ")]
    assert ids[0] == 4 and ids == sorted(ids)
    assert text.rstrip().endswith('data: {"status": "complete"}')


def test_overrides_reevaluate_saved_evidence(client):
    run_id = client.post("/api/agent/runs", json={"website": "https://seller.example/"}).json()["id"]
    finished(client, run_id)
    response = client.post(f"/api/agent/runs/{run_id}/overrides", json={"remove_competitors": ["rival-desk.example"]})
    assert response.status_code == 202
    body = finished(client, run_id)
    kinds = {c["domain"]: c["verdict"]["kind"] for c in body["run"]["companies"]}
    assert kinds["brightkettle.example"] == "needs_look"
    assert any(e["stage"] == "overrides" for e in body["events"])


def test_vague_site_choice_through_the_api(client):
    run_id = client.post("/api/agent/runs", json={"website": "vague.example"}).json()["id"]
    body = finished(client, run_id)
    assert body["status"] == "needs_choice"
    reading = body["run"]["profile"]["interpretations"][0]["id"]
    client.post(f"/api/agent/runs/{run_id}/overrides", json={"interpretation": reading})
    body = finished(client, run_id)
    assert body["status"] == "complete" and body["run"]["profile"]["offer"]["origin"] == "interpretation"
    assert client.post(f"/api/agent/runs/{run_id}/overrides", json={"interpretation": "reading-9"}).status_code in (202, 409)


def test_bad_input_and_missing_runs(client):
    assert client.post("/api/agent/runs", json={"website": "http://seller.example"}).status_code == 422
    assert client.post("/api/agent/runs", json={"website": "https://127.0.0.1"}).status_code == 422
    assert client.post("/api/agent/runs", json={"website": "seller.example", "extra": 1}).status_code == 422
    assert client.get("/api/agent/runs/nope").status_code == 404
    assert client.get("/api/agent/runs/nope/events").status_code == 404


def test_missing_keys_fail_the_run_with_a_clear_message(tmp_path):
    app = create_app(Settings(db_path=tmp_path / "research.sqlite3"))
    app.state.agent_service.settings = lambda: AgentSettings()
    with TestClient(app) as client:
        run_id = client.post("/api/agent/runs", json={"website": "seller.example"}).json()["id"]
        app.state.agent_service.wait(run_id, 10)
        body = client.get(f"/api/agent/runs/{run_id}").json()
    assert body["status"] == "failed" and "META_MODEL_API_KEY" in body["run"]["error"]


def test_hosted_mode_has_no_agent_routes():
    paths = {route.path for route in create_app(Settings(mode="hosted", database_url="postgresql://x",
                                                         supabase_url="https://x.supabase.co",
                                                         supabase_publishable_key="sb_publishable_x",
                                                         app_url="https://app.example")).routes}
    assert not any(path.startswith("/api/agent") for path in paths)


def test_storage_keeps_runs_and_events(tmp_path, run_result, events):
    store = SQLiteAgentRuns(tmp_path / "db.sqlite3")
    store.save(run_result)
    for event in events[:3]:
        store.append_event(run_result.id, event)
    saved = store.get(run_result.id)
    assert saved["result"] == run_result and [e.seq for e in saved["events"]] == [1, 2, 3]
    status, later = store.events(run_result.id, after=2)
    assert status == "complete" and [e.seq for e in later] == [3]


def test_cli_run_and_eval(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SHORTLIST_DB", str(tmp_path / "cli.sqlite3"))
    output = tmp_path / "run.json"
    assert cli.main(["run", "https://seller.example/", "--synthetic", "--output", str(output)]) == 0
    run = json.loads(output.read_text(encoding="utf-8"))
    verdicts = {c["domain"]: c["verdict"] for c in run["companies"]}
    assert {v["kind"] for v in verdicts.values()} == {"shortlisted", "needs_look", "rejected"}
    assert verdicts["brightkettle.example"]["disqualifier"]["quote"]["text"] == "Customer support powered by RivalDesk"
    assert SQLiteAgentRuns(tmp_path / "cli.sqlite3").get(run["id"])["events"]
    capsys.readouterr()
    report = tmp_path / "report.json"
    assert cli.main(["eval", str(LABELS), "--run", str(output), "--output", str(report)]) == 0
    assert "Agreement: 100%" in capsys.readouterr().out
    scored = json.loads(report.read_text(encoding="utf-8"))
    assert scored["agreement"] == 1.0 and scored["shortlisted_precision"] == 1.0 and scored["disqualifier_recall"] == 1.0
    assert scored["cost_per_company_usd"] > 0 and scored["latency_p95_ms"] is not None
    assert cli.main(["eval", str(LABELS), "--run", str(output), "--no-skeptic"]) == 0
    assert "Agreement: 67%" in capsys.readouterr().out  # Without the skeptic an integration reads as current use.
    assert cli.main(["eval", str(LABELS), "--website", "seller.example", "--synthetic"]) == 0
    assert "Agreement: 100%" in capsys.readouterr().out


def test_cli_explains_missing_keys(monkeypatch, capsys, tmp_path):
    for name in ("META_MODEL_API_KEY", "BASETEN_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr("shortlist.agent.settings.load_dotenv", lambda: None)
    assert cli.main(["run", "seller.example", "--no-save"]) == 2
    assert "META_MODEL_API_KEY" in capsys.readouterr().err
