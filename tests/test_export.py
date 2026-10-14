import csv
import io
from copy import deepcopy
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest

from shortlist.export import export_run


@pytest.fixture
def customer_run():
    research = {"id": "record-one", "domain": "example.com", "name": 'Example, "AI" 日本',
                "qualification": "needs_verification", "status": "partial",
                "findings": [{"status": "supported", "criterion_id": "ai", "evidence": [{
                    "source_id": "source-one", "claim": "Offers AI software", "passage": "We build AI software for teams."}]},
                    {"status": "unknown", "criterion_id": "private", "reason": "Ownership is not stated."}],
                "exclusion_findings": [{"status": "unknown", "exclusion_id": "exclude-1", "reason": "Product model not clear."}],
                "sources": [{"id": "source-one", "url": "https://example.com/about", "title": "About Example",
                             "text": "FULL PAGE TEXT SHOULD STAY IN JSON", "company_domain": "example.com",
                             "content_hash": "a" * 64, "retrieved_at": "2026-10-14T17:00:00+00:00", "published_at": None}],
                "hypotheses": [{"text": "May need help with expansion", "assumptions": ["Expansion plans are not confirmed"]}],
                "unknowns": ["Ownership is not stated."]}
    return {"id": "run-one", "profile": {"target": "Private AI software companies",
            "criteria": [{"id": "ai", "description": "Offers AI software"}, {"id": "private", "description": "Privately held"}],
            "exclusions": ["Consultancy without a product"]}, "status": "partial", "checkpoint": {},
            "records": [{"research": research, "review": {"decision": "accepted", "reason": "Human review note"},
                         "operator_review": {"annotation": {"outcome": "needs_research", "reviewer": "Reviewer",
                                                            "note": "Check ownership", "source_ids": []},
                                             "reviewed_at": "2026-10-14T17:01:00+00:00"}}]}


def workbook_xml(content):
    with ZipFile(io.BytesIO(content)) as archive:
        assert archive.testzip() is None
        return {name: ET.fromstring(archive.read(name)) for name in archive.namelist()}


def test_customer_workbook_preserves_evidence_and_separates_decisions(customer_run):
    before = deepcopy(customer_run)
    package = workbook_xml(export_run(customer_run, "xlsx"))
    ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    assert [s.attrib["name"] for s in package["xl/workbook.xml"].findall("s:sheets/s:sheet", ns)] == ["Shortlist", "Evidence"]
    summary = " ".join(package["xl/worksheets/sheet1.xml"].itertext())
    evidence = " ".join(package["xl/worksheets/sheet2.xml"].itertext())
    assert "Fit unverified" in summary and "Accepted" in summary
    assert "Human review note" in summary and "Reviewer: Check ownership" in summary
    assert "Privately held" in summary and "Consultancy without a product" in summary
    assert "Ownership is not stated." in evidence and "We build AI software for teams." in evidence
    assert "Hypothesis" in evidence and "Unverified" in evidence and "Expansion plans are not confirmed" in evidence
    assert "https://example.com/about" in evidence and "Not provided" in evidence
    assert "FULL PAGE TEXT" not in summary + evidence
    date = package["xl/worksheets/sheet2.xml"].find(".//s:c[@r='H5']/s:v", ns)
    assert date is not None and float(date.text) > 46000  # A sortable numeric Excel date, not an ISO text label.
    assert customer_run == before


def test_customer_export_filter_empty_and_csv_readability(customer_run):
    rejected = deepcopy(customer_run["records"][0])
    rejected["research"]["name"] = "Rejected business"
    rejected["review"]["decision"] = "rejected"
    customer_run["records"].append(rejected)
    package = workbook_xml(export_run(customer_run, "xlsx", accepted_only=True))
    assert "Rejected business" not in " ".join(package["xl/worksheets/sheet2.xml"].itertext())
    csv_content = export_run(customer_run, "csv", accepted_only=True)
    assert csv_content.startswith("\ufeff")
    rows = list(csv.DictReader(io.StringIO(csv_content.lstrip("\ufeff"))))
    assert len(rows) == 1 and rows[0]["Company"] == 'Example, "AI" 日本'
    assert rows[0]["Fit assessment"] == "Fit unverified"
    assert "json" not in ",".join(rows[0]) and "FULL PAGE TEXT" not in str(rows)
    customer_run["records"][0]["review"] = None
    empty = workbook_xml(export_run(customer_run, "xlsx", accepted_only=True))
    assert "0 companies" in " ".join(empty["xl/worksheets/sheet1.xml"].itertext())


def test_xlsx_untrusted_strings_are_never_formulas(customer_run):
    customer_run["records"][0]["research"]["name"] = '=HYPERLINK("https://evil.example")\x00'
    package = workbook_xml(export_run(customer_run, "xlsx"))
    ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    for sheet in ("xl/worksheets/sheet1.xml", "xl/worksheets/sheet2.xml"):
        assert package[sheet].findall(".//s:f", ns) == []
    assert "evil.example" in " ".join(package["xl/worksheets/sheet1.xml"].itertext())


def test_actual_api_workbook_download_preserves_run_and_review(tmp_path, customer_run):
    from fastapi.testclient import TestClient

    from shortlist.api import create_app
    from shortlist.config import Settings
    from shortlist.domain import Profile, Research
    from shortlist.store import Store

    settings = Settings(db_path=tmp_path / "export.sqlite3")
    store = Store(settings.db_path)
    profile = Profile(seller_url="https://seller.example/", offer="Research software for teams",
                      target="Private software companies", criteria=[{"id": "ai", "description": "Offers AI software"}])
    identity = store.create_run(profile, "workbook-api-proof")
    data = deepcopy(customer_run["records"][0]["research"])
    data["profile_id"] = profile.id
    store.save_record(identity, store.claim(identity), Research.model_validate(data))
    before = store.get_run(identity)
    client = TestClient(create_app(settings))
    response = client.get(f"/api/runs/{identity}/export?format=xlsx")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert response.headers["content-disposition"].endswith(f'shortlist-{identity}.xlsx"')
    workbook_xml(response.content)
    empty = client.get(f"/api/runs/{identity}/export?format=xlsx&accepted_only=true")
    assert "0 companies" in " ".join(workbook_xml(empty.content)["xl/worksheets/sheet1.xml"].itertext())
    assert store.get_run(identity) == before


@pytest.mark.parametrize("name", ["=HYPERLINK(\"evil\")", "+1+1", "-1+1", "@SUM(A1:A2)", "\t=1+1", "\r=1+1"])
def test_csv_formula_cells_are_escaped(name):
    run = {"id": "run", "profile": {}, "status": "partial", "checkpoint": {}, "records": [{
        "research": {"name": name, "domain": "example.com", "qualification": "needs_verification",
                     "status": "partial", "findings": [], "sources": [], "hypotheses": [], "unknowns": []},
        "review": None}]}
    rows = list(csv.reader(io.StringIO(export_run(run, "csv"))))
    assert rows[1][0].startswith("'")
