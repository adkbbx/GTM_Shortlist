"""The installed one-command app (`gtm-shortlist`). scripts/package_smoke.py runs the built wheel end to end."""
import os
import sys
from pathlib import Path

import pytest

from shortlist import cli


@pytest.fixture
def launched(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "serve", lambda settings, port, open_browser: calls.append((settings, port, open_browser)))
    # start() sets SHORTLIST_DB itself; registering it first makes pytest restore the original afterwards.
    monkeypatch.setenv("SHORTLIST_DB", "unset")
    monkeypatch.delenv("SHORTLIST_DB")
    monkeypatch.setenv("SHORTLIST_MODE", "hosted")  # A stray hosted setting never applies to the local app.
    return calls


def test_one_command_app_runs_locally_with_research_in_the_user_folder(launched, monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "home_database", lambda: tmp_path / "home" / "shortlist.sqlite3")
    monkeypatch.setattr(sys, "argv", ["gtm-shortlist"])
    cli.start()
    settings, port, open_browser = launched[0]
    assert settings.mode == "local" and port == 8014 and open_browser
    assert settings.db_path == tmp_path / "home" / "shortlist.sqlite3"


def test_explicit_database_and_no_browser_are_respected(launched, monkeypatch, tmp_path):
    monkeypatch.setenv("SHORTLIST_DB", str(tmp_path / "chosen.sqlite3"))
    monkeypatch.setattr(sys, "argv", ["gtm-shortlist", "--port", "8020", "--no-browser"])
    cli.start()
    settings, port, open_browser = launched[0]
    assert settings.db_path == tmp_path / "chosen.sqlite3" and port == 8020 and not open_browser


@pytest.mark.skipif(os.name != "nt", reason="Windows keeps app data under LOCALAPPDATA")
def test_windows_research_lives_in_local_app_data(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert cli.home_database() == tmp_path / "GTM Shortlist" / "shortlist.sqlite3"


@pytest.mark.skipif(os.name == "nt" or sys.platform == "darwin", reason="Linux follows XDG_DATA_HOME")
def test_linux_research_follows_xdg_data_home(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert cli.home_database() == Path(tmp_path) / "gtm-shortlist" / "shortlist.sqlite3"
