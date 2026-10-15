"""SQLite command, checkpoint and budget ownership for the local research core."""
import hashlib
import json
import sqlite3
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from shortlist.domain import (
    OperatorReview,
    OperatorReviewCommand,
    Profile,
    Research,
    Review,
    Source,
    new_id,
    read_research,
    utcnow,
)
from shortlist.email_drafts import EditEmailDraft, EmailDraft, StartEmailDraft, starting_draft
from shortlist.fetch import domain_of
from shortlist.progress import ProgressUpdate


class Conflict(ValueError):
    pass


class BudgetExceeded(ValueError):
    pass


class Store:
    order_key = "rowid"
    operator_access = True

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
                CREATE TABLE IF NOT EXISTS run_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
                    phase TEXT NOT NULL, label TEXT NOT NULL, state TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS worker_heartbeats (
                    id TEXT PRIMARY KEY, expires_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS booking_clicks (
                    id TEXT PRIMARY KEY,run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
                    request_key TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(run_id,request_key)
                );
                CREATE UNIQUE INDEX IF NOT EXISTS records_run_identity ON records(id,run_id);
                CREATE TABLE IF NOT EXISTS operator_reviews (
                    id TEXT PRIMARY KEY, run_id TEXT NOT NULL, record_id TEXT NOT NULL,
                    request_key TEXT NOT NULL, command_hash TEXT NOT NULL, payload TEXT NOT NULL,
                    UNIQUE(run_id,record_id,request_key),
                    FOREIGN KEY(record_id,run_id) REFERENCES records(id,run_id) ON DELETE CASCADE
                );
            """)
            if "detail" not in {row["name"] for row in db.execute("PRAGMA table_info(run_events)")}:
                db.execute("ALTER TABLE run_events ADD COLUMN detail TEXT")
            if "deleted_at" not in {row["name"] for row in db.execute("PRAGMA table_info(runs)")}:
                db.execute("ALTER TABLE runs ADD COLUMN deleted_at TEXT")
            if "email_draft" not in {row["name"] for row in db.execute("PRAGMA table_info(records)")}:
                db.execute("ALTER TABLE records ADD COLUMN email_draft TEXT")

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

    def begin(self, db):
        db.execute("BEGIN IMMEDIATE")

    def reserve_run(self, db, run_id: str, *, draft: bool = False):
        """Local operators have no demo restriction; hosted storage owns its grant."""

    def created_run(self, db, run_id: str):
        """Hosted confirmed runs reserve their research allowance atomically."""

    def reserve_batch(self, db, run_id: str, quantity: int) -> bool:
        return False

    def delivered(self, db, run_id: str, record: Research, billable: bool):
        """Local research does not debit a hosted wallet."""

    def finished(self, db, run_id: str):
        """Hosted terminal outcomes settle held credits."""

    def event(self, run_id: str, fence: int, update: ProgressUpdate):
        with self.connection() as db:
            self.begin(db)
            self._assert_lease(db, run_id, fence)
            db.execute("INSERT INTO run_events(run_id,phase,label,state,detail,created_at) VALUES (?,?,?,?,?,?)",
                       (run_id, update.phase, update.label, update.state, update.detail, utcnow().isoformat()))

    def worker_heartbeat(self, worker_id: str):
        with self.connection() as db:
            db.execute("INSERT INTO worker_heartbeats(id,expires_at) VALUES (?,?) "
                       "ON CONFLICT(id) DO UPDATE SET expires_at=excluded.expires_at", (worker_id, time.time() + 20))

    def worker_online(self) -> bool:
        with self.connection() as db:
            return bool(db.execute("SELECT 1 FROM worker_heartbeats WHERE expires_at>? LIMIT 1", (time.time(),)).fetchone())

    def remove_worker(self, worker_id: str):
        with self.connection() as db:
            db.execute("DELETE FROM worker_heartbeats WHERE id=?", (worker_id,))

    def reserve_global_search(self, db, provider: str, month: str, cap: int):
        total = db.execute("SELECT count(*) FROM attempts WHERE provider=? AND kind='search' AND month=?",
                           (provider, month)).fetchone()[0]
        if total >= cap:
            raise BudgetExceeded("Global monthly search cap reached")

    def cached_source(self, url: str, domain: str, max_age_hours: int, *, run_id: str, operation: str) -> Source | None:
        if max_age_hours == 0:
            return None
        now = utcnow().timestamp()
        with self.connection() as db:
            if db.execute("SELECT 1 FROM attempts WHERE run_id=? AND operation_key=?", (run_id, operation)).fetchone():
                return None  # Journal recovery/uncertainty takes precedence over cache reuse.
            row = db.execute("SELECT * FROM source_cache WHERE requested_url=? AND domain=? "
                             f"AND retrieved_epoch BETWEEN ? AND ? ORDER BY retrieved_epoch DESC,{self.order_key} DESC LIMIT 1",
                             (url, domain, now - max_age_hours * 3600, now)).fetchone()
        if row is None:
            return None
        try:
            source = Source.model_validate_json(row["payload"])
            if source.id != row["source_id"] or source.company_domain != domain or domain_of(source.url) != domain or \
                    source.retrieved_at.timestamp() != row["retrieved_epoch"]:
                raise ValueError("Cached source identity changed")
            if "research_links" not in json.loads(row["payload"]):
                return None  # Older snapshots cannot prove which follow-up links were observed.
            return source
        except ValueError as exc:
            raise Conflict("Cached source is corrupt; inspect operator storage") from exc

    def cache_source(self, run_id: str, fence: int, url: str, source: Source):
        if domain_of(url) != source.company_domain or domain_of(source.url) != source.company_domain:
            raise Conflict("Cached source URL must belong to its company")
        with self.connection() as db:
            self.begin(db)
            self._assert_lease(db, run_id, fence)
            existing = db.execute("SELECT payload FROM source_cache WHERE source_id=?", (source.id,)).fetchone()
            if existing and existing["payload"] != source.model_dump_json():
                raise Conflict("Source snapshots cannot be changed")
            db.execute("INSERT INTO source_cache(source_id,requested_url,domain,retrieved_epoch,payload) VALUES (?,?,?,?,?) "
                       "ON CONFLICT(source_id) DO NOTHING",
                       (source.id, url, source.company_domain, source.retrieved_at.timestamp(), source.model_dump_json()))

    def create_run(self, profile: Profile, request_key: str) -> str:
        # Confirmation ID/time are generated values, not part of the caller's command identity.
        payload = profile.model_dump(mode="json", exclude={"id", "confirmed_at"})
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        with self.connection() as db:
            self.begin(db)
            existing = db.execute("SELECT id,payload_hash,deleted_at FROM runs WHERE request_key=?", (request_key,)).fetchone()
            if existing:
                if existing["deleted_at"]:
                    raise Conflict("This request was deleted. Start a new shortlist")
                if existing["payload_hash"] != digest:
                    raise Conflict("Request key was already used for different inputs")
                return existing["id"]
            run_id = new_id()
            self.reserve_run(db, run_id)
            now = utcnow().isoformat()
            db.execute("INSERT INTO runs(id,request_key,payload_hash,profile,status,stage,created_at,updated_at) "
                       "VALUES (?,?,?,?,?,?,?,?)", (run_id, request_key, digest, profile.model_dump_json(),
                                                   "queued", "discovery", now, now))
            self.created_run(db, run_id)
            return run_id

    def get_run(self, run_id: str) -> dict:
        with self.connection() as db:
            row = db.execute("SELECT * FROM runs WHERE id=? AND deleted_at IS NULL", (run_id,)).fetchone()
            if not row:
                raise KeyError(run_id)
            result = dict(row)
            result["profile"] = json.loads(result["profile"])
            result["checkpoint"] = json.loads(result["checkpoint"])
            result["records"] = [{"research": json.loads(r["research"]),
                                  "review": json.loads(r["review"]) if r["review"] else None,
                                  "email_draft": json.loads(r["email_draft"])["draft"] if r["email_draft"] else None,
                                  "operator_review": self._latest_operator_review(db, run_id, r["id"])}
                                 for r in db.execute(f"SELECT id,research,review,email_draft FROM records WHERE run_id=? ORDER BY {self.order_key}", (run_id,))]
            if result["profile"]:
                profile = Profile.model_validate(result["profile"])
                for item in result["records"]:
                    item["research"] = read_research(profile, item["research"]).model_dump(mode="json")
            result["attempts"] = [dict(a) for a in db.execute(
                "SELECT provider,kind,state,created_at FROM attempts WHERE run_id=? ORDER BY created_at,id", (run_id,))]
            result["events"] = [dict(e) for e in db.execute(
                "SELECT * FROM (SELECT id,phase,label,state,detail,created_at FROM run_events WHERE run_id=? "
                "ORDER BY id DESC LIMIT 100) recent ORDER BY id", (run_id,))]
            return result

    def _operator_history(self, db, run_id: str, record_id: str, limit: int = 100) -> list[dict]:
        return [OperatorReview.model_validate_json(row["payload"]).model_dump(mode="json") for row in db.execute(
            f"SELECT payload FROM operator_reviews WHERE run_id=? AND record_id=? ORDER BY {self.order_key} DESC LIMIT ?",
            (run_id, record_id, limit))]

    def _latest_operator_review(self, db, run_id: str, record_id: str) -> dict | None:
        history = self._operator_history(db, run_id, record_id, limit=1)
        return history[0] if history else None

    def operator_history(self, run_id: str, record_id: str) -> list[dict]:
        with self.connection() as db:
            if not db.execute("SELECT id FROM records WHERE run_id=? AND id=?", (run_id, record_id)).fetchone():
                raise KeyError(record_id)
            return self._operator_history(db, run_id, record_id)

    def annotate(self, command: OperatorReviewCommand) -> dict:
        if not self.operator_access:
            raise ValueError("Operator annotations require the separate scoped worker credential")
        digest = hashlib.sha256(json.dumps(command.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()
        with self.connection() as db:
            self.begin(db)
            record = db.execute("SELECT research FROM records WHERE id=? AND run_id=?",
                                (command.record_id, command.run_id)).fetchone()
            if record is None:
                raise KeyError(command.record_id)
            run = db.execute("SELECT status,deleted_at FROM runs WHERE id=?", (command.run_id,)).fetchone()
            if run is None or run["deleted_at"]:
                raise KeyError(command.run_id)
            if run["status"] not in ("ready", "partial"):
                raise Conflict("Wait for research to finish before recording an operator review")
            replay = db.execute("SELECT command_hash,payload FROM operator_reviews WHERE run_id=? AND record_id=? AND request_key=?",
                                (command.run_id, command.record_id, command.request_key)).fetchone()
            if replay:
                if replay["command_hash"] != digest:
                    raise Conflict("Review request key was already used for different inputs")
                return OperatorReview.model_validate_json(replay["payload"]).model_dump(mode="json")
            history = self._operator_history(db, command.run_id, command.record_id)
            previous = history[0]["id"] if history else None
            if command.previous_id != previous:
                raise Conflict("Operator review changed. Read the latest history before adding a note")
            if len(history) >= 100:
                raise BudgetExceeded("This sheet has reached its 100 operator-note limit")
            sources = {source["id"] for source in json.loads(record["research"])["sources"]}
            if not set(command.annotation.source_ids) <= sources:
                raise ValueError("Operator review references a source outside this saved sheet")
            review = OperatorReview(annotation=command.annotation,
                                    research_hash=hashlib.sha256(record["research"].encode()).hexdigest())
            db.execute("INSERT INTO operator_reviews(id,run_id,record_id,request_key,command_hash,payload) VALUES (?,?,?,?,?,?)",
                       (review.id, command.run_id, command.record_id, command.request_key, digest, review.model_dump_json()))
            return review.model_dump(mode="json")

    def list_runs(self) -> list[dict]:
        with self.connection() as db:
            return [dict(row) for row in db.execute(
                f"SELECT id,status,stage,created_at,updated_at,error FROM runs WHERE deleted_at IS NULL ORDER BY created_at DESC,{self.order_key} DESC LIMIT 100")]

    def clear_source_cache(self, db):
        db.execute("DELETE FROM source_cache")

    def retention_candidates(self, cutoff: datetime) -> list[str]:
        if cutoff.tzinfo is None:
            raise ValueError("Retention cutoff must include a timezone")
        with self.connection() as db:
            return [row["id"] for row in db.execute(
                "SELECT id FROM runs WHERE deleted_at IS NULL "
                "AND status IN ('ready','partial','awaiting_confirmation') AND updated_at<? "
                f"ORDER BY updated_at,{self.order_key} LIMIT 100",
                (cutoff.astimezone(UTC).isoformat(),))]

    def delete_run(self, run_id: str) -> bool:
        """Erase research content; retain minimal command/spending identities."""
        with self.connection() as db:
            self.begin(db)
            row = db.execute("SELECT status,deleted_at FROM runs WHERE id=?", (run_id,)).fetchone()
            if not row:
                raise KeyError(run_id)
            if row["deleted_at"]:
                return False
            if row["status"] in ("queued", "running"):
                raise Conflict("Wait for research to finish before deleting this shortlist")
            self.finished(db, run_id)
            db.execute("DELETE FROM records WHERE run_id=?", (run_id,))
            db.execute("DELETE FROM run_events WHERE run_id=?", (run_id,))
            db.execute("DELETE FROM booking_clicks WHERE run_id=?", (run_id,))
            db.execute("UPDATE attempt_results SET payload=NULL,request_hash='' "
                       "WHERE attempt_id IN (SELECT id FROM attempts WHERE run_id=?)", (run_id,))
            db.execute("UPDATE attempts SET operation_key=id WHERE run_id=?", (run_id,))
            self.clear_source_cache(db)
            now = utcnow().isoformat()
            db.execute("UPDATE runs SET profile='{}',checkpoint='{}',payload_hash='',error=NULL,stage='deleted',"
                       "status='partial',deleted_at=?,updated_at=?,lease_until=0,fence=fence+1 WHERE id=?",
                       (now, now, run_id))
            return True

    def stop_run(self, run_id: str):
        with self.connection() as db:
            self.begin(db)
            row = db.execute("SELECT status,checkpoint,deleted_at FROM runs WHERE id=?", (run_id,)).fetchone()
            if row is None or row["deleted_at"]:
                raise KeyError(run_id)
            checkpoint = json.loads(row["checkpoint"])
            if checkpoint.get("termination") == "user_stopped":
                return
            if row["status"] not in ("queued", "running", "awaiting_confirmation"):
                raise Conflict("Research finished before it could be stopped. Review the saved results")
            now = utcnow().isoformat()
            checkpoint.update(termination="user_stopped", stopped_at=now)
            db.execute("UPDATE runs SET status='partial',stage='stopped',checkpoint=?,error='Research stopped at your request',"
                       "updated_at=?,lease_until=0,fence=fence+1 WHERE id=?", (json.dumps(checkpoint), now, run_id))
            db.execute("INSERT INTO run_events(run_id,phase,label,state,created_at) VALUES (?,?,?,?,?)",
                       (run_id, "review", "Stopped further research at your request", "succeeded", now))
            self.finished(db, run_id)

    def booking_click(self, run_id: str, request_key: str):
        """Record a link click only; never infer an appointment or buying intent."""
        with self.connection() as db:
            self.begin(db)
            row = db.execute("SELECT status,profile FROM runs WHERE id=? AND deleted_at IS NULL", (run_id,)).fetchone()
            if row is None:
                raise KeyError(run_id)
            if row["status"] not in ("ready", "partial") or row["profile"] == "{}" or not db.execute(
                "SELECT 1 FROM records WHERE run_id=? LIMIT 1", (run_id,)).fetchone():
                raise Conflict("Finish company research before requesting a setup call")
            if db.execute("SELECT 1 FROM booking_clicks WHERE run_id=? AND request_key=?", (run_id, request_key)).fetchone():
                return
            if db.execute("SELECT count(*) FROM booking_clicks WHERE created_at>=?",
                          (utcnow().date().isoformat(),)).fetchone()[0] >= 100:
                raise BudgetExceeded("Setup-call click allowance reached")
            db.execute("INSERT INTO booking_clicks(id,run_id,request_key,created_at) VALUES (?,?,?,?)",
                       (new_id(), run_id, request_key, utcnow().isoformat()))

    def pending_runs(self) -> list[str]:
        with self.connection() as db:
            return [row["id"] for row in db.execute(
                "SELECT id FROM runs WHERE status IN ('queued','running') AND lease_until<=? "
                f"ORDER BY created_at,{self.order_key} LIMIT 50", (time.time(),))]

    def create_draft(self, seller_url: str | None, request_key: str, *, company_name: str | None = None,
                     experience_version: int = 1) -> str:
        if experience_version not in (1, 2):
            raise ValueError("Unsupported research experience")
        if bool(seller_url) == bool(company_name):
            raise ValueError("Provide either a website or a company name")
        digest = hashlib.sha256((seller_url if seller_url else "company:" + company_name.casefold()).encode()).hexdigest()
        if experience_version == 2:
            digest = hashlib.sha256((digest + ":experience-2").encode()).hexdigest()
        with self.connection() as db:
            self.begin(db)
            row = db.execute("SELECT id,payload_hash,deleted_at FROM runs WHERE request_key=?", (request_key,)).fetchone()
            if row:
                if row["deleted_at"]:
                    raise Conflict("This request was deleted. Start a new shortlist")
                if row["payload_hash"] != digest:
                    raise Conflict("Request key was already used for a different website")
                return row["id"]
            run_id = new_id()
            self.reserve_run(db, run_id, draft=True)
            now = utcnow().isoformat()
            db.execute("INSERT INTO runs(id,request_key,payload_hash,profile,status,stage,checkpoint,created_at,updated_at) "
                       "VALUES (?,?,?,?,?,?,?,?,?)", (run_id, request_key, digest, "{}", "queued", "seller" if seller_url else "identity",
                       json.dumps({"seller_url": seller_url, "experience_version": experience_version,
                                   "seller_output_protocol": 2,
                                   **({"company_name": company_name} if company_name else {})}), now, now))
            return run_id

    def confirm_website(self, run_id: str, website_url: str):
        from shortlist.fetch import canonical_url
        website_url = canonical_url(website_url)
        with self.connection() as db:
            self.begin(db)
            row = db.execute("SELECT status,stage,checkpoint FROM runs WHERE id=? AND deleted_at IS NULL", (run_id,)).fetchone()
            if row is None:
                raise KeyError(run_id)
            checkpoint = json.loads(row["checkpoint"])
            if checkpoint.get("termination") == "user_stopped":
                raise Conflict("This research was stopped; start a new shortlist")
            if checkpoint["seller_url"] is not None:
                if checkpoint["seller_url"] == website_url:
                    return
                raise Conflict("Website already selected; start a new shortlist to change it")
            if row["status"] not in ("awaiting_confirmation", "partial") or row["stage"] not in ("website", "identity"):
                raise Conflict("Wait for website lookup before choosing your website")
            checkpoint["seller_url"] = website_url
            db.execute("UPDATE runs SET status='queued',stage='seller',checkpoint=?,error=NULL,updated_at=? WHERE id=?",
                       (json.dumps(checkpoint), utcnow().isoformat(), run_id))
            db.execute("INSERT INTO run_events(run_id,phase,label,state,created_at) VALUES (?,?,?,?,?)",
                       (run_id, "seller", "You confirmed the company website", "succeeded", utcnow().isoformat()))

    def reuse_draft(self, source_id: str, request_key: str) -> str:
        digest = hashlib.sha256(("reuse:" + source_id).encode()).hexdigest()
        with self.connection() as db:
            self.begin(db)
            previous = db.execute("SELECT id,payload_hash,deleted_at FROM runs WHERE request_key=?", (request_key,)).fetchone()
            if previous:
                if previous["deleted_at"] or previous["payload_hash"] != digest:
                    raise Conflict("Request key was deleted or used for a different offer")
                return previous["id"]
            source = db.execute("SELECT profile,status FROM runs WHERE id=? AND deleted_at IS NULL", (source_id,)).fetchone()
            if source is None:
                raise KeyError(source_id)
            if source["status"] not in ("ready", "partial") or not json.loads(source["profile"]):
                raise Conflict("Finish a confirmed shortlist before reusing its offer")
            profile = Profile.model_validate_json(source["profile"])
            identity = new_id()
            self.reserve_run(db, identity)  # Balance/one-active-run checks; no automated profiling.
            checkpoint = {"seller_url": profile.seller_url, "reused_offer": True,
                          "draft_exclusions": list(profile.exclusions), "draft": {
                              "offer": profile.offer, "target": profile.target,
                              "criteria": [item.model_dump(mode="json") for item in profile.criteria], "unknowns": []}}
            now = utcnow().isoformat()
            db.execute("INSERT INTO runs(id,request_key,payload_hash,profile,status,stage,checkpoint,created_at,updated_at) "
                       "VALUES (?,?,?,?,?,?,?,?,?)", (identity, request_key, digest, "{}", "awaiting_confirmation", "confirmation",
                                                      json.dumps(checkpoint), now, now))
            db.execute("INSERT INTO run_events(run_id,phase,label,state,created_at) VALUES (?,?,?,?,?)",
                       (identity, "confirmation", "Saved offer copied; review before starting a new batch", "waiting", now))
            return identity

    def confirm_draft(self, run_id: str, profile: Profile, company_limit: int = 3, campaign_name: str | None = None,
                      discovery_terms: str | None = None):
        with self.connection() as db:
            self.begin(db)
            row = db.execute("SELECT * FROM runs WHERE id=? AND deleted_at IS NULL", (run_id,)).fetchone()
            if not row:
                raise KeyError(run_id)
            existing = json.loads(row["profile"])
            payload = profile.model_dump(mode="json", exclude={"id", "confirmed_at"})
            if existing:
                previous = Profile.model_validate(existing).model_dump(mode="json", exclude={"id", "confirmed_at"})
                saved_checkpoint = json.loads(row["checkpoint"])
                if previous != payload or saved_checkpoint.get("company_limit", 3) != company_limit or \
                        saved_checkpoint.get("campaign_name") != campaign_name or saved_checkpoint.get("discovery_terms") != discovery_terms:
                    raise Conflict("Target was already confirmed; start a new run to change it")
                return
            checkpoint = json.loads(row["checkpoint"])
            if row["status"] != "awaiting_confirmation" or checkpoint["seller_url"] != profile.seller_url:
                raise Conflict("Seller draft is not ready for confirmation")
            checkpoint["company_limit"] = company_limit
            if checkpoint.get("experience_version") == 2:
                checkpoint["selection_policy"] = 3
            if discovery_terms is not None:
                checkpoint["discovery_terms"] = discovery_terms
            if campaign_name is not None:
                if campaign_name not in {c["name"] for c in checkpoint.get("market", {}).get("campaigns", [])}:
                    raise Conflict("Choose a campaign from this run or define a custom target")
                checkpoint["campaign_name"] = campaign_name
            if self.reserve_batch(db, run_id, company_limit):
                checkpoint["credit_policy"] = "company-v1"
            db.execute("UPDATE runs SET profile=?,checkpoint=?,stage='discovery',status='queued',error=NULL,updated_at=? WHERE id=?",
                       (profile.model_dump_json(), json.dumps(checkpoint), utcnow().isoformat(), run_id))

    def claim(self, run_id: str, lease_seconds: int = 180) -> int | None:
        with self.connection() as db:
            self.begin(db)
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
            self.begin(db)
            self._assert_lease(db, run_id, fence)
            db.execute("UPDATE runs SET stage=?,checkpoint=?,status=?,error=?,updated_at=?,lease_until=? WHERE id=?",
                       (stage, json.dumps(payload), status, error, utcnow().isoformat(),
                        time.time() + 180 if status == "running" else 0, run_id))
            if status in ("ready", "partial"):
                self.finished(db, run_id)

    def reserve(self, run_id: str, fence: int, provider: str, kind: str, operation_key: str,
                global_cap: int = 200, request_hash: str = "") -> str:
        caps = {"search": 4, "model": 8, "fetch": 21}
        month = utcnow().strftime("%Y-%m")
        with self.connection() as db:
            self.begin(db)
            self._assert_lease(db, run_id, fence)
            if db.execute("SELECT 1 FROM attempts WHERE run_id=? AND operation_key=?", (run_id, operation_key)).fetchone():
                raise Conflict("Operation already dispatched; recover saved outcome or stop conservatively")
            used = db.execute("SELECT count(*) FROM attempts WHERE run_id=? AND kind=?", (run_id, kind)).fetchone()[0]
            if used >= caps[kind]:
                raise BudgetExceeded(f"Run {kind} attempt cap reached")
            if kind == "search":
                self.reserve_global_search(db, provider, month, global_cap)
            attempt_id = new_id()
            db.execute("INSERT INTO attempts(id,run_id,provider,kind,month,operation_key,state,created_at) "
                       "VALUES (?,?,?,?,?,?,?,?)",
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
            self.begin(db)
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

    def save_record(self, run_id: str, fence: int, record: Research, *, billable: bool = True):
        with self.connection() as db:
            self.begin(db)
            self._assert_lease(db, run_id, fence)
            # A completed record is immutable; retried checkpoints preserve review decisions.
            changed = db.execute("INSERT INTO records(id,run_id,domain,research) VALUES (?,?,?,?) ON CONFLICT(run_id,domain) DO NOTHING",
                                 (record.id, run_id, record.domain, record.model_dump_json())).rowcount
            if changed:
                self.delivered(db, run_id, record, billable)

    def review(self, run_id: str, record_id: str, decision: Review):
        with self.connection() as db:
            changed = db.execute("UPDATE records SET review=? WHERE id=? AND run_id=?",
                                 (decision.model_dump_json(), record_id, run_id)).rowcount
            if not changed:
                raise KeyError(record_id)

    def write_email_draft(self, run_id: str, record_id: str, command: StartEmailDraft | EditEmailDraft):
        with self.connection() as db:
            self.begin(db)
            row = db.execute("SELECT r.research,r.email_draft,u.profile FROM records r JOIN runs u ON u.id=r.run_id "
                             "WHERE r.id=? AND r.run_id=? AND u.deleted_at IS NULL", (record_id, run_id)).fetchone()
            if row is None:
                raise KeyError(record_id)
            digest = hashlib.sha256((type(command).__name__ + command.model_dump_json()).encode()).hexdigest()
            saved = json.loads(row["email_draft"]) if row["email_draft"] else None
            if saved and saved["request_key"] == command.request_key:
                if saved["command_hash"] != digest:
                    raise Conflict("This draft request was already used with different content")
                return EmailDraft.model_validate(saved["draft"])
            current = EmailDraft.model_validate(saved["draft"]) if saved else None
            if command.previous_id != (current.id if current else None):
                raise Conflict("This draft changed elsewhere. Load the saved draft before saving again; keep a copy of your edits.")
            if isinstance(command, StartEmailDraft):
                profile = Profile.model_validate_json(row["profile"])
                research = read_research(profile, json.loads(row["research"]))
                try:
                    draft = starting_draft(profile, research, command.person_id)
                except ValueError as exc:
                    raise Conflict(str(exc)) from None
            else:
                draft = EmailDraft(subject=command.subject, body=command.body, person_id=current.person_id,
                                   basis=current.basis, created_at=current.created_at, edited=True)
            envelope = {"request_key": command.request_key, "command_hash": digest, "draft": draft.model_dump(mode="json")}
            db.execute("UPDATE records SET email_draft=? WHERE id=? AND run_id=?",
                       (json.dumps(envelope), record_id, run_id))
            return draft
