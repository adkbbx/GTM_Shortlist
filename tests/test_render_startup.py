"""Render replaces both image startup instructions, so commands must be executable."""
import json
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from shortlist import container_entrypoint
from shortlist.config import Settings

ROOT = Path(__file__).resolve().parents[1]
SERVICES = json.loads((ROOT / "render.yaml").read_text(encoding="utf-8"))["services"]


@pytest.mark.parametrize("service", SERVICES, ids=lambda item: item["name"])
def test_render_override_launches_and_selects_the_right_process(service, monkeypatch):
    command = shlex.split(service["dockerCommand"])
    # Run the configured complete command with ENTRYPOINT absent, just as Render does.
    executable = sys.executable if command[0] == "python" else command[0]
    result = subprocess.run([executable, *command[1:], "--help"], cwd=ROOT,
                            capture_output=True, text=True, timeout=15, check=False)
    assert result.returncode == 0, result.stderr
    assert "api,worker,migrate" in result.stdout
    settings = Settings(mode="hosted", database_url="labelled-api-database",
        worker_database_url="labelled-worker-database", supabase_url="https://auth.example",
        supabase_publishable_key="sb_publishable_fixture", app_url="https://app.example")
    monkeypatch.setattr(Settings, "load", classmethod(lambda cls: settings))
    monkeypatch.setattr(sys, "argv", command[2:])
    dispatched = []
    monkeypatch.setattr(container_entrypoint.os, "execv", lambda executable, args: dispatched.append(args))
    container_entrypoint.main()
    assert len(dispatched) == 1
    if service["type"] == "worker":
        assert dispatched[0] == [sys.executable, "-m", "shortlist.cli", "worker"]
    elif service["name"] == "gtm-shortlist-agent":
        # The public agent demo needs no hosted settings and serves its own app factory.
        assert dispatched[0][1:5] == ["-m", "uvicorn", "--factory", "shortlist.agent.public:create_public_app"]
    else:
        assert dispatched[0][1:4] == ["-m", "uvicorn", "shortlist.api:app"]
