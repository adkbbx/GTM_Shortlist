"""Local sample data: the whole flow on invented, labelled data, with no provider, key or network."""
import csv
import io
import json
import socket
import zipfile
from types import SimpleNamespace

from fastapi.testclient import TestClient

from shortlist.api import create_app
from shortlist.config import Settings
from shortlist.export import SAMPLE_NOTE
from shortlist.sample import COMPANIES, PAGE_LABEL, SAMPLE_PROVIDER, match
from shortlist.store import Store
from shortlist.worker import execute_run


def refuse(*args, **kwargs):
    raise AssertionError("A sample run reached a real provider or the network")


class Refused:
    name = "labelled-refused-provider"
    search = seller = market = research = verify = staticmethod(refuse)


def run_sample(store, settings, run_id):
    execute_run(store, settings, run_id, search=Refused(), model=Refused(), fetch=refuse, sample_pace=0)


def test_sample_run_covers_the_whole_flow_offline_and_labelled(tmp_path, monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    settings = Settings(db_path=tmp_path / "sample.sqlite3")
    client = TestClient(create_app(settings))
    store = Store(settings.db_path)
    created = client.post("/api/samples", json={"request_key": "sample-request"})
    assert created.status_code == 201
    run_id = created.json()["id"]
    assert created.json()["sample"] is True
    assert client.post("/api/samples", json={"request_key": "sample-request"}).json()["id"] == run_id

    run_sample(store, settings, run_id)
    draft = client.get(f"/api/runs/{run_id}").json()
    assert draft["status"] == "awaiting_confirmation"
    assert draft["draft"]["offer"].startswith("Onboarding reviews")
    assert draft["market"]["competitors"] and len(draft["market"]["campaigns"]) == 3
    assert draft["seller_source"]["text"].startswith(PAGE_LABEL)

    body = {key: draft["draft"][key] for key in ("offer", "target", "criteria")} | {"exclusions": ["Consumer-only products"]}
    assert client.post(f"/api/runs/{run_id}/confirm", json=body).status_code == 200
    run_sample(store, settings, run_id)
    result = client.get(f"/api/runs/{run_id}").json()
    assert result["status"] in ("ready", "partial") and result["sample"] is True
    assert len(result["records"]) == 3
    assert {record["research"]["domain"] for record in result["records"]} <= set(COMPANIES)
    for record in result["records"]:
        sources = {source["id"]: source for source in record["research"]["sources"]}
        assert all(source["text"].startswith(PAGE_LABEL) for source in sources.values())
        cited = [evidence for finding in record["research"]["findings"] for evidence in finding.get("evidence", [])]
        assert all(evidence["passage"] in sources[evidence["source_id"]]["text"] for evidence in cited)
        assert record["research"]["exclusion_findings"][0]["status"] == "unknown"
    statuses = {finding["status"] for record in result["records"] for finding in record["research"]["findings"]}
    assert statuses == {"supported", "unknown"}  # The sample shows evidence and honest gaps, never invented certainty.
    paid = [attempt for attempt in store.get_run(run_id)["attempts"] if attempt["kind"] in ("search", "model")]
    assert paid and {attempt["provider"] for attempt in paid} == {SAMPLE_PROVIDER}

    exported = json.loads(client.get(f"/api/runs/{run_id}/export?format=json").text)
    assert exported["sample_data"] is True and exported["note"].startswith(SAMPLE_NOTE)
    response = client.get(f"/api/runs/{run_id}/export?format=csv")
    assert 'filename="shortlist-sample-' in response.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(response.text.lstrip("﻿"))))
    assert rows[0][0] == "Data" and len(rows) == 4
    assert all(row[0] == "Sample data, invented" for row in rows[1:])
    workbook = zipfile.ZipFile(io.BytesIO(client.get(f"/api/runs/{run_id}/export?format=xlsx").content))
    assert any(SAMPLE_NOTE in workbook.read(name).decode() for name in workbook.namelist())

    domain = result["records"][0]["research"]["domain"]
    assert client.get(f"/api/runs/{run_id}/site-icon/{domain}").json() == {"url": None}
    reuse = client.post(f"/api/runs/{run_id}/reuse", json={"request_key": "sample-reuse"})
    assert reuse.status_code == 409 and "Sample research" in reuse.json()["detail"]
    real = client.post("/api/sellers", json={"seller_url": "https://eygentic.com", "request_key": "real-request"})
    assert real.json()["sample"] is False


def test_sample_matching_cites_only_literal_statements():
    statements = [("source", sentence, claim) for sentence, claim in COMPANIES["northstar.example"].pages[""].statements]
    assert match("Sells software to business customers", statements)[1].startswith("Northstar Cloud sells")
    assert match("Does not sell software to business customers", statements) is None
    assert match("Headquartered in Germany", statements) is None
    lumenly = [("source", sentence, claim) for sentence, claim in COMPANIES["lumenly.example"].pages[""].statements]
    assert match("Shows a growing customer success team, such as open roles", lumenly) is None


def test_hosted_workspaces_cannot_create_sample_runs(monkeypatch):
    import shortlist.api as api_module
    from shortlist import postgres
    created = []

    class Workspace:
        def __init__(self, *args):
            pass

        def ensure_workspace(self):
            pass

        def create_draft(self, *args, **kwargs):
            created.append(kwargs)

    monkeypatch.setattr(api_module, "verify_user", lambda settings, token: SimpleNamespace(id="labelled-user"))
    monkeypatch.setattr(postgres, "PostgresStore", Workspace)
    settings = Settings(mode="hosted", supabase_url="https://auth.example", app_url="https://app.example",
                        supabase_publishable_key="sb_publishable_fixture", database_url="postgresql://fixture")
    client = TestClient(create_app(settings), base_url="https://app.example")
    response = client.post("/api/samples", json={"request_key": "sample-request"}, headers={"Authorization": "Bearer labelled"})
    assert response.status_code == 404
    assert not created
