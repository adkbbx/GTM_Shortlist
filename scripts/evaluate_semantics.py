"""Run a bounded, journaled real-model audit of authored cases; no fabricated score."""
import argparse
import hashlib
import json
from pathlib import Path

from shortlist.config import Settings
from shortlist.domain import Profile, Research, utcnow
from shortlist.evaluation import semantic_case
from shortlist.journal import call_step
from shortlist.providers import Gemma, ProviderError
from shortlist.store import Store
from shortlist.verification import Verification, apply_verification

parser = argparse.ArgumentParser()
parser.add_argument("--cases", type=Path, default=Path("examples/evaluation/semantic-cases.json"))
parser.add_argument("--database", type=Path, default=Path("data/semantic-evaluation.sqlite3"))
parser.add_argument("--output", type=Path, default=Path("data/semantic-evaluation.json"))
parser.add_argument("--max-calls", type=int, choices=range(1, 31), default=30)
args = parser.parse_args()
cases = json.loads(args.cases.read_text())
assert len(cases) <= 30 and len({c["id"] for c in cases}) == len(cases)
settings = Settings.load()
model = Gemma(settings)
store = Store(args.database)
results = []
for case in cases:
    profile, proposed = semantic_case(case)
    digest = hashlib.sha256(json.dumps(case, sort_keys=True).encode()).hexdigest()
    run_id = store.create_run(profile, f"semantic-v2:{settings.gemma_model}:{digest}")
    run = store.get_run(run_id)
    profile = Profile.model_validate(run["profile"])
    checkpoint = run["checkpoint"]
    if "result" not in checkpoint:
        with store.connection() as db:
            count = db.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]
        # Completed journal entries replay freely; never start a new request over the total cap.
        with store.connection() as db:
            has_attempt = db.execute("SELECT 1 FROM attempts WHERE run_id=?", (run_id,)).fetchone()
        if count >= args.max_calls and not has_attempt:
            break
        fence = store.claim(run_id)
        if fence is None:
            raise RuntimeError("Evaluation lease is active; wait for its expiry before resuming")
        if "proposed" not in checkpoint:
            proposed = proposed.model_copy(update={"profile_id": profile.id})
            checkpoint["proposed"] = proposed.model_dump(mode="json")
            store.checkpoint(run_id, fence, "semantic_evaluation", checkpoint)
        proposed = Research.model_validate(checkpoint["proposed"])
        try:
            audit = call_step(store, run_id, fence, settings.global_search_cap, kind="model", provider=model.name,
                              operation="verify", inputs={"profile": profile.model_dump(mode="json"),
                                "research": proposed.model_dump(mode="json"), "model": settings.gemma_model,
                                "endpoint": settings.gemma_base_url, "verification_policy": 2},
                              function=lambda p=profile, r=proposed: model.verify(p, r), decode=Verification.model_validate)
            final = apply_verification(profile, proposed, audit)
            finding = final.exclusion_findings[0] if case["kind"] == "exclusion" else final.findings[0]
            actual = finding.status != "unknown"
            result = {"id": case["id"], "run_id": run_id, "expected_entailed": case["expected_entailed"],
                      "actual_entailed": actual, "correct": actual == case["expected_entailed"],
                      "audit": audit.model_dump(mode="json")}
        except ProviderError as exc:
            result = {"id": case["id"], "run_id": run_id, "expected_entailed": case["expected_entailed"],
                      "actual_entailed": False, "correct": False, "error": str(exc)}
        checkpoint["result"] = result
        store.checkpoint(run_id, fence, "evaluation_complete", checkpoint, "ready")
    results.append(checkpoint["result"])
    print(json.dumps({"completed": len(results), "case": case["id"], "correct": results[-1]["correct"]}), flush=True)
errors = sum("error" in r for r in results)
report = {"model": settings.gemma_model, "verification_policy": 2, "evaluated_at": utcnow().isoformat(),
          "scope": "Verifier only on labelled proposed assessments; not extraction or discovery quality",
          "corpus_sha256": hashlib.sha256(args.cases.read_bytes()).hexdigest(),
          "cases": len(results), "expected_cases": len(cases), "errors": errors,
          "correct": sum(r["correct"] for r in results),
          "false_acceptances": sum(r["actual_entailed"] and not r["expected_entailed"] for r in results),
          "false_rejections": sum(not r["actual_entailed"] and r["expected_entailed"] for r in results),
          "results": results}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({k: v for k, v in report.items() if k != "results"}), flush=True)
