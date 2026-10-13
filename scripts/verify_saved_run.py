"""Inspect a real saved run and exports without dispatching any provider request."""
import argparse
import json
from pathlib import Path

from shortlist.config import Settings
from shortlist.domain import Profile, Research
from shortlist.export import export_run
from shortlist.providers import validate_extraction
from shortlist.store import Store

parser = argparse.ArgumentParser()
parser.add_argument("run_id")
parser.add_argument("--output", type=Path, default=Path("data/exports"))
args = parser.parse_args()
run = Store(Settings.load().db_path).get_run(args.run_id)
profile = Profile.model_validate(run["profile"])
assert run["status"] in ("ready", "partial"), "Run must have finished its current work"
assert 0 < len(run["records"]) <= 3
assert run["checkpoint"].get("candidates"), "Discovery provenance is missing"
supported = 0
sources = 0
for item in run["records"]:
    record = Research.model_validate(item["research"])
    assert record.profile_id == profile.id
    checked = validate_extraction({"name": record.name,
                                   "findings": [f.model_dump(mode="json") for f in record.findings],
                                   "hypotheses": [h.model_dump(mode="json") for h in record.hypotheses]},
                                  profile, record.domain, record.sources)
    assert [f.status for f in checked.findings] == [f.status for f in record.findings], "Saved citation lost grounding"
    supported += sum(f.status == "supported" for f in checked.findings)
    sources += len(record.sources)
assert sources > 0 and supported > 0, "Milestone needs actual inspectable supporting evidence"
args.output.mkdir(parents=True, exist_ok=True)
for format in ("json", "csv"):
    (args.output / f"{args.run_id}.{format}").write_text(export_run(run, format), encoding="utf-8")
print(json.dumps({"run_id": run["id"], "status": run["status"], "records": len(run["records"]),
                  "sources": sources, "supported_findings": supported,
                  "discovered_domains": len(run["checkpoint"]["candidates"]),
                  "search_providers": sorted({c["provider"] for c in run["checkpoint"]["candidates"]}),
                  "export_directory": str(args.output)}, indent=2))
