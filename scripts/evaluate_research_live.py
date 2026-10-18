"""End-to-end research on companies found by the approved live searches. Run only with the user's explicit approval.

Approved by the user on 18 October 2026: one research run with at most six model calls and no new searches. The
companies are the ones the live channel-partner searches admitted (data/evaluations/discovery-policy2-2026-10-18.json);
the seller, offer and target come from saved run 98331456, using its first campaign's fit checks as a user who applied
that campaign would. The real worker then fetches pages, researches and verifies, and qualifies. A search attempt
raises; the run's model cap is six.
"""
import argparse
import json
import sqlite3
from pathlib import Path

from shortlist.config import Settings
from shortlist.domain import Criterion, Profile
from shortlist.store import DISCOVERY_POLICY, RUN_CAPS, Store
from shortlist.worker import execute_run


class NoSearch:
    name = "approved_saved_results_only"

    def search(self, query, seller_url):
        raise AssertionError("This approved run makes no searches")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-provider-calls", action="store_true", help="Only after the user's explicit approval")
    parser.add_argument("--search-journal", type=Path, required=True)
    parser.add_argument("--saved-db", type=Path, required=True, help="Read-only database holding saved run 98331456")
    parser.add_argument("--output-db", type=Path, required=True)
    parser.add_argument("--model", default="gemma4:e2b-it-qat")
    parser.add_argument("--endpoint", default="http://localhost:11434/v1")
    parser.add_argument("--run-key", default="research-run-channel-partner-2026-10-18",
                        help="A new key in the same output database is a repeat run: it sets aside companies already saved")
    parser.add_argument("--discovery-policy", type=int, default=DISCOVERY_POLICY,
                        help="The first two runs of 18 October used 2; 3 also reads the page search found")
    args = parser.parse_args()
    if not args.allow_provider_calls:
        parser.error("Disabled without --allow-provider-calls and the user's approval.")
    with sqlite3.connect(args.saved_db.resolve().as_uri() + "?mode=ro", uri=True) as db:
        profile_json, checkpoint_json = db.execute("SELECT profile, checkpoint FROM runs WHERE id LIKE '98331456%'").fetchone()
    saved_profile, saved_checkpoint = json.loads(profile_json), json.loads(checkpoint_json)
    campaign = saved_checkpoint["market"]["campaigns"][0]
    profile = Profile(seller_url=saved_profile["seller_url"], offer=saved_profile["offer"], target=campaign["target"],
                      criteria=tuple(Criterion.model_validate(c) for c in campaign["criteria"]))
    journal = json.loads(args.search_journal.read_text(encoding="utf-8"))
    found = {}
    for item in journal["searches"].values():
        if item["case"] == "channel-partner-programs":
            for candidate in item["admitted"]:
                found.setdefault(candidate["domain"], candidate)
    store = Store(args.output_db)
    run_id = store.create_run(profile, args.run_key)
    run = store.get_run(run_id)
    if run["status"] == "queued" and run["stage"] == "discovery" and "discovered" not in run["checkpoint"]:
        fence = store.claim(run_id)
        # A repeat run sets aside earlier companies, leaving too few for the low-yield third query; it is not approved.
        store.checkpoint(run_id, fence, "discovery", {**run["checkpoint"], "discovery_policy": args.discovery_policy,
                         "selection_policy": 3,
                         "company_limit": 3, "discovered": list(found.values()), "completed_queries": [0, 1],
                         "discovery_failures": {"2": "Not run: this approved evaluation makes no searches"},
                         "campaign_name": campaign["name"], "evaluation": "approved research run on saved live search results"},
                         "queued")
        with store.connection() as db:
            db.execute("UPDATE runs SET lease_until=0 WHERE id=?", (run_id,))
    RUN_CAPS["model"] = 6  # The approval: at most six model calls in this run.
    settings = Settings(db_path=args.output_db, gemma_base_url=args.endpoint, gemma_model=args.model)
    print(f"Target: {profile.target}\nChecks: {[(c.description, c.required) for c in profile.criteria]}\n"
          f"Candidates: {sorted(found)}", flush=True)
    execute_run(store, settings, run_id, search=NoSearch())
    saved = store.get_run(run_id)
    print("status", saved["status"], "| error", saved["error"])
    print("attempts", {kind: sum(a["kind"] == kind for a in saved["attempts"]) for kind in ("search", "fetch", "model")})
    print("set aside as already shortlisted", saved["checkpoint"].get("previously_researched", []))
    for reason in saved["checkpoint"].get("candidate_failures", {}).items():
        print("  refused", reason[0], "|", reason[1]["reason"][:120])
    for record in saved["records"]:
        research = record["research"]
        print(f"\n{research['name']} ({research['domain']}): {research['qualification']}")
        for finding in research["findings"]:
            criterion = next(c.description for c in profile.criteria if c.id == finding["criterion_id"])
            detail = finding["evidence"][0]["passage"][:160] if finding["status"] != "unknown" else finding["reason"][:160]
            print(f"   {finding['status']:<12} {criterion[:70]} | {detail}")


if __name__ == "__main__":
    main()
