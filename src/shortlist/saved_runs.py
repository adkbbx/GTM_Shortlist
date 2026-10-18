"""Read saved evaluation databases without creating SQLite sidecars."""
import sqlite3
from pathlib import Path


def read_only_database(path: Path) -> sqlite3.Connection:
    uri = "file:" + str(path) + "?mode=ro"
    db = sqlite3.connect(uri, uri=True)
    try:
        db.execute("PRAGMA schema_version")
        return db
    except sqlite3.OperationalError:
        db.close()
        # A sealed WAL-mode database without sidecars needs no shared-memory file.
        # Never ignore an existing WAL, which may contain committed saved evidence.
        if not path.is_file() or Path(str(path) + "-wal").exists():
            raise
        return sqlite3.connect(uri + "&immutable=1", uri=True)
