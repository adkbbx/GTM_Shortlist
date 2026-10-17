"""Replay a saved run's model steps against the configured on-device model.

Reads the run database read-only and reuses its saved pages and search results, so no search
provider is called and nothing is saved. Hosted model endpoints are refused because a replay would
spend inference credits. Run without a run ID to list recent runs.
"""
import argparse
import json
import sqlite3
import sys
import time
from urllib.parse import urlsplit

import shortlist
from shortlist.config import Settings
from shortlist.domain import Candidate, Profile, Source
from shortlist.local_credentials import apply_local_credentials
from shortlist.prompting import LOOPBACK
from shortlist.providers import Gemma, ModelOutputError, ProviderError, SellerDraft
from shortlist.verification import apply_verification


def step(label, function):
    start = time.monotonic()
    try:
        result = function()
    except ModelOutputError as exc:
        print(f"FAILED  {label} ({time.monotonic() - start:.0f}s): invalid model output {exc.issues[:3]}")
        return None
    except ProviderError as exc:
        print(f"FAILED  {label} ({time.monotonic() - start:.0f}s): {exc}")
        return None
    print(f"OK      {label} ({time.monotonic() - start:.0f}s)")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", nargs="?", help="saved run ID or prefix; omit to list recent runs")
    parser.add_argument("--companies", type=int, default=3, help="companies to research (default 3)")
    args = parser.parse_args()
    settings = apply_local_credentials(Settings.load())
    print("Code under test:", shortlist.__file__)
    print("Database:", settings.db_path.resolve())
    database = sqlite3.connect(settings.db_path.resolve().as_uri() + "?mode=ro", uri=True)
    if not args.run:
        for run_id, created, status, stage in database.execute(
                "SELECT id, created_at, status, stage FROM runs WHERE deleted_at IS NULL ORDER BY created_at DESC LIMIT 10"):
            print(run_id[:8], created[:16], status, stage)
        return
    host = urlsplit(settings.gemma_base_url).hostname or ""
    if host not in LOOPBACK and not host.endswith(".localhost"):
        sys.exit("Refusing a hosted model endpoint: a replay must not spend inference credits.")
    row = database.execute("SELECT profile, checkpoint FROM runs WHERE id LIKE ? AND deleted_at IS NULL",
                           (args.run + "%",)).fetchone()
    if row is None:
        sys.exit("No saved run matches " + args.run)
    checkpoint = json.loads(row[1])
    model = Gemma(settings)
    print("Model:", settings.gemma_model, "|", model.runtime, "\n")

    if "seller_source" in checkpoint:
        draft = step("Understand offer", lambda: model.seller(Source.model_validate(checkpoint["seller_source"])))
        for criterion in draft.criteria if draft else ():
            print("          criterion:", criterion.description[:100])
    if "draft" in checkpoint and "market_candidates" in checkpoint:
        plan = step("Explore market", lambda: model.market(
            SellerDraft.model_validate(checkpoint["draft"]),
            [Candidate.model_validate(c) for c in checkpoint["market_candidates"]]))
        for campaign in plan.campaigns if plan else ():
            print(f"          campaign: {campaign.name} | search terms: {campaign.search_terms}")
    saved_profile = json.loads(row[0] or "null")
    if not isinstance(saved_profile, dict) or not saved_profile.get("criteria"):
        print("\nNo confirmed target yet, so there is no research to replay.")
        return
    profile = Profile.model_validate(saved_profile)
    candidates = {c["domain"]: Candidate.model_validate(c) for c in checkpoint.get("candidates", [])}
    domains = [domain for domain in checkpoint.get("sources", {}) if domain in candidates][:args.companies]
    for domain in domains:
        sources = tuple(Source.model_validate(s) for s in checkpoint["sources"][domain])
        record = step("Inspect evidence: " + domain,
                      lambda c=candidates[domain], s=sources: model.research(profile, c, s))
        if record is None:
            continue
        audit = step("Check evidence:   " + domain, lambda r=record: model.verify(profile, r))
        if audit is not None:
            record = apply_verification(profile, record, audit)
        for finding in record.findings:
            detail = "; ".join(e.claim for e in getattr(finding, "evidence", ())) or getattr(finding, "reason", "")
            print(f"          [{finding.status}] {finding.criterion_id}: {detail[:110]}")


if __name__ == "__main__":
    main()
