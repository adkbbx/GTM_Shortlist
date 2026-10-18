"""Credit-free comparison of compact excerpts from read-only saved SQLite databases."""
import argparse
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from shortlist.domain import Profile, Source
from shortlist.prompting import MENU_RUN, excerpts
from shortlist.relevance import quoted_in


def measure(pages: list[dict]) -> dict:
    chars = sum(len(page["text"]) for page in pages)
    content = sum(len(line) for page in pages for line in page["text"].splitlines() if len(line.split()) >= 6)
    return {"chars": chars, "content_chars": content, "content_share": content / chars if chars else 0}


def check(paths: list[Path], *, budget: int = 8000) -> dict:
    sets = {}
    for path in paths:
        with closing(sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)) as db:
            for profile_json, checkpoint_json, run_id in db.execute("SELECT profile,checkpoint,id FROM runs ORDER BY rowid"):
                if not json.loads(profile_json):
                    continue
                profile = Profile.model_validate_json(profile_json)
                checkpoint = json.loads(checkpoint_json)
                focus = " ".join((profile.target, *(c.description for c in profile.criteria), *profile.exclusions))
                records = [json.loads(row[0]) for row in db.execute("SELECT research FROM records WHERE run_id=?", (run_id,))]
                for domain, pages in checkpoint.get("sources", {}).items():
                    sources = tuple(Source.model_validate(page) for page in pages)
                    key = (domain, tuple(s.id for s in sources), focus)
                    before = excerpts(sources, focus, budget, menu_run=0)
                    after = excerpts(sources, focus, budget, menu_run=MENU_RUN)
                    row = sets.setdefault(key, {"domain": domain, "source_ids": [s.id for s in sources],
                                               "runs": [], "before": measure(before), "after": measure(after), "missing": []})
                    origin = {"database": str(path), "run_id": run_id}
                    if origin not in row["runs"]:
                        row["runs"].append(origin)
                    for record in records:
                        if record["domain"] != domain:
                            continue
                        for finding in record.get("findings", []):
                            if finding["status"] not in ("supported", "contradicted"):
                                continue
                            for evidence in finding.get("evidence", []):
                                passage = evidence["passage"]
                                if any(quoted_in(passage, part) for page in after for part in page["text"].split("\n…\n")):
                                    continue
                                missing = {"criterion_id": finding["criterion_id"], "status": finding["status"],
                                           "passage": passage, "sent_before": any(
                                               quoted_in(passage, part) for page in before for part in page["text"].split("\n…\n"))}
                                if missing not in row["missing"]:
                                    row["missing"].append(missing)
    totals = {}
    for label in ("before", "after"):
        chars = sum(row[label]["chars"] for row in sets.values())
        content = sum(row[label]["content_chars"] for row in sets.values())
        totals[label] = {"chars": chars, "content_chars": content, "content_share": content / chars if chars else 0}
    return {"company_page_sets": len(sets), "totals": totals, "pages": list(sets.values())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("databases", type=Path, nargs="+")
    parser.add_argument("--budget", type=int, default=8000)
    args = parser.parse_args()
    print(json.dumps(check(args.databases, budget=args.budget), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
