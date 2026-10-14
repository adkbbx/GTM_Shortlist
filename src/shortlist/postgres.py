"""Postgres adapter for the shared command/journal core, scoped by database RLS."""

import json
from contextlib import contextmanager
from uuid import UUID

import psycopg
from pydantic import SecretStr

from shortlist.store import BudgetExceeded, Store


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

    def __init__(self, dsn: SecretStr, workspace_id: UUID | None, *, worker: bool = False):
        if workspace_id is None and not worker:
            raise ValueError("Hosted access requires a verified workspace")
        self.dsn = dsn
        self.workspace_id = workspace_id
        self.worker = worker

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
                "SELECT set_config('shortlist.workspace_id',%s,true)",
                (str(self.workspace_id) if self.workspace_id else "",),
            )
            yield Connection(db)

    def begin(self, db):
        # Short command transactions serialize global quotas/idempotent commands.
        # Provider dispatch is outside this transaction. The lock is database-wide.
        db.execute("SELECT pg_advisory_xact_lock(7421391)")

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

    def reserve_global_search(self, db, provider: str, month: str, cap: int):
        if not db.execute("SELECT reserve_search_quota(?,?,?)", (provider, month, cap)).fetchone()[0]:
            raise BudgetExceeded("Global monthly search cap reached")
