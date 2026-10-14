"""Isolated Postgres + actual hosted API/worker with labelled provider transports.

Never deploy this fixture or point its operator URL at a production cluster.
"""

import base64
import json
import os
import threading
from uuid import UUID, uuid4

import httpx
import psycopg
import uvicorn
from fastapi import FastAPI
from migrate_postgres import migrate
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from pydantic import BaseModel, SecretStr
from ui_test_providers import FixtureModel, FixtureSearch, fixture_fetch

import shortlist.api as api_module
from shortlist.auth import verify_user
from shortlist.config import Settings
from shortlist.postgres import PostgresStore
from shortlist.providers import ProviderError
from shortlist.worker import execute_run


def run():
    admin = os.environ["SHORTLIST_UI_TEST_PG_URL"]
    name = "shortlist_browser_" + uuid4().hex
    with psycopg.connect(admin, autocommit=True) as db:
        db.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    try:
        operator = make_conninfo(admin, dbname=name)
        migrate(operator)
        with psycopg.connect(admin, autocommit=True) as db:
            for login, role in (
                ("shortlist_browser_api", "shortlist_api"),
                ("shortlist_browser_worker", "shortlist_worker"),
            ):
                if not db.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (login,)).fetchone():
                    db.execute(
                        sql.SQL(
                            "CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD 'isolated-test-only' IN ROLE {}"
                        ).format(sql.Identifier(login), sql.Identifier(role))
                    )
        connection = conninfo_to_dict(operator)
        connection.update(user="shortlist_browser_api", password="isolated-test-only")
        api_dsn = SecretStr(make_conninfo(**connection))
        connection["user"] = "shortlist_browser_worker"
        worker_dsn = SecretStr(make_conninfo(**connection))
        settings = Settings(
            mode="hosted",
            database_url=api_dsn,
            worker_database_url=worker_dsn,
            supabase_url="https://shortlist-auth.example",
            supabase_publishable_key="sb_publishable_fixture",
            app_url="https://app.example",
            booking_url="https://cal.example/eygentic/setup-fixture",
            tavily_key="labelled-fixture",
            gemma_model="labelled-fixture",
            gemma_base_url="https://labelled-fixture.example",
        )

        def user_endpoint(request):
            token = request.headers.get("authorization", "").removeprefix("Bearer ")
            try:
                if not token.endswith(".labelled-credit-fixture"):
                    return httpx.Response(401)
                payload = token.split(".")[1]
                identity = UUID(
                    json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))["sub"]
                )
            except (ValueError, KeyError, IndexError):
                return httpx.Response(401)
            return httpx.Response(
                200,
                json={
                    "id": str(identity),
                    "role": "authenticated",
                    "email_confirmed_at": "2026-10-14T00:00:00Z",
                },
            )

        # Test-only transport still exercises the production auth boundary.
        api_module.verify_user = lambda cfg, token: verify_user(
            cfg, token, transport=httpx.MockTransport(user_endpoint)
        )
        scheduler = PostgresStore(worker_dsn, None, worker=True)
        stopped = threading.Event()

        class Model(FixtureModel):
            def verify(self, profile, record):
                if record.domain == "example-2.com":
                    raise ProviderError("Labelled fixture: verifier temporarily unavailable")
                return super().verify(profile, record)

        def loop():
            while not stopped.is_set():
                scheduler.worker_heartbeat("labelled-hosted-browser-worker")
                for run_id in scheduler.pending_runs():
                    execute_run(
                        scheduler.for_run(run_id),
                        settings,
                        run_id,
                        search=FixtureSearch(),
                        model=Model(),
                        fetch=fixture_fetch,
                    )
                stopped.wait(0.1)

        thread = threading.Thread(target=loop, daemon=True)
        thread.start()
        application = FastAPI()

        @application.get("/__fixture_ready")
        def ready():
            return {"fixture": True}

        class CreditFixture(BaseModel):
            workspace_id: UUID

        @application.post("/__fixture_credit_grants")
        def credit_grants(input: CreditFixture):
            # Fixed, isolated operator grants for pagination verification, never payments.
            scoped = PostgresStore(worker_dsn, input.workspace_id, worker=True)
            scoped.ensure_workspace()
            with scoped.connection() as db:
                scoped.begin(db)
                for index in range(101):
                    db.execute("INSERT INTO credit_entries(workspace_id,operation_key,kind,amount,description) VALUES (?,?,?,?,?) "
                               "ON CONFLICT(workspace_id,operation_key) DO NOTHING",
                               (input.workspace_id, f"pagination-fixture-{index}", "purchase", 1,
                                "Labelled browser operator grant; no payment"))
            return {"fixture": True}

        application.mount("/", api_module.create_app(settings))
        try:
            uvicorn.run(application, host="127.0.0.1", port=8016, log_level="warning")
        finally:
            stopped.set()
            thread.join(timeout=10)
    finally:
        # This exact UUID-named database was created above; never delete a supplied database.
        with psycopg.connect(admin, autocommit=True) as db:
            db.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


if __name__ == "__main__":
    run()
