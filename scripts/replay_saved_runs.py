"""Replay saved research runs through today's shortlisting rules, read-only and offline.

For every saved company record it asks what the current rules would have done with the same evidence:
- refused at search time (not a company's own page), saving the research credit;
- set aside as already in an earlier shortlist for the same seller, saving the credit;
- otherwise re-qualified from the saved, verified findings, with checks a company website rarely states treated as
  nice to have, as new drafts now default to and the confirmation advice suggests.
No search, fetch or model call is made, and the database is opened read-only. Usage:
  python scripts/replay_saved_runs.py path/to/shortlist.sqlite3 [more.sqlite3 ...]
"""
import json
import sqlite3
import sys
from collections import Counter, defaultdict

from shortlist.criteria import rarely_public
from shortlist.domain import Candidate, Profile, exclusion_id, qualify, read_research
from shortlist.fetch import domain_of
from shortlist.ranking import evidence_key
from shortlist.relevance import candidate_issue


def replay(path: str) -> dict:
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    totals = Counter()
    seen = defaultdict(set)  # Seller domain -> companies saved in earlier shortlists.
    runs = []
    for run in db.execute("SELECT id, profile, checkpoint, created_at FROM runs WHERE deleted_at IS NULL ORDER BY created_at"):
        records = [json.loads(row["research"]) for row in db.execute("SELECT research FROM records WHERE run_id=?", (run["id"],))]
        if not records or run["profile"] in (None, "", "{}"):
            continue
        profile = Profile.model_validate_json(run["profile"])
        checkpoint = json.loads(run["checkpoint"] or "{}")
        found = {c["domain"]: Candidate.model_validate(c) for c in checkpoint.get("candidates", [])}
        # The confirmation advice: rarely-public checks become nice to have, and rarely-public exclusions are asked in
        # conversation instead. Remaining exclusion findings keep their meaning under their new positions.
        kept_exclusions = [index for index, text in enumerate(profile.exclusions) if not rarely_public(text)]
        renumbered = {exclusion_id(old): exclusion_id(new) for new, old in enumerate(kept_exclusions)}
        advised = profile.model_copy(update={
            "criteria": tuple(c.model_copy(update={"required": c.required and not rarely_public(c.description)}) for c in profile.criteria),
            "exclusions": tuple(profile.exclusions[index] for index in kept_exclusions)})
        seller = domain_of(profile.seller_url)
        rows, leads = [], []
        for raw in records:
            research = read_research(profile, raw)
            totals["records"] += 1
            totals[f"qualified_before:{research.qualification}"] += 1
            # Re-qualification from the same saved findings, reported for every record so that credit savings
            # below do not hide it.
            checks = tuple(f.model_copy(update={"exclusion_id": renumbered[f.exclusion_id]})
                           for f in research.exclusion_findings if f.exclusion_id in renumbered)
            after = qualify(advised, research.findings, checks)
            totals[f"qualified_after_advice:{after}"] += 1
            candidate = found.get(research.domain) or Candidate(
                domain=research.domain, url=research.sources[0].url if research.sources else f"https://{research.domain}/",
                name=research.name, query=profile.target, provider="saved")
            if issue := candidate_issue(candidate):
                outcome = f"{research.qualification} -> {after}; now refused before research: {issue}"
                totals["credits_saved:not_a_company_page"] += 1
            elif research.domain in seen[seller]:
                outcome = f"{research.qualification} -> {after}; now set aside: already in an earlier shortlist for this seller"
                totals["credits_saved:repeat"] += 1
            else:
                outcome = f"{research.qualification} -> {after}"
                leads.append((evidence_key(advised.model_dump(mode="json"), {**research.model_dump(mode="json"), "qualification": after}),
                              research.domain))
            rows.append((research.domain, outcome))
        for raw in records:
            seen[seller].add(raw["domain"])
        runs.append({"run": run["id"][:8], "created": run["created_at"][:16], "target": profile.target[:70],
                     "advised": [c.description[:60] for c, before in zip(advised.criteria, profile.criteria, strict=True)
                                 if before.required and not c.required]
                                + [f"exclusion: {text}" for index, text in enumerate(profile.exclusions) if index not in kept_exclusions],
                     "records": rows, "first_lead": min(leads)[1] if leads else None})
    return {"runs": runs, "totals": dict(totals)}


if __name__ == "__main__":
    grand = Counter()
    for database in sys.argv[1:]:
        report = replay(database)
        print(f"\n== {database}")
        for run in report["runs"]:
            print(f"{run['created']} {run['run']} target={run['target']!r}")
            if run["advised"]:
                print(f"   checks now nice to have: {run['advised']}")
            for domain, outcome in run["records"]:
                print(f"   {domain:<26} {outcome}")
            print(f"   first lead in the shortlist: {run['first_lead']}")
        grand.update(report["totals"])
    print("\ntotals", json.dumps(dict(sorted(grand.items())), indent=1))
