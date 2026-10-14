"""Real disposable image/API/worker/Postgres smoke; no live accounts or providers."""
import json
import os
import re
import subprocess
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4


def docker(*arguments, input=None):
    result = subprocess.run(["docker", *arguments], input=input, text=True, capture_output=True,
                            timeout=180, check=True)
    return result.stdout.strip()


def wait_ready(name):
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        state = json.loads(docker("inspect", "--format", "{{json .State}}", name))
        if state["Status"] != "running":
            raise RuntimeError("Disposable container failed to start: " + name)
        if state.get("Health", {}).get("Status") == "healthy":
            return
        time.sleep(.5)
    raise TimeoutError("Disposable container did not become healthy: " + name)


def main():
    root = Path(__file__).resolve().parents[1]
    with TemporaryDirectory(prefix="shortlist-compose-check-") as folder:
        target = Path(folder)
        (target / "secrets").mkdir()
        for name in ("compose.yaml", "Caddyfile"):
            (target / name).write_text((root / "deploy" / name).read_text(), encoding="utf-8")
        for name in ("api", "worker"):
            (target / "secrets" / (name + ".env")).write_text(
                (root / "deploy" / (name + ".env.example")).read_text(), encoding="utf-8")
        subprocess.run(["docker", "compose", "-f", str(target / "compose.yaml"), "config", "--quiet"],
                       env={**os.environ, "SHORTLIST_IMAGE": "shortlist-check", "SHORTLIST_HOST": "app.example"},
                       timeout=30, check=True)
    prefix = "shortlist-check-" + uuid4().hex[:12]
    database, api, worker = (prefix + suffix for suffix in ("-db", "-api", "-worker"))
    created = []
    docker("network", "create", prefix)
    try:
        docker("run", "-d", "--name", database, "--network", prefix,
               "-e", "POSTGRES_PASSWORD=labelled-container-fixture", "--health-cmd", "pg_isready -U postgres",
               "--health-interval", "1s", "--health-retries", "30", "postgres:18")
        created.append(database)
        wait_ready(database)
        operator = f"postgresql://postgres:labelled-container-fixture@{database}:5432/postgres"
        for _ in range(2):
            docker("run", "--rm", "--network", prefix, "-e", "SHORTLIST_MIGRATION_DATABASE_URL=" + operator,
                   "shortlist-check", "migrate")
        docker("exec", "-i", database, "psql", "-U", "postgres", "-v", "ON_ERROR_STOP=1", input="""
CREATE ROLE api_fixture LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD 'labelled-api' IN ROLE shortlist_api;
CREATE ROLE worker_fixture LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD 'labelled-worker' IN ROLE shortlist_worker;
""")
        common = ["-e", "SUPABASE_URL=https://auth.example", "-e", "SUPABASE_PUBLISHABLE_KEY=sb_publishable_container_fixture",
                  "-e", "SHORTLIST_APP_URL=https://app.example"]
        worker_dsn = f"postgresql://worker_fixture:labelled-worker@{database}:5432/postgres"
        docker("run", "-d", "--name", worker, "--network", prefix, *common,
               "-e", "SHORTLIST_DATABASE_URL=" + worker_dsn, "-e", "SHORTLIST_WORKER_DATABASE_URL=" + worker_dsn,
               "--health-cmd", "python -m shortlist.container_health worker", "shortlist-check", "worker")
        created.append(worker)
        docker("run", "-d", "--name", api, "--network", prefix, *common,
               "-e", f"SHORTLIST_DATABASE_URL=postgresql://api_fixture:labelled-api@{database}:5432/postgres",
               "-p", "127.0.0.1::8000", "shortlist-check", "api")
        created.append(api)
        wait_ready(worker)
        wait_ready(api)
        assert docker("exec", api, "id", "-u") == "10001"
        docker("exec", api, "python", "-c", "from uuid import UUID; from shortlist.config import Settings; "
               "from shortlist.postgres import PostgresStore; store=PostgresStore(Settings.load().database_url, UUID(int=0)); "
               "\nwith store.connection() as db: db.execute('SELECT deleted_at,legacy_credit_exempt FROM runs LIMIT 0'); "
               "db.execute('SELECT requested,consumed FROM credit_reservations LIMIT 0')")
        assert json.loads(docker("inspect", "--format", "{{json .HostConfig.PortBindings}}", database)) in (None, {})
        docker("exec", api, "python", "-c", "from pathlib import Path; import shutil; "
               "assert shutil.which('node') is None; assert not Path('/app/.env').exists(); "
               "assert not Path('/app/data').exists(); assert not Path('/app/tests').exists()")
        port = docker("port", api, "8000").rsplit(":", 1)[1]
        origin = "http://127.0.0.1:" + port

        def get(path):
            with urlopen(Request(origin + path, headers={"Host": "app.example"}), timeout=5) as response:
                return response.read()

        assert json.loads(get("/api/health")) == {"mode": "hosted", "search_ready": False,
                                                "gemma_ready": False, "worker_online": False}
        setup = json.loads(get("/api/auth/setup"))
        assert setup["mode"] == "hosted" and setup["publishable_key"] == "sb_publishable_container_fixture"
        try:
            get("/api/runs")
        except HTTPError as exc:
            assert exc.code == 401
        else:
            raise AssertionError("Hosted image exposed research without authentication")
        html = get("/").decode()
        assets = re.findall(r'(?:src|href)="(/assets/[^\"]+)"', html)
        assert assets
        for path in assets:
            assert get(path)
        docker("restart", worker)
        docker("restart", api)
        wait_ready(worker)
        wait_ready(api)
        assert get("/").decode() == html
        print("PASS: non-root image, real migrations/replay, private Postgres, separate worker/API, assets, auth boundary and restart")
    finally:
        for name in reversed(created):
            docker("rm", "-f", name)
        docker("network", "rm", prefix)


if __name__ == "__main__":
    main()
