"""Apply checksummed migrations with operator credentials, never API credentials."""
import argparse
import hashlib
import os
from pathlib import Path

import psycopg


def migrate(dsn: str):
    with psycopg.connect(dsn, connect_timeout=5) as db:
        db.execute("SELECT pg_advisory_xact_lock(7421390)")
        db.execute("CREATE SCHEMA IF NOT EXISTS shortlist")
        db.execute("REVOKE ALL ON SCHEMA shortlist FROM PUBLIC")
        db.execute("CREATE TABLE IF NOT EXISTS shortlist.schema_migrations(version TEXT PRIMARY KEY,checksum TEXT NOT NULL)")
        for path in sorted((Path(__file__).resolve().parents[1] / "migrations").glob("*.sql")):
            content = path.read_text(encoding="utf-8")
            checksum = hashlib.sha256(content.encode()).hexdigest()
            previous = db.execute("SELECT checksum FROM shortlist.schema_migrations WHERE version=%s", (path.name,)).fetchone()
            if previous:
                if previous[0] != checksum:
                    raise ValueError("An applied migration changed; add a new migration")
                continue
            db.execute(content)
            db.execute("INSERT INTO shortlist.schema_migrations VALUES(%s,%s)", (path.name, checksum))
            print("Applied", path.name, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.parse_args()
    migrate(os.environ["SHORTLIST_MIGRATION_DATABASE_URL"])
