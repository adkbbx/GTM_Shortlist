"""Repeatable offline check of manually labelled confirmed targets. No provider calls."""
import json
from pathlib import Path

from shortlist.providers import broad_target

if __name__ == "__main__":
    path = Path(__file__).resolve().parents[1] / "examples/evaluation/target-breadth.json"
    cases = json.loads(path.read_text(encoding="utf-8"))
    correct = 0
    for case in cases:
        actual = broad_target(case["target"])
        correct += actual == case["broad"]
        print(f"{case['label']}: {'broad' if actual else 'specific'}; expected {'broad' if case['broad'] else 'specific'}")
    print(f"{correct} of {len(cases)} labelled saved targets agree")
    raise SystemExit(correct != len(cases))
