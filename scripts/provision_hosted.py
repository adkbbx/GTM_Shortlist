"""One-time operator setup. Credentials stay in ignored files, never stdout."""
import json
import os
import secrets
from pathlib import Path
from urllib.parse import quote, urlencode, urlsplit, urlunsplit
from uuid import UUID

import psycopg
from dotenv import dotenv_values, set_key
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
from pydantic import SecretStr

from shortlist.config import Settings
from shortlist.local_credentials import apply_local_credentials
from shortlist.postgres import PostgresStore

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "deploy" / "secrets"
ROLES = {"api": ("shortlist_api_login", "shortlist_api"), "worker": ("shortlist_worker_login", "shortlist_worker")}


def runtime_uri(operator, login, password, project):
    settings = conninfo_to_dict(operator)
    host = settings["host"]
    if host.endswith(".pooler.supabase.com"):
        if not settings["user"].endswith("." + project):
            raise ValueError("Pooler project does not match public project settings")
        login += "." + project
    elif host != f"db.{project}.supabase.co":
        raise ValueError("Operator hostname does not match this Supabase project")
    extras = {key: value for key, value in settings.items() if key not in {"host", "port", "user", "password", "dbname"}}
    extras["sslmode"] = "require"
    return urlunsplit(("postgresql", f'{quote(login, safe="")}:{quote(password, safe="")}@{host}:{settings.get("port", "5432")}',
                       "/" + quote(settings.get("dbname", "postgres"), safe=""), urlencode(extras), ""))


def private_env(path, values):
    temporary = path.with_suffix(".pending")
    temporary.write_text("# Private hosted configuration. Do not commit or paste into chat.\n", encoding="utf-8")
    for key, value in values.items():
        set_key(temporary, key, value or "", quote_mode="always")
    os.replace(temporary, path)


def main():
    operator = dotenv_values(PRIVATE / "migrate.env").get("SHORTLIST_MIGRATION_DATABASE_URL")
    public = dotenv_values(PRIVATE / "supabase-public.env")
    project = urlsplit(public["SUPABASE_URL"]).hostname.split(".")[0]
    state_path = PRIVATE / "runtime-logins.json"
    with psycopg.connect(operator, sslmode="require", connect_timeout=10) as db:
        db.execute("SELECT pg_advisory_xact_lock(7421390)")
        if not db.pgconn.ssl_in_use:
            raise ValueError("Operator connection requires TLS")
        if state_path.exists():
            state = json.loads(state_path.read_text(encoding="utf-8"))
            if state["project"] != project:
                raise ValueError("Private login state belongs to another project")
        else:
            if any(db.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (login,)).fetchone() for login, _ in ROLES.values()):
                raise ValueError("Existing login roles require their original private credentials; not rotating passwords")
            state = {"project": project, **{kind: secrets.token_urlsafe(36) for kind in ROLES}}
            temporary = state_path.with_suffix(".pending")
            temporary.write_text(json.dumps(state), encoding="utf-8")
            os.replace(temporary, state_path)
        connections = {kind: runtime_uri(operator, login, state[kind], project) for kind, (login, _) in ROLES.items()}
        for kind, (login, group) in ROLES.items():
            existing = db.execute("SELECT rolsuper,rolbypassrls,rolcreatedb,rolcreaterole FROM pg_roles WHERE rolname=%s", (login,)).fetchone()
            if existing is None:
                db.execute(sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD {} IN ROLE {}")
                           .format(sql.Identifier(login), sql.Literal(state[kind]), sql.Identifier(group)))
            elif any(existing):
                raise ValueError("Existing runtime login has excessive privileges")
        if db.execute("SELECT pg_has_role(%s,'shortlist_worker','MEMBER')", (ROLES["api"][0],)).fetchone()[0]:
            raise ValueError("API login must not be a member of the worker role")
    for kind in ROLES:
        store = PostgresStore(SecretStr(connections[kind]), UUID(int=0) if kind == "api" else None, worker=kind == "worker")
        with store.connection() as connection:
            if not connection.database.pgconn.ssl_in_use:
                raise ValueError("Runtime connection requires TLS")
            connection.execute("SELECT 1")
    shared = {"SHORTLIST_MODE": "hosted", "SUPABASE_URL": public["SUPABASE_URL"],
              "SUPABASE_PUBLISHABLE_KEY": public["SUPABASE_PUBLISHABLE_KEY"], "SHORTLIST_APP_URL": public["SHORTLIST_APP_URL"]}
    private_env(PRIVATE / "api.env", {**shared, "SHORTLIST_DATABASE_URL": connections["api"], "PORT": "8000"})
    previous = dotenv_values(PRIVATE / "worker.env")
    settings = apply_local_credentials(Settings.load())
    private_env(PRIVATE / "worker.env", {**shared, "SHORTLIST_DATABASE_URL": connections["worker"],
                "SHORTLIST_WORKER_DATABASE_URL": connections["worker"], "SHORTLIST_SEARCH_PROVIDER": settings.search_provider,
                "TAVILY_API_KEY": settings.tavily_key.get_secret_value(), "SERPAPI_API_KEY": settings.serpapi_key.get_secret_value(),
                **{key: previous.get(key) or value for key, value in {
                    "GEMMA_BASE_URL": settings.gemma_base_url, "GEMMA_MODEL": settings.gemma_model,
                    "GEMMA_API_KEY": settings.gemma_key.get_secret_value()}.items()},
                "SHORTLIST_GLOBAL_SEARCH_CAP": str(settings.global_search_cap),
                "SHORTLIST_SOURCE_CACHE_HOURS": str(settings.source_cache_hours)})
    print("Restricted API/worker logins authenticated with TLS; private Render environment files prepared. No deployment triggered.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, psycopg.Error) as exc:
        # Driver errors may contain a DSN/password; print only classification.
        print("Provisioning stopped:", type(exc).__name__, "SQLSTATE", getattr(exc, "sqlstate", None))
        raise SystemExit(1) from None
