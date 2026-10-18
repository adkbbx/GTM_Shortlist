"""Check local reader-document links without fetching any remote page.

Run from any directory. --commands also lists README code blocks for manual verification.
"""
import argparse
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS = ("README.md", "CONTRIBUTING.md", "SECURITY.md")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commands", action="store_true")
    args = parser.parse_args()
    errors = []
    count = 0
    for name in DOCUMENTS:
        path = ROOT / name
        content = path.read_text(encoding="utf-8")
        for destination in re.findall(r"\]\(([^)]+)\)", content):
            parsed = urlsplit(destination)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            count += 1
            target = path.parent / unquote(parsed.path)
            if not target.is_file():
                errors.append(f"{name}: missing {destination}")
        if args.commands and name == "README.md":
            for index, block in enumerate(re.findall(r"```[^\n]*\n(.*?)```", content, re.DOTALL), 1):
                print(f"README command block {index}:\n{block.rstrip()}\n")
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"Reader-document links passed: {count} local links in {len(DOCUMENTS)} files; no network requests")


if __name__ == "__main__":
    main()
