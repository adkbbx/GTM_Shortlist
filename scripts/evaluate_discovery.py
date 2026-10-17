"""Offline discovery check against labelled real search results (examples/evaluation/discovery-admission.json).

No search, fetch or model call: each saved result goes through the same admission the search adapters apply, then the
strict first-party page check the worker applies after fetching a candidate. Reports what reaches research.
"""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from shortlist.domain import Source
from shortlist.providers import candidates_from_results
from shortlist.relevance import primary_source_issue, research_entry

FIXTURE = Path(__file__).resolve().parents[1] / "examples/evaluation/discovery-admission.json"


def outcome(result: dict, policy: int) -> tuple[str, str | None]:
    """'research' (reaches research), 'wasted' (fetched, then rejected) or 'skipped' (never fetched), with the URL used.
    Policy 1 fetches the page as found; policy 2 starts research from `research_entry`."""
    admitted = candidates_from_results([{"url": result["url"], "title": result["title"]}], "labelled evaluation", "fixture", None)
    if not admitted:
        return "skipped", None
    candidate = admitted[0]
    url = research_entry(candidate.url, candidate.name) if policy >= 2 else candidate.url
    # The fetched page's own title is unknown offline; the search title stands in for it.
    page = Source(url=url, company_domain=candidate.domain, title=candidate.name, text="Labelled evaluation page",
                  content_hash=hashlib.sha256(url.encode()).hexdigest())
    return ("wasted" if primary_source_issue(page, strict=True) else "research"), url


def evaluate(path: Path = FIXTURE, policy: int = 2) -> dict:
    results = json.loads(path.read_text(encoding="utf-8"))["results"]
    table = Counter()
    rows = []
    for result in results:
        state, url = outcome(result, policy)
        table[(result["label"], state)] += 1
        rows.append({**result, "outcome": state, "candidate_url": url})
    companies = sum(r["label"] == "company" for r in results)
    junk = sum(r["label"] == "not_company" for r in results)
    return {
        "companies_reaching_research": f"{table[('company', 'research')]} of {companies}",
        "non_companies_reaching_research": f"{table[('not_company', 'research')]} of {junk}",
        "editorial_reaching_research": table[("editorial", "research")],
        "fetches_wasted_on_rejected_pages": sum(n for (label, state), n in table.items() if state == "wasted"),
        "detail": {f"{label}/{state}": n for (label, state), n in sorted(table.items())},
        "rows": rows,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--show", choices=("company", "not_company", "editorial"), help="List outcomes for one label")
    parser.add_argument("--policy", type=int, choices=(1, 2), default=2, help="1: fetch the page as found; 2: research entry")
    args = parser.parse_args()
    report = evaluate(policy=args.policy)
    rows = report.pop("rows")
    print(json.dumps(report, indent=2))
    for row in rows:
        if row["label"] == args.show:
            print(f"{row['outcome']:<8} {row['url'][:80]:<80} -> {row['candidate_url'] or '':<40} | {row['title'][:50]}")
