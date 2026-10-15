"""Validate the proposed storyboard and its local planning assets, without provider calls."""
import json
import re
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    folder = root / "docs" / "planning" / "landing-demo"
    storyboard = json.loads((folder / "storyboard.json").read_text(encoding="utf-8"))
    stages = storyboard["stages"]
    identifiers = [stage["id"] for stage in stages]
    assert identifiers == ["offer", "market", "confirm", "discover", "evidence", "review"]
    assert storyboard["provider_calls"] == 0
    assert storyboard["changes_production"] is False
    assert storyboard["real_confirmation_required"] is True
    assert storyboard["automatic_outreach"] is False
    assert storyboard["reduced_motion_stage"] == storyboard["terminal_stage"] == "review"
    for stage in stages:
        assert (stage["hold_ms"] is None) == (stage["pause_for"] is not None)
    assert stages[2]["pause_for"] == "confirm_example_target"
    assert stages[4]["pause_for"] == "inspect_example_passage"
    text = (folder / "PLAN.md").read_text(encoding="utf-8")
    for link in re.findall(r"!\[[^]]*\]\(([^)]+)\)", text):
        assert (folder / link).is_file(), link
    for color in ("#f7f7f5", "#1b1b1b", "#b4501c", "#e1dfd9"):
        assert color in (root / "DESIGN.md").read_text(encoding="utf-8")
        assert color in text
    print("Plan verified: six stages, explicit interaction pauses, preserved brand colors,")
    print("visible reduced-motion result, existing screenshot, and zero-provider sample boundary.")
    print("This validates the planning specification; the UI is not implemented.")


if __name__ == "__main__":
    main()
