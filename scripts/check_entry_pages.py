"""Live, credit-free check of research entry pages for the labelled real companies.

For each 'company' result in examples/evaluation/discovery-admission.json, fetch the page research would start from
(policy 1: the page as found; policy 2: relevance.research_entry) with the app's own fetcher and its public-address and
size limits, then apply the strict first-party identity check to the page that actually came back. Page fetches only:
no search, model or enrichment call. Usage: python scripts/check_entry_pages.py [--out result.json]
"""
import argparse
import json
import time
from pathlib import Path

from shortlist.fetch import FetchError, domain_of, fetch_page
from shortlist.relevance import primary_source_issue, research_entry

FIXTURE = Path(__file__).resolve().parents[1] / "examples/evaluation/discovery-admission.json"


def check(url: str, domain: str) -> dict:
    try:
        source = fetch_page(url, expected_domain=domain)
    except FetchError as exc:
        return {"url": url, "outcome": "unreadable", "detail": str(exc)}
    issue = primary_source_issue(source, strict=True)
    return {"url": url, "outcome": "refused" if issue else "researchable", "detail": issue or source.title[:90],
            "words": len(source.text.split())}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    rows = []
    for result in json.loads(FIXTURE.read_text(encoding="utf-8"))["results"]:
        if result["label"] != "company":
            continue
        domain = domain_of(result["url"])
        before = check(result["url"], domain)
        entry = research_entry(result["url"], result["title"])
        after = before if entry == result["url"] else check(entry, domain)
        rows.append({"company": domain, "before": before, "after": after})
        print(f"{domain:<26} before={before['outcome']:<12} after={after['outcome']:<12} {after['detail'][:70]}", flush=True)
        time.sleep(0.5)  # Polite pacing for public sites.
    summary = {f"{when}:{outcome}": sum(row[when]["outcome"] == outcome for row in rows)
               for when in ("before", "after") for outcome in ("researchable", "refused", "unreadable")}
    print(json.dumps(summary, indent=1))
    if args.out:
        args.out.write_text(json.dumps({"checked_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "summary": summary, "rows": rows},
                                       indent=1, ensure_ascii=False), encoding="utf-8")
