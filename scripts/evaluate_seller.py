"""One journaled seller-summary call from a saved source, with no search or account debit."""
import argparse
import json
from pathlib import Path

from dotenv import dotenv_values

from shortlist.config import Settings
from shortlist.domain import Source
from shortlist.store import Store
from shortlist.worker import execute_run


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-json", type=Path, required=True)
    parser.add_argument("--output-db", type=Path, required=True)
    parser.add_argument("--provider-env", type=Path, default=Path("deploy/secrets/worker.env"))
    parser.add_argument("--allow-provider-calls", action="store_true")
    args = parser.parse_args(argv)
    if not args.allow_provider_calls:
        parser.error("Live evaluation is disabled. Obtain user approval for one inference call before --allow-provider-calls.")
    if (args.source_json.resolve() == args.output_db.resolve()
            or (args.output_db.exists() and args.source_json.samefile(args.output_db))):
        raise ValueError("Source and output must be different files")
    source = Source.model_validate_json(args.source_json.read_text(encoding="utf-8"))
    private = dotenv_values(args.provider_env)
    settings = Settings(db_path=args.output_db, gemma_base_url=private.get("GEMMA_BASE_URL") or "",
                        gemma_model=private.get("GEMMA_MODEL") or "", gemma_key=private.get("GEMMA_API_KEY") or "")
    if not settings.gemma_base_url or not settings.gemma_model:
        raise ValueError("Configure the inference endpoint and model before evaluation")
    # Version 1 experience stops after seller extraction. No market/search/research stage runs.
    args.output_db.parent.mkdir(parents=True, exist_ok=True)
    store = Store(args.output_db)
    identity = store.create_draft(source.url, "seller-output-evaluation")
    run = store.get_run(identity)
    context = {"source": source.model_dump(mode="json"), "model": settings.gemma_model,
               "endpoint": settings.gemma_base_url, "output_protocol": 2}
    if run["checkpoint"].get("evaluation", context) != context:
        raise ValueError("Saved evaluation context changed; no provider call was made")
    if "evaluation" not in run["checkpoint"]:
        fence = store.claim(identity)
        if fence is None:
            raise ValueError("Evaluation is already claimed")
        checkpoint = {**run["checkpoint"], "evaluation": context, "seller_source": source.model_dump(mode="json")}
        store.checkpoint(identity, fence, "seller", checkpoint, "queued")
    execute_run(store, settings, identity)
    result = store.get_run(identity)
    print(json.dumps({"run_id": identity, "status": result["status"], "valid_summary": "draft" in result["checkpoint"],
                      "model_attempts": sum(a["kind"] == "model" for a in result["attempts"]),
                      "source_reused": True}))


if __name__ == "__main__":
    main()
