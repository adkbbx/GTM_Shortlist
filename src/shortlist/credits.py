"""Hosted credit accounting; company delivery integration is a separate boundary."""

from pydantic import BaseModel, ConfigDict, Field

from shortlist.postgres import PostgresStore
from shortlist.store import BudgetExceeded, Conflict


class Balance(BaseModel):
    model_config = ConfigDict(frozen=True)
    available: int = Field(ge=0)
    reserved: int = Field(ge=0)
    used: int = Field(ge=0)


class CreditWallet:
    def __init__(self, store: PostgresStore):
        if store.workspace_id is None:
            raise ValueError("Credit commands require a verified workspace")
        self.store = store

    def _balance(self, db):
        entries = db.execute(
            "SELECT COALESCE(sum(amount),0) AS ledger_total,"
            "COALESCE(sum(CASE WHEN kind='usage' THEN -amount ELSE 0 END),0) AS used_total "
            "FROM credit_entries WHERE workspace_id=?",
            (self.store.workspace_id,),
        ).fetchone()
        held = db.execute(
            "SELECT COALESCE(sum(requested-consumed),0) FROM credit_reservations "
            "WHERE workspace_id=? AND state='held'",
            (self.store.workspace_id,),
        ).fetchone()[0]
        return Balance(available=entries["ledger_total"] - held, reserved=held, used=entries["used_total"])

    def balance(self):
        with self.store.connection() as db:
            self.store.begin(db)
            return self._balance(db)

    def grant(self, quantity: int, operation_key: str, description: str):
        if not self.store.worker:
            raise ValueError("Only verified server purchase/operator processing can grant credits")
        if (
            type(quantity) is not int
            or not 1 <= quantity <= 10000
            or not operation_key
            or operation_key == "signup"
        ):
            raise ValueError("Invalid credit grant")
        with self.store.connection() as db:
            self.store.begin(db)
            existing = db.execute(
                "SELECT amount,kind,description FROM credit_entries WHERE workspace_id=? AND operation_key=?",
                (self.store.workspace_id, operation_key),
            ).fetchone()
            if existing:
                if (existing["amount"], existing["kind"], existing["description"]) != (
                    quantity,
                    "purchase",
                    description,
                ):
                    raise Conflict("Credit grant key was already used for different inputs")
                return
            db.execute(
                "INSERT INTO credit_entries(workspace_id,operation_key,kind,amount,description) VALUES (?,?,?,?,?)",
                (self.store.workspace_id, operation_key, "purchase", quantity, description),
            )

    def reserve(self, run_id: str, quantity: int):
        if type(quantity) is not int or not 1 <= quantity <= 3:
            raise ValueError("Current batches support one to three companies")
        with self.store.connection() as db:
            self.store.begin(db)
            self.reserve_in_transaction(db, run_id, quantity)

    def reserve_in_transaction(self, db, run_id: str, quantity: int):
        if not db.execute(
            "SELECT 1 FROM runs WHERE id=? AND workspace_id=?", (run_id, self.store.workspace_id)
        ).fetchone():
            raise KeyError(run_id)
        existing = db.execute(
            "SELECT requested FROM credit_reservations WHERE run_id=? AND workspace_id=?",
            (run_id, self.store.workspace_id),
        ).fetchone()
        if existing:
            if existing["requested"] != quantity:
                raise Conflict("Batch credit reservation already has a different size")
            return
        if self._balance(db).available < quantity:
            raise BudgetExceeded("Not enough research credits for this batch")
        db.execute(
            "INSERT INTO credit_reservations(run_id,workspace_id,requested) VALUES (?,?,?)",
            (run_id, self.store.workspace_id, quantity),
        )

    def consume(self, run_id: str, company_domain: str):
        """Foundation command; worker must later call within the record-save transaction."""
        if not self.store.worker:
            raise ValueError("Only delivery processing can consume credits")
        with self.store.connection() as db:
            self.store.begin(db)
            self.consume_in_transaction(db, run_id, company_domain)

    def consume_in_transaction(self, db, run_id: str, company_domain: str):
        key = "delivery:" + run_id + ":" + company_domain
        if db.execute(
            "SELECT 1 FROM credit_entries WHERE workspace_id=? AND operation_key=?",
            (self.store.workspace_id, key),
        ).fetchone():
            return
        changed = db.execute(
            "UPDATE credit_reservations SET consumed=consumed+1 WHERE run_id=? AND workspace_id=? "
            "AND state='held' AND consumed<requested RETURNING run_id",
            (run_id, self.store.workspace_id),
        ).fetchone()
        if changed is None:
            raise Conflict("Batch credits are no longer held or its delivery allowance is exhausted")
        db.execute(
            "INSERT INTO credit_entries(workspace_id,operation_key,kind,amount,description) VALUES (?,?,?,?,?)",
            (self.store.workspace_id, key, "usage", -1, "Company research: " + company_domain),
        )

    def settle(self, run_id: str):
        if not self.store.worker:
            raise ValueError("Only terminal worker processing can settle credits")
        with self.store.connection() as db:
            self.store.begin(db)
            self.settle_in_transaction(db, run_id)

    def settle_in_transaction(self, db, run_id: str):
        changed = db.execute(
            "UPDATE credit_reservations SET state=CASE WHEN consumed=0 THEN 'released' ELSE 'settled' END "
            "WHERE run_id=? AND workspace_id=? AND state='held' RETURNING run_id",
            (run_id, self.store.workspace_id),
        ).fetchone()
        if (
            not changed
            and not db.execute(
                "SELECT 1 FROM credit_reservations WHERE run_id=? AND workspace_id=?",
                (run_id, self.store.workspace_id),
            ).fetchone()
        ):
            raise KeyError(run_id)
