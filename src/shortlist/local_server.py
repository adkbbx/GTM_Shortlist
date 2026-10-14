"""One local command supervises separate API and durable worker processes."""
import os
import signal
import socket
import subprocess
import sys
import time

from shortlist.config import Settings
from shortlist.windows_job import protect_process_tree


def serve(settings: Settings, port: int):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", port))  # Fail before launching children if the port is in use.
    protect_process_tree()
    environment = {**os.environ, "SHORTLIST_DB": str(settings.db_path.resolve())}
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    processes = []

    def stop(signum, frame):
        raise KeyboardInterrupt()

    previous = signal.signal(signal.SIGTERM, stop)
    try:
        for arguments in (("shortlist.cli", "worker"),
                          ("uvicorn", "shortlist.api:app", "--host", "127.0.0.1", "--port", str(port))):
            processes.append(subprocess.Popen([sys.executable, "-m", *arguments], env=environment,
                                              creationflags=flags))
        print(f"GTM Shortlist API and worker: http://127.0.0.1:{port}", flush=True)
        while all(process.poll() is None for process in processes):
            time.sleep(.2)
        raise RuntimeError("The API or worker exited; the local service stopped. Inspect its error and restart.")
    except KeyboardInterrupt:
        pass
    finally:
        signal.signal(signal.SIGTERM, previous)
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
