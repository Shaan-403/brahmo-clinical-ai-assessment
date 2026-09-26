"""SQLite connection + numbered-migration runner.

SQLite is a deliberate choice for this assessment: zero external services to
stand up, trivially inspectable by a reviewer, and fully sufficient at this
data volume. See SCALE.md for where this would need to change.

Note for development inside a sandboxed/bridged filesystem (e.g. a cloud
agent's mount of a local folder): some such bridges don't support the file
locking SQLite requires and raise "disk I/O error" on connect. Set the
BRAHMO_DB_PATH environment variable to point the database at a path on a
normal local filesystem in that situation. This has no effect on a normal
checkout on a real machine, where the configured db/brahmo.sqlite3 path
just works.
"""
from __future__ import annotations
import os
import sqlite3
from pathlib import Path

from src.config import REPO_ROOT, load_config

MIGRATIONS_DIR = REPO_ROOT / "db" / "migrations"


def get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    if db_path is None:
        db_path = os.environ.get("BRAHMO_DB_PATH") or (REPO_ROOT / load_config()["database"]["path"])
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_migrations_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            filename    TEXT PRIMARY KEY,
            applied_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.commit()


def applied_migrations(conn: sqlite3.Connection) -> set[str]:
    _ensure_migrations_table(conn)
    return {row["filename"] for row in conn.execute("SELECT filename FROM schema_migrations")}


def pending_migrations(conn: sqlite3.Connection) -> list[Path]:
    already = applied_migrations(conn)
    all_migrations = sorted(MIGRATIONS_DIR.glob("*.sql"))
    return [m for m in all_migrations if m.name not in already]


def migrate(conn: sqlite3.Connection) -> list[str]:
    """Apply every pending numbered migration, in order. Returns filenames applied."""
    _ensure_migrations_table(conn)
    applied = []
    for path in pending_migrations(conn):
        sql = path.read_text()
        conn.executescript(sql)
        conn.execute("INSERT INTO schema_migrations (filename) VALUES (?)", (path.name,))
        conn.commit()
        applied.append(path.name)
    return applied
