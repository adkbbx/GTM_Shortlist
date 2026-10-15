import io
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from shortlist.api import create_app
from shortlist.config import Settings
from shortlist.domain import Criterion, Profile, Source
from shortlist.email_drafts import DraftText, EditEmailDraft, StartEmailDraft, starting_draft
from shortlist.export import export_run
from shortlist.providers import validate_extraction
from shortlist.store import Conflict, Store


@pytest.fixture
def saved(tmp_path):
    store = Store(tmp_path / "drafts.sqlite3")
    profile = Profile(seller_url="https://seller.example/", offer="Customer acquisition experiments for software teams",
                      target="Business software", criteria=(Criterion(id="software", description="Sells software"),))
    run_id = store.create_run(profile, "email-fixture")
    fence = store.claim(run_id)
    source = Source(url="https://company.example/team", company_domain="company.example", title="Labelled fixture",
                    text="We build workflow software. Jane Example is our CEO.", content_hash="a" * 64)
    research = validate_extraction({"name": "Company fixture", "findings": [],
        "company_facts": [{"kind": "description", "evidence": {"source_id": source.id,
            "passage": "We build workflow software.", "claim": "Workflow software for teams."}}],
        "people": [{"name": "Jane Example", "role": "CEO", "evidence": {"source_id": source.id,
            "passage": "Jane Example is our CEO.", "claim": "Jane Example is CEO."}}]},
        profile, source.company_domain, (source,))
    store.save_record(run_id, fence, research)
    store.checkpoint(run_id, fence, "complete", {}, "partial")
    return store, profile, run_id, research


def test_source_template_and_edits_survive_reopen_without_mutating_research(saved):
    store, profile, run_id, research = saved
    command = StartEmailDraft(request_key="start-fixture", person_id=research.people[0].id)
    first = store.write_email_draft(run_id, research.id, command)
    assert "Hi Jane Example," in first.body and profile.offer in first.body
    assert 'Your company page says: "We build workflow software."' in first.body
    assert "@" not in first.body and not first.edited
    assert first.basis == (research.people[0].evidence, research.company_facts[0].evidence)
    assert store.write_email_draft(run_id, research.id, command) == first
    edit = EditEmailDraft(request_key="edit-fixture", previous_id=first.id, subject="A useful conversation",
                          body="Hi Jane,\n\nA manually edited message.\n\nSam")
    updated = store.write_email_draft(run_id, research.id, edit)
    assert updated.id != first.id and updated.edited and updated.basis == first.basis
    assert updated.created_at == first.created_at
    reopened = Store(store.path)
    assert reopened.write_email_draft(run_id, research.id, edit) == updated
    row = reopened.get_run(run_id)["records"][0]
    assert row["email_draft"]["body"] == edit.body
    assert row["research"] == research.model_dump(mode="json")
    assert reopened.get_run(run_id)["attempts"] == []
    with pytest.raises(Conflict, match="changed elsewhere"):
        reopened.write_email_draft(run_id, research.id, command)


def test_concurrent_duplicate_requests_converge_and_stale_edit_cannot_win(saved):
    store, _, run_id, research = saved
    command = StartEmailDraft(request_key="concurrent-start")
    barrier = Barrier(6)

    def start(_):
        barrier.wait(timeout=10)
        return store.write_email_draft(run_id, research.id, command).id

    with ThreadPoolExecutor(max_workers=6) as pool:
        identities = list(pool.map(start, range(6)))
    assert len(set(identities)) == 1
    barrier = Barrier(2)

    def edit(index):
        barrier.wait(timeout=10)
        try:
            return store.write_email_draft(run_id, research.id, EditEmailDraft(request_key=f"concurrent-edit-{index}",
                previous_id=identities[0], subject=f"Edit {index}", body=f"Message {index}")).subject
        except Conflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(edit, range(2)))
    assert outcomes.count("conflict") == 1


def test_request_key_content_drift_and_foreign_person_rejected(saved):
    store, _, run_id, research = saved
    with pytest.raises(KeyError):
        store.write_email_draft("different-run", research.id, StartEmailDraft(request_key="wrong-run"))
    with pytest.raises(Conflict, match="Choose a person"):
        store.write_email_draft(run_id, research.id, StartEmailDraft(request_key="foreign-person", person_id="b" * 32))
    store.write_email_draft(run_id, research.id, StartEmailDraft(request_key="same-key"))
    with pytest.raises(Conflict, match="different content"):
        store.write_email_draft(run_id, research.id, StartEmailDraft(request_key="same-key", person_id=research.people[0].id))


def test_unknown_company_facts_produce_no_invented_personalization(saved):
    _, profile, _, research = saved
    draft = starting_draft(profile, research.model_copy(update={"people": (), "company_facts": ()}), None)
    assert "company page says" not in draft.body and draft.basis == ()
    assert "Hi Company fixture team," in draft.body
    assert "CEO" not in draft.body and "growth" not in draft.body and "funding" not in draft.body


@pytest.mark.parametrize("subject,body", [("Bad\r\nSubject", "Body"), ("Subject", " "), (" ", "Body"),
                                        ("x" * 201, "Body"), ("Subject", "x" * 8001)])
def test_draft_content_boundaries(subject, body):
    with pytest.raises(ValidationError):
        DraftText(subject=subject, body=body)


def test_api_drafts_export_delete_and_validation(saved):
    store, _, run_id, research = saved
    client = TestClient(create_app(Settings(db_path=store.path)))
    path = f"/api/runs/{run_id}/records/{research.id}/email-draft"
    response = client.post(path + "/start", json={"request_key": "api-start", "person_id": research.people[0].id})
    assert response.status_code == 200
    first = response.json()["records"][0]["email_draft"]
    response = client.post(path, json={"request_key": "api-edit", "previous_id": first["id"],
                                      "subject": "Edited subject", "body": "My edited message"})
    assert response.status_code == 200
    assert client.post(path, json={"request_key": "stale-edit", "previous_id": first["id"],
                                  "subject": "Stale", "body": "Must not overwrite"}).status_code == 409
    assert client.post(path, json={"request_key": "bad-edit", "previous_id": first["id"],
                                  "subject": "Bad\nHeader", "body": "Message"}).status_code == 422
    exported = json.loads(export_run(store.get_run(run_id), "json"))
    assert exported["records"][0]["email_draft"]["body"] == "My edited message"
    with ZipFile(io.BytesIO(export_run(store.get_run(run_id), "xlsx"))) as archive:
        assert "Email drafts" in archive.read("xl/workbook.xml").decode()
        draft_sheet = archive.read("xl/worksheets/sheet3.xml").decode()
        assert "My edited message" in draft_sheet and "User edited" in draft_sheet
        assert "https://company.example/team" in draft_sheet
        date = ET.fromstring(draft_sheet).find(".//s:c[@r='G6']/s:v",
            {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"})
        assert date is not None and float(date.text) > 46000
    assert export_run(store.get_run(run_id), "xlsx", accepted_only=True)
    client.delete(f"/api/runs/{run_id}")
    assert client.post(path + "/start", json={"request_key": "deleted-start"}).status_code == 404
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM records").fetchone()[0] == 0
