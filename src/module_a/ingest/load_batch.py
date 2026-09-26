"""Every ingested file gets a load_batches row. All rows it produces carry
this batch id, so any past output is reconstructable against exactly the
data version that produced it (binding law: everything versioned, everything
replayable).

Also the idempotency mechanism: file_hash is a content hash of the source
file. Before a loader inserts anything, it checks find_completed_batch() for
an existing COMPLETE batch with the same (source_name, file_hash) and skips
re-ingestion entirely if one exists -- see DESIGN.md D-006.

file_hash doubles as the provenance fallback for sources that declare no
version of their own (e.g. pharmacy_stock.csv has no version/date column at
all): rather than inventing a fake source_version, the load batch's content
hash + timestamp is the honest identity for that data -- see DESIGN.md D-007
and gaps_register.md.
"""
from __future__ import annotations
import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def compute_file_hash(file_path: str | Path) -> str:
    """SHA-256 of the file's raw bytes. Used to detect "have we already
    ingested this exact file" without relying on a source-declared version."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def find_completed_batch(conn: sqlite3.Connection, source_name: str, file_hash: str) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT * FROM load_batches
        WHERE source_name = ? AND file_hash = ? AND status = 'COMPLETE'
        ORDER BY id DESC LIMIT 1
        """,
        (source_name, file_hash),
    ).fetchone()


def start_load_batch(conn: sqlite3.Connection, source_name: str, source_version: str | None,
                      file_path: str, file_hash: str | None = None) -> int:
    now = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        """
        INSERT INTO load_batches (source_name, source_version, file_path, file_hash, started_at, status)
        VALUES (?, ?, ?, ?, ?, 'RUNNING')
        """,
        (source_name, source_version, file_path, file_hash, now),
    )
    conn.commit()
    return cur.lastrowid


def finish_load_batch(conn: sqlite3.Connection, batch_id: int, row_count: int, status: str = "COMPLETE", notes: str | None = None) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        UPDATE load_batches SET finished_at = ?, row_count = ?, status = ?, notes = ?
        WHERE id = ?
        """,
        (now, row_count, status, notes, batch_id),
    )
    conn.commit()
