"""One bounded live-provider evaluation from an existing saved seller source.

The source database is read-only. Output is a separate local research database.
Reusing the same output and request key resumes the journal instead of re-paying.
This does not establish a fresh website fetch or a hosted customer run.
"""
import argparse
import json
import sqlite3
from pathlib import Path

from dotenv import dotenv_values

from shortlist.config import Settings
from shortlist.domain import Source
from shortlist.store import Store
from shortlist.worker import execute_run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-db", type=Path, required=True)
    parser.add_argument("--source-run", required=True)
    parser.add_argument("--output-db", type=Path, required=True)
    parser.add_argument("--provider-env", type=Path, default=Path("deploy/secrets/worker.env"))
    parser.add_argument("--request-key", default="market-live-evaluation")
    parser.add_argument("--allow-provider-calls", action="store_true",
                        help="Allow credit-consuming evaluation only after explicit user approval")
    args = parser.parse_args()
    if not args.allow_provider_calls:
        parser.error("Live evaluation is disabled. Use saved evidence or fixtures; obtain user approval "
                     "before opting in with --allow-provider-calls.")
    if args.source_db.resolve() == args.output_db.resolve():
        raise ValueError("Source and evaluation databases must be different")
    with sqlite3.connect(args.source_db.resolve().as_uri() + "?mode=ro", uri=True) as db:
        row = db.execute("SELECT checkpoint FROM runs WHERE id=? AND deleted_at IS NULL", (args.source_run,)).fetchone()
    if row is None:
        raise ValueError("Source run was not found")
    saved = json.loads(row[0])
    source = Source.model_validate(saved["seller_source"])
    private = dotenv_values(args.provider_env)
    settings = Settings(db_path=args.output_db, search_provider=private.get("SHORTLIST_SEARCH_PROVIDER", "serpapi"),
                        tavily_key=private.get("TAVILY_API_KEY") or "", serpapi_key=private.get("SERPAPI_API_KEY") or "",
                        gemma_base_url=private.get("GEMMA_BASE_URL") or "", gemma_model=private.get("GEMMA_MODEL") or "",
                        gemma_key=private.get("GEMMA_API_KEY") or "")
    args.output_db.parent.mkdir(parents=True, exist_ok=True)
    store = Store(args.output_db)
    identity = store.create_draft(saved["seller_url"], args.request_key, experience_version=2)
    current = store.get_run(identity)
    if current["checkpoint"].get("evaluation", {}).get("source_id", source.id) != source.id:
        raise ValueError("This request key belongs to a different saved source; choose a new request key")
    if "seller_source" not in current["checkpoint"]:
        fence = store.claim(identity)
        if fence is None:
            raise ValueError("Evaluation is already claimed")
        checkpoint = {**current["checkpoint"], "seller_source": source.model_dump(mode="json"),
                      "evaluation": {"kind": "saved_real_source_replay", "source_id": source.id,
                                     "retrieved_at": source.retrieved_at.isoformat()}}
        store.checkpoint(identity, fence, "seller", checkpoint, "queued")
    print("Opening the saved evaluation or executing unfinished provider steps; no fresh website fetch.", flush=True)
    execute_run(store, settings, identity)
    result = store.get_run(identity)
    market = result["checkpoint"].get("market") or {}
    print(json.dumps({"run_id": identity, "status": result["status"], "stage": result["stage"],
                      "competitors": len(market.get("competitors", [])), "campaigns": len(market.get("campaigns", [])),
                      "issues": market.get("issues", []), "attempts": len(result["attempts"])}))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, sqlite3.Error) as exc:
        print("Evaluation stopped:", type(exc).__name__)
        raise SystemExit(1) from None
