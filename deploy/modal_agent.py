"""The public agent demo (shortlist.agent.public) on Modal: one always-on CPU container serving the built UI and the
agent API, with each search saved as a JSON file on a Modal Volume. Setup and limits: docs/agent-public-demo.md.

    npm ci && npm run build          # the UI goes into dist/, which this image copies
    modal deploy deploy/modal_agent.py

Provider keys and the demo's own settings come from the Modal secret `gtm-shortlist-agent`; nothing secret is in here.
"""
import threading
from pathlib import Path

import modal

ROOT = Path(__file__).resolve().parents[1]
APP_NAME = "gtm-shortlist-agent"

volume = modal.Volume.from_name("gtm-shortlist-agent-runs", create_if_missing=True)
image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install_from_requirements(str(ROOT / "requirements.runtime.txt"))
    # Modal's proxy sets X-Forwarded-For, so the hourly limit counts visitors rather than the proxy.
    .env({"PYTHONPATH": "/app/src", "AGENT_PUBLIC_DATA": "/data/runs", "AGENT_PUBLIC_DIST": "/app/dist",
          "AGENT_PUBLIC_TRUST_PROXY": "on"})
    .add_local_dir(str(ROOT / "dist"), "/app/dist")
    .add_local_dir(str(ROOT / "src" / "shortlist"), "/app/src/shortlist")
)
app = modal.App(APP_NAME, image=image)


class VolumeCommits:
    """Saves are atomic files on the volume; commit them every few seconds instead of on every progress event."""

    def __init__(self, every: float = 3.0):
        self.pending = threading.Event()
        threading.Thread(target=self.loop, args=(every,), name="volume-commits", daemon=True).start()

    def __call__(self):
        self.pending.set()

    def loop(self, every: float):
        while True:
            self.pending.wait()
            self.pending.clear()
            try:
                volume.commit()
            except Exception as exc:  # noqa: BLE001 - thread boundary: retry with the next change, keep serving
                print(f"Volume commit failed: {exc}")
                self.pending.set()
            threading.Event().wait(every)


# One container keeps the per-visitor limits, the running searches and the files in one place.
@app.function(secrets=[modal.Secret.from_name("gtm-shortlist-agent")], volumes={"/data": volume},
              min_containers=1, max_containers=1, timeout=1800, memory=1024)
@modal.concurrent(max_inputs=100)
@modal.asgi_app()
def web():
    from shortlist.agent.public import create_public_app
    return create_public_app(after_write=VolumeCommits())
