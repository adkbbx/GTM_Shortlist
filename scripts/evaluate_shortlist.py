"""Journaled discovery/research evaluation from an already confirmed saved target.

This does not prove fresh seller profiling, market planning or hosted accounts.
Source storage is read-only. The separate evaluation can be resumed without
repeating saved provider outcomes. No automatic retry of uncertain dispatches.
"""
import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

from dotenv import dotenv_values

from shortlist.config import Settings
from shortlist.domain import Profile
from shortlist.store import Conflict, Store
from shortlist.worker import execute_run


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-db", type=Path, required=True)
    parser.add_argument("--source-run", required=True)
    parser.add_argument("--output-db", type=Path, required=True)
    parser.add_argument("--provider-env", type=Path, default=Path("deploy/secrets/worker.env"))
    parser.add_argument("--request-key", default="confirmed-target-evaluation")
    parser.add_argument("--allow-provider-calls", action="store_true",
                        help="Requires separate explicit human approval before live credit use")
    args = parser.parse_args(argv)
    if not args.allow_provider_calls:
        parser.error("Live evaluation is disabled. Obtain user approval before opting in with --allow-provider-calls.")
    if args.source_db.resolve() == args.output_db.resolve() or (
            args.output_db.exists() and args.source_db.samefile(args.output_db)):
        raise ValueError("Source and evaluation databases must be different")
    with sqlite3.connect(args.source_db.resolve().as_uri() + "?mode=ro", uri=True) as db:
        row = db.execute("SELECT profile,checkpoint FROM runs WHERE id=? AND deleted_at IS NULL", (args.source_run,)).fetchone()
    if row is None:
        raise ValueError("Source run was not found")
    profile = Profile.model_validate_json(row[0])
    source_checkpoint = json.loads(row[1])
    # Keep an exact, already-confirmed target and campaign. Never auto-confirm new model output.
    context = {key: source_checkpoint[key] for key in ("market", "campaign_name", "discovery_terms", "seller_source")
               if key in source_checkpoint}
    context_hash = hashlib.sha256(json.dumps({"profile": profile.model_dump(mode="json"),
        "context": context}, sort_keys=True).encode()).hexdigest()
    private = dotenv_values(args.provider_env)
    settings = Settings(db_path=args.output_db, global_search_cap=2,
        search_provider=private.get("SHORTLIST_SEARCH_PROVIDER", "serpapi"),
        serpapi_key=private.get("SERPAPI_API_KEY") or "", tavily_key=private.get("TAVILY_API_KEY") or "",
        gemma_base_url=private.get("GEMMA_BASE_URL") or "", gemma_model=private.get("GEMMA_MODEL") or "",
        gemma_key=private.get("GEMMA_API_KEY") or "")
    args.output_db.parent.mkdir(parents=True, exist_ok=True)
    store = Store(args.output_db)
    identity = store.create_run(profile, args.request_key)
    current = store.get_run(identity)
    previous = current["checkpoint"].get("evaluation")
    if previous is not None and previous["context_sha256"] != context_hash:
        raise Conflict("This request key belongs to another saved target context")
    if previous is None:
        fence = store.claim(identity)
        if fence is None:
            raise Conflict("Evaluation is already claimed")
        checkpoint = {**context, "selection_policy": 3, "company_limit": 3,
            "evaluation": {"kind": "confirmed_target_research", "source_run": args.source_run,
                           "context_sha256": context_hash}}
        store.checkpoint(identity, fence, "discovery", checkpoint, "queued")
    execute_run(store, settings, identity)
    result = store.get_run(identity)
    print(json.dumps({"run_id": identity, "status": result["status"], "stage": result["stage"],
        "companies": len(result["records"]), "search_attempts": sum(a["kind"] == "search" for a in result["attempts"]),
        "model_attempts": sum(a["kind"] == "model" for a in result["attempts"]),
        "fetch_attempts": sum(a["kind"] == "fetch" for a in result["attempts"]),
        "scope": "Saved confirmed target; not fresh seller/market or hosted-account validation"}))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, sqlite3.Error, Conflict):
        print("Evaluation stopped; inspect the saved journal before considering another attempt.")
        raise SystemExit(1) from None
