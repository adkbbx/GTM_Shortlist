"""Bounded, retryable server-operator closure. Never an unauthenticated browser action."""
from typing import Literal
from uuid import UUID

import httpx
from pydantic import BaseModel, Field, ValidationError

from shortlist.auth import AuthUnavailable
from shortlist.config import Settings
from shortlist.domain import Value
from shortlist.postgres import PostgresStore
from shortlist.store import Conflict


class Closing(Value):
    state: Literal["closing"] = "closing"
    erased_in_batch: int = Field(ge=0, le=100)
    remaining_runs: int = Field(ge=0)
    reason: Literal["research_remaining", "identity_unavailable"]
    identity_removal: Literal["unconfirmed"] = "unconfirmed"


class Closed(Value):
    state: Literal["closed"] = "closed"
    erased_in_batch: int = Field(ge=0, le=100)
    identity_removal: Literal["confirmed_deleted"] = "confirmed_deleted"


class AdminUser(BaseModel):
    id: UUID


def admin_user_request(settings: Settings, identity: UUID, method: Literal["GET", "DELETE"], *, transport=None):
    """Use opaque server keys on apikey, never as user bearer JWTs."""
    try:
        with (
            httpx.Client(timeout=5, follow_redirects=False, trust_env=False, transport=transport) as client,
            client.stream(method, settings.supabase_url.rstrip("/") + f"/auth/v1/admin/users/{identity}",
                          headers={"apikey": settings.supabase_admin_key.get_secret_value()},
                          json={"should_soft_delete": False} if method == "DELETE" else None) as response,
        ):
            if method == "DELETE" and response.status_code in (200, 204):
                return
            content = bytearray()
            for chunk in response.iter_bytes():
                content.extend(chunk)
                if len(content) > 65536:
                    raise AuthUnavailable("Identity administration is unavailable")
            if method == "DELETE" and response.status_code == 404:
                payload = response.json()
                if isinstance(payload, dict) and payload.get("error_code") == "user_not_found":
                    return
            if method == "GET" and response.status_code == 200 and AdminUser.model_validate_json(content).id == identity:
                return
            raise AuthUnavailable("Identity administration is unavailable")
    except (httpx.HTTPError, ValidationError, ValueError):
        raise AuthUnavailable("Identity administration is unavailable") from None


def close_account(settings: Settings, identity: UUID, confirmation: UUID, *, transport=None) -> Closing | Closed:
    if identity != confirmation:
        raise ValueError("Confirmation must match the exact workspace UUID")
    if settings.mode != "hosted" or not settings.worker_database_url.get_secret_value() or not settings.supabase_admin_key.get_secret_value():
        raise ValueError("Hosted closure requires separate worker credentials and a server-only Supabase admin secret")
    store = PostgresStore(settings.worker_database_url, identity, worker=True, maintenance=True)
    with store.connection() as db:
        workspace = db.execute("SELECT closure_state FROM workspaces WHERE id=?", (identity,)).fetchone()
        if workspace is None:
            raise KeyError(identity)
        state = workspace["closure_state"]
    if state == "closed":
        return Closed(erased_in_batch=0)
    if state == "open":
        # Validate the configured credential/target before erasing anything.
        admin_user_request(settings, identity, "GET", transport=transport)
    with store.connection() as db:
        store.begin(db)
        if db.execute("SELECT closure_state FROM workspaces WHERE id=?", (identity,)).fetchone()[0] == "closed":
            return Closed(erased_in_batch=0)
        if db.execute("SELECT 1 FROM runs WHERE workspace_id=? AND status IN ('queued','running') AND deleted_at IS NULL",
                      (identity,)).fetchone():
            raise Conflict("Wait for active research to finish before closing this account")
        db.execute("UPDATE workspaces SET closure_state='closing',closure_requested_at=COALESCE(closure_requested_at,now()) "
                   "WHERE id=? AND closure_state='open'", (identity,))
        identities = [row["id"] for row in db.execute("SELECT id FROM runs WHERE workspace_id=? AND deleted_at IS NULL "
                                                     "ORDER BY position LIMIT 100", (identity,))]
    erased = sum(store.delete_run(run_id) for run_id in identities)
    with store.connection() as db:
        store.clear_source_cache(db)
        remaining = db.execute("SELECT count(*) FROM runs WHERE workspace_id=? AND deleted_at IS NULL", (identity,)).fetchone()[0]
    if remaining:
        return Closing(erased_in_batch=erased, remaining_runs=remaining, reason="research_remaining")
    try:
        admin_user_request(settings, identity, "DELETE", transport=transport)
    except AuthUnavailable:
        return Closing(erased_in_batch=erased, remaining_runs=0, reason="identity_unavailable")
    with store.connection() as db:
        store.begin(db)
        db.execute("UPDATE workspaces SET closure_state='closed',closure_completed_at=COALESCE(closure_completed_at,now()) "
                   "WHERE id=? AND closure_state='closing'", (identity,))
    return Closed(erased_in_batch=erased)
