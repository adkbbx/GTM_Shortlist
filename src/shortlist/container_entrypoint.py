"""Hosted-only image entry points; runtime services never run migrations."""
import argparse
import os
import sys
from pathlib import Path

from shortlist.config import Settings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("service", choices=("api", "worker", "migrate", "agent"))
    service = parser.parse_args().service
    if service == "migrate":
        command = [sys.executable, str(Path(__file__).resolve().parents[2] / "scripts/migrate_postgres.py")]
    elif service == "agent":
        # Public agent demo (Meta hackathon): its own settings (AGENT_PUBLIC_*), no hosted accounts or database.
        command = [sys.executable, "-m", "uvicorn", "--factory", "shortlist.agent.public:create_public_app",
                   "--host", "0.0.0.0", "--port", "8000"]
    else:
        settings = Settings.load()
        if settings.mode != "hosted":
            parser.error("Container services require hosted mode; use the loopback supervisor for local research")
        if service == "worker" and not settings.worker_database_url.get_secret_value():
            parser.error("Worker requires its separate database credential")
        command = [sys.executable, "-m", "shortlist.cli", "worker"] if service == "worker" else [
            sys.executable, "-m", "uvicorn", "shortlist.api:app", "--host", "0.0.0.0", "--port", "8000"]
    os.execv(sys.executable, command)


if __name__ == "__main__":
    main()
