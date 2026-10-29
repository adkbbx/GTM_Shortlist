"""A small storage interface for agent runs, with a local SQLite implementation in a new agent_runs table.

The table lives beside the existing research tables in the same local database file and shares nothing with them.
Hosted Postgres storage is a documented follow-up (HACKATHON.md); the API registers agent routes in local mode only.
"""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from threading import Lock
from typing import Protocol

from shortlist.agent.models import AgentEvent, RunResult
from shortlist.domain import utcnow

MAX_EVENTS = 1000


class AgentRunStore(Protocol):
    def create(self, result: RunResult) -> None: ...

    def save(self, result: RunResult) -> None: ...

    def append_event(self, run_id: str, event: AgentEvent) -> None: ...

    def get(self, run_id: str) -> dict: ...

    def events(self, run_id: str, after: int = 0) -> tuple[str, list[AgentEvent]]: ...

    def list(self, limit: int = 20) -> list[dict]: ...


class SQLiteAgentRuns:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = Lock()
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS agent_runs (
                id TEXT PRIMARY KEY, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, status TEXT NOT NULL,
                website TEXT NOT NULL, payload TEXT NOT NULL, events TEXT NOT NULL DEFAULT '[]')""")

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=20)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def create(self, result: RunResult) -> None:
        now = utcnow().isoformat()
        with self.lock, self.connection() as db:
            db.execute("INSERT INTO agent_runs(id,created_at,updated_at,status,website,payload,events) VALUES (?,?,?,?,?,?,?)",
                       (result.id, result.created_at.isoformat(), now, result.status, result.website,
                        result.model_dump_json(), "[]"))

    def save(self, result: RunResult) -> None:
        with self.lock, self.connection() as db:
            updated = db.execute("UPDATE agent_runs SET payload=?, status=?, updated_at=? WHERE id=?",
                                 (result.model_dump_json(), result.status, utcnow().isoformat(), result.id)).rowcount
            if not updated:
                db.execute("INSERT INTO agent_runs(id,created_at,updated_at,status,website,payload,events) "
                           "VALUES (?,?,?,?,?,?,?)", (result.id, result.created_at.isoformat(), utcnow().isoformat(),
                                                      result.status, result.website, result.model_dump_json(), "[]"))

    def set_status(self, run_id: str, status: str) -> None:
        with self.lock, self.connection() as db:
            row = db.execute("SELECT payload FROM agent_runs WHERE id=?", (run_id,)).fetchone()
            if row is None:
                raise KeyError(run_id)
            payload = json.loads(row["payload"])
            payload["status"] = status
            db.execute("UPDATE agent_runs SET payload=?, status=?, updated_at=? WHERE id=?",
                       (json.dumps(payload), status, utcnow().isoformat(), run_id))

    def append_event(self, run_id: str, event: AgentEvent) -> None:
        with self.lock, self.connection() as db:
            row = db.execute("SELECT events FROM agent_runs WHERE id=?", (run_id,)).fetchone()
            if row is None:
                return
            events = json.loads(row["events"])
            event = event.model_copy(update={"seq": (events[-1]["seq"] if events else 0) + 1})
            events = (events + [event.model_dump(mode="json")])[-MAX_EVENTS:]
            db.execute("UPDATE agent_runs SET events=? WHERE id=?", (json.dumps(events), run_id))

    def get(self, run_id: str) -> dict:
        with self.connection() as db:
            row = db.execute("SELECT * FROM agent_runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(run_id)
        return {"id": row["id"], "status": row["status"], "created_at": row["created_at"],
                "updated_at": row["updated_at"], "result": RunResult.model_validate_json(row["payload"]),
                "events": [AgentEvent.model_validate(e) for e in json.loads(row["events"])]}

    def events(self, run_id: str, after: int = 0) -> tuple[str, list[AgentEvent]]:
        with self.connection() as db:
            row = db.execute("SELECT status, events FROM agent_runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(run_id)
        return row["status"], [AgentEvent.model_validate(e) for e in json.loads(row["events"]) if e["seq"] > after]

    def list(self, limit: int = 20) -> list[dict]:
        with self.connection() as db:
            rows = db.execute("SELECT id, created_at, status, website, payload FROM agent_runs "
                              "ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        summaries = []
        for row in rows:
            payload = json.loads(row["payload"])
            counts = {kind: 0 for kind in ("shortlisted", "needs_look", "rejected")}
            for company in payload.get("companies", []):
                kind = (company.get("verdict") or {}).get("kind")
                if kind in counts:
                    counts[kind] += 1
            summaries.append({"id": row["id"], "created_at": row["created_at"], "status": row["status"],
                              "website": row["website"], "synthetic": bool(payload.get("synthetic")), **counts})
        return summaries
