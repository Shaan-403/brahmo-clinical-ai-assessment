"""Every ingested file gets a load_batches row. All rows it produces carry
this batch id, so any past output is reconstructable against exactly the
data version that produced it (binding law: everything versioned, everything
replayable)."""
from __future__ import annotations
import sqlite3
from datetime import datetime, timezone


def start_load_batch(conn: sqlite3.Connection, source_name: str, source_version: str | None, file_path: str) -> int:
    now = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        """
        INSERT INTO load_batches (source_name, source_version, file_path, started_at, status)
        VALUES (?, ?, ?, ?, 'RUNNING')
        """,
        (source_name, source_version, file_path, now),
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
