"""Postgres adapter for the shared command/journal core, scoped by database RLS."""

import hashlib
import json
import time
from contextlib import contextmanager
from uuid import UUID

import psycopg
from pydantic import SecretStr

from shortlist.auth import AuthenticationError
from shortlist.store import BudgetExceeded, Conflict, Store

ANONYMOUS_INTERRUPTED = "Drafting was interrupted. Sign in to continue; your research starts again from your website."


class Row(dict):
    """DB-API rows retain named fields and the core's positional aggregate access."""

    def __getitem__(self, key):
        return tuple(self.values())[key] if isinstance(key, int) else super().__getitem__(key)


def rows(cursor):
    names = [column.name for column in cursor.description] if cursor.description else []
    return lambda values: Row(zip(names, values, strict=True))


class Connection:
    def __init__(self, database):
        self.database = database

    def execute(self, statement: str, parameters=()):
        # Only the core's static SQL crosses this adapter; values remain driver-bound.
        # This is the DB-API parameter-style conversion, not a SQL query rewriter.
        return self.database.execute(statement.replace("?", "%s"), parameters)


class PostgresStore(Store):
    order_key = "position"

    def __init__(self, dsn: SecretStr, workspace_id: UUID | None, *, worker: bool = False, maintenance: bool = False,
                 anonymous: bool = False):
        if workspace_id is None and not worker and not anonymous:
            raise ValueError("Hosted access requires a verified workspace")
        if maintenance and (not worker or workspace_id is None):
            raise ValueError("Account maintenance requires an explicitly scoped worker credential")
        if anonymous and (worker or workspace_id is not None):
            raise ValueError("Drafts before signup use the API credential without a workspace")
        self.dsn = dsn
        self.workspace_id = workspace_id
        self.worker = worker
        self.operator_access = worker and workspace_id is not None
        self.maintenance = maintenance

    @contextmanager
    def connection(self):
        with psycopg.connect(self.dsn.get_secret_value(), connect_timeout=5, row_factory=rows) as db:
            privilege = db.execute(
                "SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=session_user"
            ).fetchone()
            if privilege["rolsuper"] or privilege["rolbypassrls"]:
                raise ValueError("Hosted runtime credentials must not bypass row security")
            db.execute("SET LOCAL ROLE shortlist_worker" if self.worker else "SET LOCAL ROLE shortlist_api")
            db.execute("SET LOCAL search_path TO shortlist,pg_catalog")
            db.execute("SET LOCAL statement_timeout TO '10s'")
            db.execute("SET LOCAL lock_timeout TO '5s'")
            db.execute(
                # Preserve exact float8 timestamps when session defaults round text output.
                "SELECT set_config('shortlist.workspace_id',%s,true) AS workspace,"
                "set_config('extra_float_digits','3',true) AS float_digits",
                (str(self.workspace_id) if self.workspace_id else "",),
            )
            connection = Connection(db)
            self.require_open_workspace(connection)
            yield connection

    def require_open_workspace(self, db):
        if self.workspace_id is None or self.maintenance:
            return
        workspace = db.execute("SELECT closure_state FROM workspaces WHERE id=?", (self.workspace_id,)).fetchone()
        if workspace and workspace["closure_state"] != "open":
            raise AuthenticationError("This account is closing or closed. Contact the service operator")

    def begin(self, db):
        # Short command transactions serialize global quotas/idempotent commands.
        # Provider dispatch is outside this transaction. The lock is database-wide.
        db.execute("SELECT pg_advisory_xact_lock(7421391)")
        self.require_open_workspace(db)

    def ensure_workspace(self):
        if self.workspace_id is None:
            raise ValueError("Workspace creation requires a verified owner")
        with self.connection() as db:
            self.begin(db)
            db.execute(
                "INSERT INTO workspaces(id) VALUES (?) ON CONFLICT(id) DO NOTHING", (self.workspace_id,)
            )

    def for_run(self, run_id: str):
        if not self.worker:
            raise ValueError("Only the worker can select a run workspace")
        with self.connection() as db:
            row = db.execute("SELECT workspace_id FROM runs WHERE id=?", (run_id,)).fetchone()
            if row is None:
                raise KeyError(run_id)
        return PostgresStore(self.dsn, row["workspace_id"], worker=True)

    def reserve_run(self, db, run_id: str, *, draft: bool = False):
        from shortlist.credits import CreditWallet

        if CreditWallet(self)._balance(db).available < 1:
            raise BudgetExceeded("No research credits available. Open saved research or add credits")
        if db.execute(
            "SELECT 1 FROM runs WHERE workspace_id=? AND status IN ('queued','running','awaiting_confirmation')",
            (self.workspace_id,),
        ).fetchone():
            raise BudgetExceeded("Finish or reopen your current shortlist before starting another")
        if draft:
            paid = bool(
                db.execute(
                    "SELECT 1 FROM credit_entries WHERE workspace_id=? AND kind='purchase' LIMIT 1",
                    (self.workspace_id,),
                ).fetchone()
            )
            changed = db.execute(
                "UPDATE workspaces SET free_profiles=free_profiles+1,profile_day=CURRENT_DATE,"
                "daily_profiles=CASE WHEN profile_day=CURRENT_DATE THEN daily_profiles+1 ELSE 1 END "
                "WHERE id=? AND (free_profiles<3 OR ?) "
                "AND (profile_day<>CURRENT_DATE OR daily_profiles<10) RETURNING id",
                (self.workspace_id, paid),
            ).fetchone()
            if changed is None:
                raise BudgetExceeded(
                    "Seller profiling allowance reached. Reuse your saved offer or try later"
                )

    def resume_batch(self, db, run_id: str, quantity: int):
        from shortlist.credits import CreditWallet

        if CreditWallet(self)._balance(db).available < quantity:
            raise BudgetExceeded("Not enough research credits to continue this batch")
        row = db.execute("UPDATE credit_reservations SET state='held' WHERE run_id=? AND workspace_id=? "
                         "AND state='released' AND consumed=0 AND requested=? RETURNING run_id",
                         (run_id, self.workspace_id, quantity)).fetchone()
        if row is None:
            raise Conflict("Only an unused, released batch reservation can be continued")

    def created_run(self, db, run_id: str):
        self.reserve_batch(db, run_id, 3)
        db.execute(
            "UPDATE runs SET checkpoint=? WHERE id=?",
            (json.dumps({"company_limit": 3, "credit_policy": "company-v1"}), run_id),
        )

    def reserve_batch(self, db, run_id: str, quantity: int) -> bool:
        if db.execute("SELECT legacy_credit_exempt FROM runs WHERE id=?", (run_id,)).fetchone()[0]:
            return False
        from shortlist.credits import CreditWallet

        CreditWallet(self).reserve_in_transaction(db, run_id, quantity)
        return True

    def delivered(self, db, run_id, record, billable):
        if (
            billable
            and db.execute(
                "SELECT 1 FROM credit_reservations WHERE run_id=? AND workspace_id=?",
                (run_id, self.workspace_id),
            ).fetchone()
        ):
            from shortlist.credits import CreditWallet

            CreditWallet(self).consume_in_transaction(db, run_id, record.domain)

    def finished(self, db, run_id):
        if db.execute(
            "SELECT 1 FROM credit_reservations WHERE run_id=? AND workspace_id=?", (run_id, self.workspace_id)
        ).fetchone():
            from shortlist.credits import CreditWallet

            CreditWallet(self).settle_in_transaction(db, run_id)

    def get_run(self, run_id):
        run = super().get_run(run_id)
        with self.connection() as db:
            held = db.execute(
                "SELECT requested,consumed,state FROM credit_reservations WHERE run_id=? AND workspace_id=?",
                (run_id, run["workspace_id"]),
            ).fetchone()
            if held:
                outstanding = held["requested"] - held["consumed"]
                run["credits"] = {
                    "maximum": held["requested"],
                    "used": held["consumed"],
                    "reserved": outstanding if held["state"] == "held" else 0,
                    "returned": 0 if held["state"] == "held" else outstanding,
                }
                for record in run["records"]:
                    record["credits_used"] = int(
                        bool(
                            db.execute(
                                "SELECT 1 FROM credit_entries WHERE workspace_id=? AND operation_key=?",
                                (
                                    run["workspace_id"],
                                    "delivery:" + run_id + ":" + record["research"]["domain"],
                                ),
                            ).fetchone()
                        )
                    )
        return run

    def workspace_scope(self, table: str) -> tuple[str, tuple]:
        # The worker role can read every workspace; another account's research must never shape this run.
        if self.workspace_id is None:
            raise ValueError("Workspace-scoped reads need an assigned workspace")
        return f" AND {table}.workspace_id=?", (self.workspace_id,)

    def clear_source_cache(self, db):
        if self.workspace_id is None:
            raise ValueError("Research deletion requires an assigned workspace")
        db.execute("DELETE FROM source_cache WHERE workspace_id=?", (self.workspace_id,))

    def reserve_global_search(self, db, provider: str, month: str, cap: int):
        if not db.execute("SELECT reserve_search_quota(?,?,?)", (provider, month, cap)).fetchone()[0]:
            raise BudgetExceeded("Global monthly search cap reached")

    # Drafts before signup. The API role reaches them only through the claim-scoped functions in migration 011.

    def create_anonymous_draft(self, draft_id: UUID, claim_hash: str, website: str, visitors: list[str],
                               daily_cap: int) -> str:
        with self.connection() as db:
            self.begin(db)
            return db.execute("SELECT create_anonymous_draft(?,?,?,?,?) AS outcome",
                              (draft_id, claim_hash, website, visitors, daily_cap)).fetchone()["outcome"]

    def read_anonymous_draft(self, draft_id: UUID, claim_hash: str) -> dict | None:
        with self.connection() as db:
            row = db.execute("SELECT * FROM read_anonymous_draft(?,?)", (draft_id, claim_hash)).fetchone()
        return dict(row) if row else None

    def claim_anonymous_draft(self, draft_id: UUID, claim_hash: str, request_key: str) -> str:
        """The signed-in owner's run from a draft. Removing the draft and creating the run share one transaction, so a
        refused credit or allowance check leaves the draft in place to claim later."""
        if self.workspace_id is None or self.worker:
            raise ValueError("Claiming a draft requires the signed-in owner's workspace")
        with self.connection() as db:
            self.begin(db)
            replay = db.execute("SELECT id FROM runs WHERE request_key=? AND deleted_at IS NULL", (request_key,)).fetchone()
            if replay:
                return replay["id"]
            saved = db.execute("SELECT * FROM read_anonymous_draft(?,?)", (draft_id, claim_hash)).fetchone()
            if saved is None:
                raise KeyError(str(draft_id))
            if saved["status"] in ("queued", "running"):
                raise Conflict("Your draft is still being written. Try again in a moment")
            taken = db.execute("SELECT * FROM take_anonymous_draft(?,?)", (draft_id, claim_hash)).fetchone()
            if taken is None:
                raise KeyError(str(draft_id))
            # A ready draft skips the page fetch and model call; the worker then explores the market as usual.
            seed = {"claimed_draft": True}
            if taken["source"]:
                seed["seller_source"] = json.loads(taken["source"])
            if taken["status"] == "ready" and taken["draft"]:
                seed["draft"] = json.loads(taken["draft"])
            digest = hashlib.sha256(("claimed-draft:" + taken["website"]).encode()).hexdigest()
            return self.insert_draft(db, taken["website"], request_key, digest, 2, seed)

    def anonymous_drafts_available(self) -> bool:
        with self.connection() as db:
            return db.execute("SELECT to_regclass('shortlist.anonymous_drafts') IS NOT NULL AS present").fetchone()["present"]

    def pending_anonymous_drafts(self) -> list[str]:
        if not self.worker:
            raise ValueError("Only the worker drafts before signup")
        with self.connection() as db:
            # A lapsed lease may already have reached the model; never dispatch the same draft twice.
            db.execute("UPDATE anonymous_drafts SET status='failed',error=? WHERE status='running' AND lease_until<=?",
                       (ANONYMOUS_INTERRUPTED, time.time()))
            return [str(row["id"]) for row in db.execute(
                "SELECT id FROM anonymous_drafts WHERE status='queued' AND expires_at>now() ORDER BY created_at LIMIT 20")]

    def lease_anonymous_draft(self, draft_id: str) -> str | None:
        with self.connection() as db:
            row = db.execute("UPDATE anonymous_drafts SET status='running',lease_until=? WHERE id=? AND status='queued' "
                             "AND expires_at>now() RETURNING website", (time.time() + 300, draft_id)).fetchone()
        return row["website"] if row else None

    def save_anonymous_draft(self, draft_id: str, *, events: list[dict], status: str | None = None,
                             source: str | None = None, draft: str | None = None, error: str | None = None):
        with self.connection() as db:
            if status is None:
                db.execute("UPDATE anonymous_drafts SET events=? WHERE id=? AND status='running'",
                           (json.dumps(events), draft_id))
            else:
                db.execute("UPDATE anonymous_drafts SET status=?,source=?,draft=?,error=?,events=? "
                           "WHERE id=? AND status='running'", (status, source, draft, error, json.dumps(events), draft_id))
