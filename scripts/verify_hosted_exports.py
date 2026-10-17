"""Compare UI downloads with a private read-only hosted snapshot, without network calls."""
import argparse
import io
import json
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

from shortlist.domain import Profile, read_research
from shortlist.export import export_run
from shortlist.fetch import domain_of


def verify(snapshot: Path, directory: Path):
    captured = json.loads(snapshot.read_text(encoding="utf-8"))
    stored = captured["run"]
    profile = Profile.model_validate_json(stored["profile"])
    checkpoint = json.loads(stored["checkpoint"])
    run = {"id": stored["id"], "status": stored["status"], "profile": profile.model_dump(mode="json"),
           "checkpoint": checkpoint, "records": []}
    for row in captured["records"]:
        run["records"].append({"research": read_research(profile, json.loads(row["research"])).model_dump(mode="json"),
                               "review": json.loads(row["review"]) if row["review"] else None,
                               "email_draft": json.loads(row["email_draft"])["draft"] if row["email_draft"] else None,
                               "operator_review": None})
        if captured["holds"]:
            operation = "delivery:" + stored["id"] + ":" + row["domain"]
            run["records"][-1]["credits_used"] = int(any(e["operation_key"] == operation for e in captured["ledger"]))
    downloaded = json.loads((directory / "shortlist.json").read_text(encoding="utf-8"))
    assert downloaded["run_id"] == run["id"] and downloaded["profile"] == run["profile"]
    assert downloaded["status"] == run["status"] and downloaded["records"] == run["records"]
    assert downloaded["discovery"] == checkpoint.get("candidates", [])
    assert downloaded["seller_source"] == checkpoint.get("seller_source")
    assert downloaded["candidate_sources"] == checkpoint.get("sources", {})
    assert (directory / "shortlist.csv").read_bytes().decode("utf-8") == export_run(run, "csv")
    sources, citations, unknowns = 0, 0, 0
    for item in downloaded["records"]:
        record = item["research"]
        by_id = {source["id"]: source for source in record["sources"]}
        sources += len(by_id)
        for source in by_id.values():
            assert source["retrieved_at"] and domain_of(source["url"]) == record["domain"]
            assert source["company_domain"] == record["domain"]
        evidence = [fact["evidence"] for fact in record.get("company_facts", []) + record.get("people", [])]
        for finding in record["findings"] + record.get("exclusion_findings", []):
            unknowns += finding["status"] == "unknown"
            evidence.extend(finding.get("evidence", []))
        for citation in evidence:
            source = by_id[citation["source_id"]]
            assert " ".join(citation["passage"].split()) in " ".join(source["text"].split())
            citations += 1
    expected = export_run(run, "xlsx")
    namespace = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with ZipFile(directory / "shortlist.xlsx") as actual, ZipFile(io.BytesIO(expected)) as reference:
        workbook = ElementTree.fromstring(actual.read("xl/workbook.xml"))
        sheets = [sheet.attrib["name"] for sheet in workbook.findall("s:sheets/s:sheet", namespace)]
        for name in reference.namelist():
            if name.startswith("xl/worksheets/") and name.endswith(".xml"):
                assert actual.read(name) == reference.read(name), "Downloaded worksheet differs from saved values"
                assert not ElementTree.fromstring(actual.read(name)).findall(".//s:f", namespace)
    assert sources > 0 and citations > 0, "Research needs inspectable source passages"
    result = {"run_id": run["id"], "records": len(run["records"]), "source_pages": sources,
              "exact_citations": citations, "unknown_findings": unknowns, "sheets": sheets,
              "json_matches_snapshot": True, "csv_matches_saved_values": True, "xlsx_matches_saved_values": True,
              "note": "Citation containment is checked; semantic usefulness requires separate review."}
    (directory / "verification.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.snapshot, args.directory), indent=2))
