"""Run PostgreSQL regressions in a unique loopback-only local cluster, then stop it."""

import argparse
import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bin", type=Path, default=ROOT / "data/postgres-runtime/pgsql/bin")
    parser.add_argument("tests", nargs="*", default=["tests/test_postgres.py"])
    parser.add_argument("-k", default="")
    parser.add_argument("--ui", action="store_true", help="Also run all browser flows against this disposable cluster")
    args = parser.parse_args()
    suffix = ".exe" if os.name == "nt" else ""
    binaries = {name: args.bin.resolve() / (name + suffix) for name in ("initdb", "pg_ctl")}
    if not all(path.is_file() for path in binaries.values()):
        raise SystemExit("Supply an installed PostgreSQL bin directory with --bin")
    directory = ROOT / "data" / ("hosted-pg-check-" + uuid4().hex)
    directory.mkdir(parents=True)
    cluster, log = directory / "cluster", directory / "server.log"
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

    def command(name, arguments):
        # A Windows server child can retain an inherited pipe after pg_ctl exits.
        # A file keeps startup output auditable without waiting for pipe EOF.
        with (directory / "commands.log").open("a", encoding="utf-8") as output:
            return subprocess.run([str(binaries[name]), *map(str, arguments)], stdout=output,
                                  stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, close_fds=True,
                                  timeout=45, creationflags=flags, check=True)

    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    command("initdb", ["-D", cluster, "-U", "postgres", "-A", "trust", "--no-locale", "-E", "UTF8"])
    started = False
    try:
        command("pg_ctl", ["-D", cluster, "-l", log, "-o", f"-h 127.0.0.1 -p {port}", "-w", "start"])
        started = True
        database_url = f"postgresql://postgres@127.0.0.1:{port}/postgres"
        environment = dict(os.environ, SHORTLIST_TEST_PG_URL=database_url,
                           PYTHONPATH=os.pathsep.join((str(ROOT / "src"), str(ROOT))))
        test_log = directory / "pytest.log"
        with test_log.open("w", encoding="utf-8") as output:
            result = subprocess.run([sys.executable, "-m", "pytest", *args.tests, "-q", "--tb=short", "--maxfail=1",
                                     "--basetemp=" + str(directory / "pytest"), "-k", args.k],
                                    cwd=ROOT, env=environment, stdout=output, stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL, close_fds=True, creationflags=flags, check=False)
        print(test_log.read_text(encoding="utf-8", errors="replace"))
        if result.returncode == 0 and args.ui:
            environment["SHORTLIST_UI_TEST_PG_URL"] = database_url
            browser_log = directory / "playwright.log"
            with browser_log.open("w", encoding="utf-8") as output:
                result = subprocess.run(["node", str(ROOT / "node_modules/playwright/cli.js"), "test"],
                                        cwd=ROOT, env=environment, stdout=output, stderr=subprocess.STDOUT,
                                        stdin=subprocess.DEVNULL, close_fds=True, creationflags=flags, check=False)
            print(browser_log.read_text(encoding="utf-8", errors="replace"))
        (directory / "result.json").write_text(json.dumps({"exit_code": result.returncode}), encoding="utf-8")
        return result.returncode
    finally:
        if started:
            command("pg_ctl", ["-D", cluster, "-m", "fast", "-w", "stop"])
            print("Stopped the test cluster; diagnostics retained under " + str(directory.relative_to(ROOT)))


if __name__ == "__main__":
    raise SystemExit(main())
