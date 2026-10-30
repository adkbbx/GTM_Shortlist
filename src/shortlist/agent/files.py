"""Agent runs as one JSON file each, for the public demo on a mounted volume (one container, no database server).

Writes are atomic (temporary file, then rename) and serialised by one lock. Run ids are 32 lowercase hex characters
(shortlist.domain.new_id); anything else is treated as not found, so a run id can never name a path.
"""
import json
import os
import re
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from threading import Lock

from shortlist.agent.models import AgentEvent, RunResult
from shortlist.agent.storage import MAX_EVENTS, prior_research
from shortlist.domain import utcnow

RUN_ID = re.compile(r"[0-9a-f]{32}")
ACTIVE = ("queued", "running")
INTERRUPTED = "The server restarted while this run was working. Start a new search to run it again."


class FileAgentRuns:
    def __init__(self, directory: Path, after_write: Callable[[], None] | None = None):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.after_write = after_write
        self.lock = Lock()

    def path(self, run_id: str) -> Path:
        if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
            raise KeyError(run_id)
        return self.directory / f"{run_id}.json"

    def read(self, run_id: str) -> dict:
        try:
            return json.loads(self.path(run_id).read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise KeyError(run_id) from None

    def write(self, record: dict) -> None:
        target = self.path(record["id"])
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(record), encoding="utf-8")
        os.replace(temporary, target)
        if self.after_write is not None:
            self.after_write()

    def record(self, result: RunResult, events: list | None = None, created: str | None = None) -> dict:
        return {"id": result.id, "created_at": created or result.created_at.isoformat(),
                "updated_at": utcnow().isoformat(), "status": result.status, "website": result.website,
                "payload": result.model_dump(mode="json"), "events": events or []}

    def create(self, result: RunResult) -> None:
        with self.lock:
            if self.path(result.id).exists():
                raise ValueError("A run with this id already exists")
            self.write(self.record(result))

    def save(self, result: RunResult) -> None:
        with self.lock:
            try:
                old = self.read(result.id)
            except KeyError:
                old = {"events": [], "created_at": None}
            self.write(self.record(result, old["events"], old["created_at"]))

    def set_status(self, run_id: str, status: str) -> None:
        with self.lock:
            record = self.read(run_id)
            record["payload"]["status"] = record["status"] = status
            record["updated_at"] = utcnow().isoformat()
            self.write(record)

    def append_event(self, run_id: str, event: AgentEvent) -> None:
        with self.lock:
            try:
                record = self.read(run_id)
            except KeyError:
                return
            events = record["events"]
            event = event.model_copy(update={"seq": (events[-1]["seq"] if events else 0) + 1})
            record["events"] = (events + [event.model_dump(mode="json")])[-MAX_EVENTS:]
            self.write(record)

    def get(self, run_id: str) -> dict:
        record = self.read(run_id)
        return {"id": record["id"], "status": record["status"], "created_at": record["created_at"],
                "updated_at": record["updated_at"], "result": RunResult.model_validate(record["payload"]),
                "events": [AgentEvent.model_validate(e) for e in record["events"]]}

    def events(self, run_id: str, after: int = 0) -> tuple[str, list[AgentEvent]]:
        record = self.read(run_id)
        return record["status"], [AgentEvent.model_validate(e) for e in record["events"] if e["seq"] > after]

    def records(self) -> list[dict]:
        found = []
        for file in self.directory.glob("*.json"):
            try:
                found.append(json.loads(file.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                continue
        return sorted(found, key=lambda record: record["created_at"], reverse=True)

    def list(self, limit: int = 20) -> list[dict]:
        summaries = []
        for record in self.records()[:limit]:
            counts = {kind: 0 for kind in ("shortlisted", "needs_look", "rejected")}
            for company in record["payload"].get("companies", []):
                kind = (company.get("verdict") or {}).get("kind")
                if kind in counts:
                    counts[kind] += 1
            summaries.append({"id": record["id"], "created_at": record["created_at"], "status": record["status"],
                              "website": record["website"], "synthetic": bool(record["payload"].get("synthetic")),
                              **counts})
        return summaries

    def researched(self, seller_domain: str, since: datetime) -> dict[str, dict]:
        return prior_research(((r["id"], r["created_at"], r["payload"]) for r in self.records()
                               if datetime.fromisoformat(r["created_at"]) >= since), seller_domain)

    def usage_since(self, since: datetime) -> tuple[float, int]:
        """Estimated dollars spent by runs created since `since`, and how many runs are working right now."""
        spent, active = 0.0, 0
        for record in self.records():
            if record["status"] in ACTIVE:
                active += 1
            if datetime.fromisoformat(record["created_at"]) >= since:
                spent += float(record["payload"].get("telemetry", {}).get("cost_usd", 0.0))
        return spent, active

    def recover_interrupted(self) -> int:
        """Runs left working by a previous process can never finish; mark them failed so their pages stop waiting."""
        recovered = 0
        with self.lock:
            for record in self.records():
                if record["status"] in ACTIVE:
                    record["payload"].update(status="failed", error=INTERRUPTED)
                    record["status"], record["updated_at"] = "failed", utcnow().isoformat()
                    self.write(record)
                    recovered += 1
        return recovered
