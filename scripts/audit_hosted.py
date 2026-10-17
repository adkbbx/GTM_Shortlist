"""Read-only hosted preflight. No research dispatch, auth mutation or secret output."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import psycopg
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "deploy" / "secrets"


def origin(value):
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path not in ("", "/")):
        raise ValueError("Expected a plain HTTPS origin")
    return value.rstrip("/")


def http_audit(public):
    app = origin(public["SHORTLIST_APP_URL"])
    result = {}
    with httpx.Client(timeout=30, follow_redirects=False) as client:
        for name, path in (("root", "/"), ("health", "/api/health"),
                           ("auth_setup", "/api/auth/setup"), ("unauthenticated_runs", "/api/runs")):
            response = client.get(app + path)
            item = {"status": response.status_code}
            if name == "health" and response.status_code == 200:
                data = response.json()
                item["mode"] = data.get("mode")
                # Hosted public health deliberately hides worker/provider state.
                item["liveness_only"] = True
            if name == "auth_setup" and response.status_code == 200:
                data = response.json()
                item["project_matches_local"] = data.get("supabase_url") == public["SUPABASE_URL"].rstrip("/")
                item["publishable_key_matches_local"] = data.get("publishable_key") == public["SUPABASE_PUBLISHABLE_KEY"]
                item["redirect_matches_app"] = data.get("redirect_url") == app + "/"
            if name == "root" and response.status_code == 200:
                item["html_sha256"] = hashlib.sha256(response.content).hexdigest()
            result[name] = item
        response = client.get(origin(public["SUPABASE_URL"]) + "/auth/v1/settings",
                              headers={"apikey": public["SUPABASE_PUBLISHABLE_KEY"]})
        auth = {"status": response.status_code, "email_delivery_unverified": True}
        if response.status_code == 200:
            data = response.json()
            for key in ("disable_signup", "mailer_autoconfirm", "external_email_enabled"):
                if isinstance(data.get(key), bool):
                    auth[key] = data[key]
            if isinstance(data.get("external"), dict):
                auth["email_enabled"] = data["external"].get("email")
        result["auth_settings"] = auth
    return result


def database_audit():
    result = {}
    for kind, envfile, key in (("api", "api.env", "SHORTLIST_DATABASE_URL"),
                               ("worker", "worker.env", "SHORTLIST_WORKER_DATABASE_URL")):
        values = dotenv_values(PRIVATE / envfile)
        with psycopg.connect(values[key], sslmode="require", connect_timeout=10,
                             options="-c default_transaction_read_only=on") as db:
            db.execute("SET LOCAL statement_timeout = '10s'")
            privileges = db.execute(
                "SELECT rolsuper,rolbypassrls,rolcreatedb,rolcreaterole FROM pg_roles WHERE rolname=session_user"
            ).fetchone()
            membership = db.execute("SELECT pg_has_role(session_user,'shortlist_worker','MEMBER')").fetchone()[0]
            db.execute("SET LOCAL ROLE shortlist_api" if kind == "api" else "SET LOCAL ROLE shortlist_worker")
            db.execute("SELECT email_draft FROM shortlist.records LIMIT 0")
            item = {"tls": db.pgconn.ssl_in_use, "excess_privilege": any(privileges),
                    "worker_membership": membership, "draft_column_readable": True}
            if kind == "worker":
                item["fresh_heartbeats"] = db.execute(
                    "SELECT count(*) FROM shortlist.worker_heartbeats WHERE expires_at > extract(epoch FROM now())"
                ).fetchone()[0]
                item["run_counts"] = dict(db.execute(
                    "SELECT status,count(*) FROM shortlist.runs GROUP BY status"
                ).fetchall())
            result[kind] = item
    operator = dotenv_values(PRIVATE / "migrate.env")["SHORTLIST_MIGRATION_DATABASE_URL"]
    with psycopg.connect(operator, sslmode="require", connect_timeout=10,
                         options="-c default_transaction_read_only=on") as db:
        db.execute("SET LOCAL statement_timeout = '10s'")
        applied = dict(db.execute("SELECT version,checksum FROM shortlist.schema_migrations").fetchall())
        expected = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in sorted((ROOT / "migrations").glob("*.sql"))}
        result["migrations"] = {"tls": db.pgconn.ssl_in_use, "expected_count": len(expected),
                                "missing": sorted(expected.keys() - applied.keys()),
                                "checksum_mismatches": sorted(k for k in expected if k in applied
                                                              and expected[k] != applied[k]),
                                "unexpected": sorted(applied.keys() - expected.keys())}
    return result


def preflight_passed(report):
    """Only the narrow read-only infrastructure gate, never full release acceptance."""
    try:
        http, database = report["http"], report["database"]
        setup, auth = http["auth_setup"], http["auth_settings"]
        migrations = database["migrations"]
        return (http["root"]["status"] == http["health"]["status"] == setup["status"] == auth["status"] == 200
                and http["health"]["mode"] == "hosted" and http["unauthenticated_runs"]["status"] == 401
                and all(setup[key] is True for key in
                        ("project_matches_local", "publishable_key_matches_local", "redirect_matches_app"))
                and auth["disable_signup"] is False and auth["mailer_autoconfirm"] is False
                and auth["email_enabled"] is True
                and all(database[kind]["tls"] is True and database[kind]["excess_privilege"] is False
                        and database[kind]["draft_column_readable"] is True for kind in ("api", "worker"))
                and database["api"]["worker_membership"] is False
                and database["worker"]["worker_membership"] is True
                and database["worker"]["fresh_heartbeats"] > 0 and migrations["tls"] is True
                and not any(migrations[key] for key in ("missing", "checksum_mismatches", "unexpected")))
    except (KeyError, TypeError):
        return False


def main():
    report = {"observed_at_utc": datetime.now(UTC).isoformat(), "read_only": True}
    public = dotenv_values(PRIVATE / "supabase-public.env")
    for name, audit in (("http", lambda: http_audit(public)), ("database", database_audit)):
        try:
            report[name] = audit()
        except (httpx.HTTPError, psycopg.Error, ValueError, KeyError, OSError) as error:
            # Driver/HTTP exceptions can embed DSNs, tokens or raw external response text.
            report[name] = {"error_type": type(error).__name__, "incomplete": True}
    report["preflight_passed"] = preflight_passed(report)
    output = PRIVATE / "evaluations" / "hosted-preflight.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    raise SystemExit(0 if main()["preflight_passed"] else 1)
