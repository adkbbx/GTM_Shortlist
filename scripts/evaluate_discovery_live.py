"""Bounded live check of discovery policy 2 queries. Run only with the user's explicit approval for this check.

Approved by the user on 18 October 2026: six searches, the two policy-2 discovery queries for each of three saved
targets, through the local app's configured search provider. Search only: no page fetch and no model call.
Every search is reserved in the journal before dispatch and saved after, so a rerun replays saved results and an
interrupted search is never sent again. Raw provider results (before admission) are kept for labelling.
"""
import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from shortlist import providers
from shortlist.config import Settings
from shortlist.domain import Criterion, Profile
from shortlist.local_credentials import apply_local_credentials
from shortlist.providers import SearchProvider, queries_for

# The seller and confirmed target of saved runs 06de9543, 35249a4e and 98331456.
CASES = (
    ("private-ai-saas", "https://eygentic.com/", "Private AI B2B SaaS startups"),
    ("b2b-saas-growth", "https://eygentic.com/",
     ("B2B and SaaS companies of any size or stage, including specialized business software, seeking more predictable "
     "customer acquisition and evidence-based growth rather than volume-based activity.")),
    ("channel-partner-programs", "https://unifyr.com/",
     ("Companies managing and scaling channel partner programs, from emerging to enterprise levels, that require tools to "
     "manage partner onboarding, co-selling, co-marketing, and performance tracking.")),
)
APPROVED_SEARCHES = 6


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-provider-calls", action="store_true", help="Only after the user's explicit approval")
    parser.add_argument("--credentials-db", type=Path, required=True, help="The local app database whose saved provider is used")
    parser.add_argument("--journal", type=Path, required=True)
    args = parser.parse_args()
    if not args.allow_provider_calls:
        parser.error("Live evaluation is disabled without --allow-provider-calls and the user's approval.")
    settings = apply_local_credentials(Settings(db_path=args.credentials_db.resolve()))
    if not settings.readiness()["search"]:
        raise SystemExit("The local app has no search provider configured")
    journal = json.loads(args.journal.read_text(encoding="utf-8")) if args.journal.exists() else {
        "note": "Live discovery policy 2 check approved by the user on 18 October 2026: six searches, no fetch or model call.",
        "provider": settings.search_provider, "searches": {}}

    def save():
        args.journal.parent.mkdir(parents=True, exist_ok=True)
        args.journal.write_text(json.dumps(journal, indent=1, ensure_ascii=False), encoding="utf-8")

    raw_results = {}
    original = providers.candidates_from_results

    def capture(results, query, provider, seller_url):
        raw_results[query] = [{"url": r.get("url") or r.get("link"), "title": r.get("title") or ""} for r in results]
        return original(results, query, provider, seller_url)
    providers.candidates_from_results = capture
    search = SearchProvider(settings)
    for key, seller, target in CASES:
        profile = Profile(seller_url=seller, offer="Discovery evaluation only", target=target,
                          criteria=(Criterion(id="evaluation", description="Discovery evaluation only"),))
        for query in queries_for(profile, policy=2)[:2]:  # The planned pair; the low-yield third query is not in scope.
            saved = journal["searches"].get(query)
            if saved and saved["state"] == "done":
                continue
            if saved:
                raise SystemExit(f"Outcome of {query!r} is uncertain; not sending it again")
            if sum(1 for item in journal["searches"].values()) >= APPROVED_SEARCHES:
                raise SystemExit("The approved number of searches is used")
            journal["searches"][query] = {"case": key, "seller": seller, "state": "reserved",
                                          "reserved_at": datetime.now(UTC).isoformat()}
            save()
            admitted = search.search(query, seller)
            journal["searches"][query].update(state="done", raw=raw_results.get(query, []),
                                              admitted=[c.model_dump(mode="json") for c in admitted])
            save()
            print(f"{key}: {query!r} raw={len(raw_results.get(query, []))} admitted={len(admitted)}", flush=True)
    providers.candidates_from_results = original
    print(f"{len(journal['searches'])} searches in the journal")


if __name__ == "__main__":
    main()
