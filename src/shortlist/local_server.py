"""One local command supervises separate API and durable worker processes."""
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser

from shortlist.config import Settings
from shortlist.windows_job import protect_process_tree


def open_when_ready(url: str, attempts: int = 150, opener=webbrowser.open, probe=None, wait=lambda: time.sleep(.2)) -> bool:
    """Open the browser once the local API answers, so the first page never shows a connection error."""
    def answering():
        with urllib.request.urlopen(url + "api/health", timeout=1) as response:
            return response.status == 200
    for _ in range(attempts):
        try:
            if (probe or answering)():
                opener(url)
                return True
        except OSError:
            pass
        wait()
    return False


def serve(settings: Settings, port: int, open_browser: bool = False):
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
        if open_browser:
            threading.Thread(target=open_when_ready, args=(f"http://127.0.0.1:{port}/",), daemon=True).start()
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
