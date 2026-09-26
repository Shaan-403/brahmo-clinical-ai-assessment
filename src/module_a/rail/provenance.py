"""Shared helper: the data-versions block attached to every rail check
result, so any past verdict can be explained against the exact ingested data
that produced it (binding law: everything versioned, everything replayable).
"""
from __future__ import annotations
import sqlite3


def current_source_versions(conn: sqlite3.Connection, source_names: list[str]) -> dict:
    versions = {}
    for name in source_names:
        row = conn.execute(
            """
            SELECT source_version, file_hash, id FROM load_batches
            WHERE source_name = ? AND status = 'COMPLETE'
            ORDER BY id DESC LIMIT 1
            """,
            (name,),
        ).fetchone()
        versions[name] = (
            {"load_batch_id": row["id"], "source_version": row["source_version"], "file_hash": row["file_hash"]}
            if row else None
        )
    return versions
