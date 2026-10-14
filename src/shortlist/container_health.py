"""Process liveness for API; recent shared durable heartbeat for worker health."""
import argparse
from urllib.parse import urlsplit

import httpx
import psycopg

from shortlist.config import Settings


def healthy(settings: Settings, service: str) -> bool:
    if settings.mode != "hosted":
        return False
    if service == "api":
        response = httpx.get("http://127.0.0.1:8000/api/health",
                             headers={"Host": urlsplit(settings.app_url).hostname}, timeout=5, trust_env=False)
        return response.status_code == 200 and response.json().get("mode") == "hosted"
    from shortlist.postgres import PostgresStore
    return PostgresStore(settings.worker_database_url, None, worker=True).worker_online()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("service", choices=("api", "worker"))
    service = parser.parse_args().service
    try:
        result = healthy(Settings.load(), service)
    except (OSError, ValueError, httpx.HTTPError, psycopg.Error):
        # No credentials, provider bodies or database exception strings in logs.
        result = False
    raise SystemExit(0 if result else 1)


if __name__ == "__main__":
    main()
