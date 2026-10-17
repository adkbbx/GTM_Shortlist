"""Install a built wheel into a fresh virtual environment and check the one-command app: API, worker and packaged UI.

Usage: python scripts/package_smoke.py package-dist/gtm_shortlist-*.whl
Runs `gtm-shortlist --no-browser` against a throwaway database; no provider is configured or called.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
import venv
from pathlib import Path

wheel = Path(sys.argv[1]).resolve()
port = 8031
with tempfile.TemporaryDirectory(prefix="gtm-shortlist-package-") as folder:
    environment = Path(folder) / "venv"
    venv.EnvBuilder(with_pip=True).create(environment)
    scripts = environment / ("Scripts" if os.name == "nt" else "bin")
    subprocess.run([str(scripts / "python"), "-m", "pip", "install", "--quiet", str(wheel)], check=True)
    command = scripts / ("gtm-shortlist.exe" if os.name == "nt" else "gtm-shortlist")
    database = Path(folder) / "data" / "shortlist.sqlite3"
    # Run from an unrelated folder: the installed app must not depend on a checkout or its dist/.
    app = subprocess.Popen([str(command), "--no-browser", "--port", str(port)], cwd=folder,
                           env={**os.environ, "SHORTLIST_DB": str(database)})
    try:
        for _ in range(150):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1) as response:
                    health = json.load(response)
                if health["worker_online"]:
                    break
            except OSError:
                pass
            if app.poll() is not None:
                sys.exit("gtm-shortlist exited before answering")
            time.sleep(.2)
        else:
            sys.exit("gtm-shortlist did not report an online worker")
        assert health["mode"] == "local" and not health["search_ready"], health
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5) as response:
            page = response.read().decode()
        assert '<div id="root">' in page and "/assets/" in page, "The packaged UI was not served"
        assert database.exists(), "Research was not saved where SHORTLIST_DB points"
        print("Package smoke passed: API, worker and packaged UI answer from an installed wheel")
    finally:
        app.terminate()
        try:
            app.wait(timeout=15)
        except subprocess.TimeoutExpired:
            app.kill()
