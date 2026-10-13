"""SQLite command, checkpoint and budget ownership for the local research core."""
import hashlib
import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from shortlist.domain import (
    Profile,
    Research,
    Review,
    Source,
    new_id,
    read_research,
    utcnow,
)
from shortlist.fetch import domain_of


class Conflict(ValueError):
    pass


class BudgetExceeded(ValueError):
    pass


class Store:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, request_key TEXT UNIQUE NOT NULL, payload_hash TEXT NOT NULL,
                    profile TEXT NOT NULL, status TEXT NOT NULL, stage TEXT NOT NULL,
                    checkpoint TEXT NOT NULL DEFAULT '{}', error TEXT,
                    lease_until REAL NOT NULL DEFAULT 0, fence INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS records (
                    id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id),
                    domain TEXT NOT NULL, research TEXT NOT NULL, review TEXT,
                    UNIQUE(run_id, domain)
                );
                CREATE TABLE IF NOT EXISTS attempts (
                    id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id), provider TEXT NOT NULL,
                    kind TEXT NOT NULL, month TEXT NOT NULL, operation_key TEXT NOT NULL,
                    state TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(run_id, operation_key)
                );
                CREATE TABLE IF NOT EXISTS attempt_results (
                    attempt_id TEXT PRIMARY KEY REFERENCES attempts(id),
                    request_hash TEXT NOT NULL, payload TEXT
                );
                CREATE TABLE IF NOT EXISTS source_cache (
                    source_id TEXT PRIMARY KEY, requested_url TEXT NOT NULL, domain TEXT NOT NULL,
                    retrieved_epoch REAL NOT NULL, payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS source_cache_lookup ON source_cache(requested_url,domain,retrieved_epoch);
            """)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=20)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def cached_source(self, url: str, domain: str, max_age_hours: int, *, run_id: str, operation: str) -> Source | None:
        if max_age_hours == 0:
            return None
        now = utcnow().timestamp()
        with self.connection() as db:
            if db.execute("SELECT 1 FROM attempts WHERE run_id=? AND operation_key=?", (run_id, operation)).fetchone():
                return None  # Journal recovery/uncertainty takes precedence over cache reuse.
            row = db.execute("SELECT * FROM source_cache WHERE requested_url=? AND domain=? "
                             "AND retrieved_epoch BETWEEN ? AND ? ORDER BY retrieved_epoch DESC,rowid DESC LIMIT 1",
                             (url, domain, now - max_age_hours * 3600, now)).fetchone()
        if row is None:
            return None
        try:
            source = Source.model_validate_json(row["payload"])
            if source.id != row["source_id"] or source.company_domain != domain or domain_of(source.url) != domain or \
                    source.retrieved_at.timestamp() != row["retrieved_epoch"]:
                raise ValueError("Cached source identity changed")
            return source
        except ValueError as exc:
            raise Conflict("Cached source is corrupt; inspect operator storage") from exc

    def cache_source(self, run_id: str, fence: int, url: str, source: Source):
        if domain_of(url) != source.company_domain or domain_of(source.url) != source.company_domain:
            raise Conflict("Cached source URL must belong to its company")
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            self._assert_lease(db, run_id, fence)
            existing = db.execute("SELECT payload FROM source_cache WHERE source_id=?", (source.id,)).fetchone()
            if existing and existing["payload"] != source.model_dump_json():
                raise Conflict("Source snapshots cannot be changed")
            db.execute("INSERT OR IGNORE INTO source_cache VALUES (?,?,?,?,?)",
                       (source.id, url, source.company_domain, source.retrieved_at.timestamp(), source.model_dump_json()))

    def create_run(self, profile: Profile, request_key: str) -> str:
        # Confirmation ID/time are generated values, not part of the caller's command identity.
        payload = profile.model_dump(mode="json", exclude={"id", "confirmed_at"})
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT id,payload_hash FROM runs WHERE request_key=?", (request_key,)).fetchone()
            if existing:
                if existing["payload_hash"] != digest:
                    raise Conflict("Request key was already used for different inputs")
                return existing["id"]
            run_id = new_id()
            now = utcnow().isoformat()
            db.execute("INSERT INTO runs(id,request_key,payload_hash,profile,status,stage,created_at,updated_at) "
                       "VALUES (?,?,?,?,?,?,?,?)", (run_id, request_key, digest, profile.model_dump_json(),
                                                   "queued", "discovery", now, now))
            return run_id

    def get_run(self, run_id: str) -> dict:
        with self.connection() as db:
            row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            if not row:
                raise KeyError(run_id)
            result = dict(row)
            result["profile"] = json.loads(result["profile"])
            result["checkpoint"] = json.loads(result["checkpoint"])
            result["records"] = [{"research": json.loads(r["research"]),
                                  "review": json.loads(r["review"]) if r["review"] else None}
                                 for r in db.execute("SELECT research,review FROM records WHERE run_id=? ORDER BY rowid", (run_id,))]
            if result["profile"]:
                profile = Profile.model_validate(result["profile"])
                for item in result["records"]:
                    item["research"] = read_research(profile, item["research"]).model_dump(mode="json")
            result["attempts"] = [dict(a) for a in db.execute(
                "SELECT provider,kind,state,created_at FROM attempts WHERE run_id=? ORDER BY created_at,id", (run_id,))]
            return result

    def list_runs(self) -> list[dict]:
        with self.connection() as db:
            return [dict(row) for row in db.execute(
                "SELECT id,status,stage,created_at,updated_at,error FROM runs ORDER BY created_at DESC,rowid DESC LIMIT 100")]

    def pending_runs(self) -> list[str]:
        with self.connection() as db:
            return [row["id"] for row in db.execute(
                "SELECT id FROM runs WHERE status IN ('queued','running') AND lease_until<=? "
                "ORDER BY created_at,rowid LIMIT 50", (time.time(),))]

    def create_draft(self, seller_url: str, request_key: str) -> str:
        digest = hashlib.sha256(seller_url.encode()).hexdigest()
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT id,payload_hash FROM runs WHERE request_key=?", (request_key,)).fetchone()
            if row:
                if row["payload_hash"] != digest:
                    raise Conflict("Request key was already used for a different website")
                return row["id"]
            run_id = new_id()
            now = utcnow().isoformat()
            db.execute("INSERT INTO runs(id,request_key,payload_hash,profile,status,stage,checkpoint,created_at,updated_at) "
                       "VALUES (?,?,?,?,?,?,?,?,?)", (run_id, request_key, digest, "{}", "queued", "seller",
                       json.dumps({"seller_url": seller_url}), now, now))
            return run_id

    def confirm_draft(self, run_id: str, profile: Profile):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            if not row:
                raise KeyError(run_id)
            existing = json.loads(row["profile"])
            payload = profile.model_dump(mode="json", exclude={"id", "confirmed_at"})
            if existing:
                previous = Profile.model_validate(existing).model_dump(mode="json", exclude={"id", "confirmed_at"})
                if previous != payload:
                    raise Conflict("Target was already confirmed; start a new run to change it")
                return
            checkpoint = json.loads(row["checkpoint"])
            if row["status"] != "awaiting_confirmation" or checkpoint["seller_url"] != profile.seller_url:
                raise Conflict("Seller draft is not ready for confirmation")
            db.execute("UPDATE runs SET profile=?,stage='discovery',status='queued',error=NULL,updated_at=? WHERE id=?",
                       (profile.model_dump_json(), utcnow().isoformat(), run_id))

    def claim(self, run_id: str, lease_seconds: int = 180) -> int | None:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            now = time.time()
            row = db.execute("SELECT status,lease_until,fence FROM runs WHERE id=?", (run_id,)).fetchone()
            if not row or row["status"] not in ("queued", "running") or row["lease_until"] > now:
                return None
            fence = row["fence"] + 1
            db.execute("UPDATE runs SET status='running',fence=?,lease_until=?,updated_at=? WHERE id=?",
                       (fence, now + lease_seconds, utcnow().isoformat(), run_id))
            return fence

    def _assert_lease(self, db, run_id: str, fence: int):
        if not db.execute("SELECT 1 FROM runs WHERE id=? AND fence=? AND lease_until>? AND status='running'",
                          (run_id, fence, time.time())).fetchone():
            raise Conflict("Worker lease expired or was replaced")

    def checkpoint(self, run_id: str, fence: int, stage: str, payload: dict,
                   status: str = "running", error: str | None = None):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            self._assert_lease(db, run_id, fence)
            db.execute("UPDATE runs SET stage=?,checkpoint=?,status=?,error=?,updated_at=?,lease_until=? WHERE id=?",
                       (stage, json.dumps(payload), status, error, utcnow().isoformat(),
                        time.time() + 180 if status == "running" else 0, run_id))

    def reserve(self, run_id: str, fence: int, provider: str, kind: str, operation_key: str,
                global_cap: int = 200, request_hash: str = "") -> str:
        caps = {"search": 4, "model": 8, "fetch": 21}
        month = utcnow().strftime("%Y-%m")
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            self._assert_lease(db, run_id, fence)
            if db.execute("SELECT 1 FROM attempts WHERE run_id=? AND operation_key=?", (run_id, operation_key)).fetchone():
                raise Conflict("Operation already dispatched; recover saved outcome or stop conservatively")
            used = db.execute("SELECT count(*) FROM attempts WHERE run_id=? AND kind=?", (run_id, kind)).fetchone()[0]
            if used >= caps[kind]:
                raise BudgetExceeded(f"Run {kind} attempt cap reached")
            if kind == "search":
                total = db.execute("SELECT count(*) FROM attempts WHERE provider=? AND kind='search' AND month=?",
                                   (provider, month)).fetchone()[0]
                if total >= global_cap:
                    raise BudgetExceeded("Global monthly search cap reached")
            attempt_id = new_id()
            db.execute("INSERT INTO attempts VALUES (?,?,?,?,?,?,?,?)",
                       (attempt_id, run_id, provider, kind, month, operation_key, "outcome_unknown", utcnow().isoformat()))
            db.execute("INSERT INTO attempt_results(attempt_id,request_hash) VALUES (?,?)", (attempt_id, request_hash))
            return attempt_id

    def restore(self, run_id: str, fence: int, provider: str, kind: str, operation_key: str,
                request_hash: str) -> dict | None:
        with self.connection() as db:
            self._assert_lease(db, run_id, fence)
            row = db.execute("SELECT a.state,a.provider,a.kind,r.request_hash,r.payload FROM attempts a "
                             "LEFT JOIN attempt_results r ON r.attempt_id=a.id "
                             "WHERE a.run_id=? AND a.operation_key=?", (run_id, operation_key)).fetchone()
            if not row:
                return None
            if row["request_hash"] is None:
                raise Conflict("Legacy attempt has no recoverable result; automatic redispatch stopped")
            if row["request_hash"] != request_hash or row["provider"] != provider or row["kind"] != kind:
                raise Conflict("Saved operation inputs or provider changed; start a new run")
            if row["state"] == "outcome_unknown" or row["payload"] is None:
                raise Conflict("Provider outcome is uncertain; automatic redispatch stopped to protect allowance")
            try:
                payload = json.loads(row["payload"])
            except ValueError as exc:
                raise Conflict("Saved provider result is corrupt; inspect or start a new run") from exc
            return {"state": row["state"], "payload": payload}

    def outcome(self, attempt_id: str, state: str, *, run_id: str, fence: int, payload: dict | list | None = None):
        if state not in ("succeeded", "failed"):
            raise ValueError("Invalid provider outcome")
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            self._assert_lease(db, run_id, fence)
            changed = db.execute("UPDATE attempts SET state=? WHERE id=? AND run_id=? AND state='outcome_unknown'",
                                 (state, attempt_id, run_id)).rowcount
            if not changed:
                raise Conflict("Provider outcome is already final or belongs to another run")
            # State and result are one transaction: a crash cannot expose success
            # without its replayable value. No provider bodies or credentials here.
            if not db.execute("UPDATE attempt_results SET payload=? WHERE attempt_id=?",
                              (json.dumps(payload) if payload is not None else None, attempt_id)).rowcount:
                raise Conflict("Provider attempt has no result journal")

    def save_record(self, run_id: str, fence: int, record: Research):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            self._assert_lease(db, run_id, fence)
            # A completed record is immutable; retried checkpoints preserve review decisions.
            db.execute("INSERT INTO records(id,run_id,domain,research) VALUES (?,?,?,?) ON CONFLICT(run_id,domain) DO NOTHING",
                       (record.id, run_id, record.domain, record.model_dump_json()))

    def review(self, run_id: str, record_id: str, decision: Review):
        with self.connection() as db:
            changed = db.execute("UPDATE records SET review=? WHERE id=? AND run_id=?",
                                 (decision.model_dump_json(), record_id, run_id)).rowcount
            if not changed:
                raise KeyError(record_id)
