"""Postgres adapter for the shared command/journal core, scoped by database RLS."""
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
            privilege = db.execute("SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=session_user").fetchone()
            if privilege["rolsuper"] or privilege["rolbypassrls"]:
                raise ValueError("Hosted runtime credentials must not bypass row security")
            db.execute("SET LOCAL ROLE shortlist_worker" if self.worker else "SET LOCAL ROLE shortlist_api")
            db.execute("SET LOCAL search_path TO shortlist,pg_catalog")
            db.execute("SET LOCAL statement_timeout TO '10s'")
            db.execute("SET LOCAL lock_timeout TO '5s'")
            db.execute("SELECT set_config('shortlist.workspace_id',%s,true)",
                       (str(self.workspace_id) if self.workspace_id else "",))
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
            db.execute("INSERT INTO workspaces(id) VALUES (?) ON CONFLICT(id) DO NOTHING", (self.workspace_id,))

    def reserve_global_search(self, db, provider: str, month: str, cap: int):
        if not db.execute("SELECT reserve_search_quota(?,?,?)", (provider, month, cap)).fetchone()[0]:
            raise BudgetExceeded("Global monthly search cap reached")
