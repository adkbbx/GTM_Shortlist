"""Credit-free before/after admission and NEED evidence on hand-labelled saved excerpts."""
import argparse
import hashlib
import json
from pathlib import Path

from shortlist.competitors import competitor_issue
from shortlist.domain import Candidate, Criterion, Profile, Source
from shortlist.relevance import candidate_issue
from shortlist.verification import reader_need

CASES = Path(__file__).resolve().parents[1] / "examples/evaluation/competitor-cases.json"


def inputs(case):
    seller, primary = case["seller"], case["primary"]
    profile = Profile(seller_url="https://" + seller["domain"] + "/", offer=seller["offer"], target=seller["target"],
                      criteria=(Criterion(id="need", description="Evidence of a need for partner training"),))
    source = Source(url=primary["url"], company_domain=case["domain"], title=primary["title"], text=primary["opening"],
                    content_hash=hashlib.sha256(primary["opening"].encode()).hexdigest())
    candidate = Candidate(domain=case["domain"], url=source.url, name=source.title, excerpt=source.text,
                          query=profile.target, provider="labelled_saved_excerpt")
    return profile, candidate, source


def check(path=CASES):
    corpus = json.loads(Path(path).read_text(encoding="utf-8"))
    result = {"cases": [], "before": {}, "after": {}}
    for case in corpus["cases"]:
        profile, candidate, source = inputs(case)
        row = {"domain": case["domain"], "label": case["label"], "provenance": case["provenance"]}
        for name, policy in (("before", 4), ("after", 5)):
            row[name] = competitor_issue(profile, candidate.domain, source, policy=policy) or candidate_issue(
                candidate, target=profile.target, policy=policy)
        result["cases"].append(row)
    peers = [c for c in result["cases"] if c["label"] == "competitor/peer"]
    buyers = [c for c in result["cases"] if c["label"] == "buyer"]
    for name in ("before", "after"):
        result[name] = {"peers_set_aside": sum(bool(c[name]) for c in peers), "peers": len(peers),
                        "buyers_kept": sum(not c[name] for c in buyers), "buyers": len(buyers),
                        "buyers_lost": [c["domain"] for c in buyers if c[name]]}
    needs = corpus["need_cases"]
    result["need_evidence"] = {
        "reader_needs_before": sum(c["label"] == "reader_need" for c in needs),
        "reader_needs_after": sum(c["label"] == "reader_need" and not reader_need(c["passage"]) for c in needs),
        "company_passages": sum(c["label"] == "company_programme_or_offering" for c in needs),
        "company_passages_kept": sum(c["label"] == "company_programme_or_offering" and not reader_need(c["passage"]) for c in needs)}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=CASES)
    args = parser.parse_args()
    report = check(args.cases)
    for name in ("before", "after"):
        row = report[name]
        print(f"{name}: peers set aside {row['peers_set_aside']}/{row['peers']}; "
              f"buyers kept {row['buyers_kept']}/{row['buyers']}; buyers lost {len(row['buyers_lost'])}")
    for row in report["cases"]:
        print(f"{row['domain']} [{row['provenance']}]: " + (row["after"] or "kept"))
    row = report["need_evidence"]
    print(f"NEED evidence: reader needs retained {row['reader_needs_before']} -> {row['reader_needs_after']}; "
          f"company programme/offering passages kept {row['company_passages_kept']}/{row['company_passages']}")
    after = report["after"]
    return int(after["peers_set_aside"] != after["peers"] or bool(after["buyers_lost"]) or
               row["reader_needs_after"] != 0 or row["company_passages_kept"] != row["company_passages"])


if __name__ == "__main__":
    raise SystemExit(main())
