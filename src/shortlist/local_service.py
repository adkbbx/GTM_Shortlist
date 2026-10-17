"""Explicit local worker startup, owned by the API lifetime."""
import logging
from threading import Event, Lock, Thread

from shortlist.config import Settings
from shortlist.local_credentials import apply_local_credentials
from shortlist.store import Store


class ServiceUnavailable(RuntimeError):
    pass


class LocalResearchService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.lock = Lock()
        self.stopped = Event()
        self.thread: Thread | None = None
        self.closed = False

    def start(self):
        from shortlist.worker import work

        with self.lock:
            if self.closed:
                raise ServiceUnavailable("The app is closing. Reopen it before starting research.")
            readiness = apply_local_credentials(self.settings).readiness()
            if not all(readiness.values()):
                raise ServiceUnavailable("Configure company search and the research model before starting the research service.")
            if Store(self.settings.db_path).worker_online():
                return  # Includes a separately supervised CLI worker.
            if self.thread and self.thread.is_alive():
                raise ServiceUnavailable("The research service is still starting or stopping. Wait a moment and try again.")
            self.stopped.clear()
            started = Event()

            def run():
                try:
                    work(self.settings, stopped=self.stopped, started=started)
                except Exception:  # noqa: BLE001 - thread boundary must not print credentials
                    # Provider/configuration exceptions must never expose secrets
                    # through an unhandled thread traceback.
                    logging.getLogger(__name__).error("Local research service stopped unexpectedly")
                finally:
                    started.set()

            self.thread = Thread(target=run, name="shortlist-local-research", daemon=True)
            self.thread.start()
            if not started.wait(5) or not Store(self.settings.db_path).worker_online():
                self.stopped.set()
                raise ServiceUnavailable("The research service could not start. Check your local settings and try again.")

    def close(self):
        with self.lock:
            self.closed = True
            self.stopped.set()
            thread = self.thread
        if thread:
            thread.join(timeout=5)
