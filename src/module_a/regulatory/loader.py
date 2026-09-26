"""A.5 -- loads regulatory_gazette_events.csv as an append-only event log.

This file has no version/date-of-extract column of its own (each row is
itself a dated legal event, which is different from a source-version). Like
pharmacy_stock.csv (DESIGN.md D-007), the load_batches.file_hash is the
provenance identity for "which exact extract of the gazette log produced
these rows" -- source_version is left NULL for the same honest-NULL reason.

Idempotent: re-running against the same file content is a no-op (see
DESIGN.md D-006 / load_batch.find_completed_batch).
"""
from __future__ import annotations
import csv
import json
import sqlite3
from datetime import datetime, timezone

from src.config import data_path
from src.module_a.ingest.load_batch import start_load_batch, finish_load_batch, compute_file_hash, find_completed_batch
from src.module_a.regulatory.target_parser import parse_target_description

SOURCE_NAME = "regulatory_events"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_regulatory_events(conn: sqlite3.Connection, csv_path=None) -> dict:
    csv_path = csv_path or data_path("regulatory_events")
    file_hash = compute_file_hash(csv_path)

    existing = find_completed_batch(conn, SOURCE_NAME, file_hash)
    if existing:
        rows = conn.execute(
            "SELECT COUNT(*) c FROM regulatory_events WHERE load_batch_id=?", (existing["id"],)
        ).fetchone()["c"]
        return {"batch_id": existing["id"], "events": rows, "skipped": True}

    rows = list(csv.DictReader(open(csv_path, newline="")))
    if not rows:
        raise ValueError(f"{csv_path} is empty")

    batch_id = start_load_batch(conn, SOURCE_NAME, None, str(csv_path), file_hash)

    for row in rows:
        ingredient_names, scope_note = parse_target_description(row["target_description"], row["target_type"])
        conn.execute(
            """
            INSERT INTO regulatory_events
                (event_id, notification_id, date_published, effective_date, action, target_type,
                 target_description, target_ingredients_json, scope_note, supersedes_event_id,
                 note, source, load_batch_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["event_id"], row.get("notification_id"), row.get("date_published"),
                row["effective_date"], row["action"], row["target_type"], row["target_description"],
                json.dumps(ingredient_names) if ingredient_names is not None else None,
                scope_note, row.get("supersedes_event_id") or None, row.get("note"),
                SOURCE_NAME, batch_id, _now(),
            ),
        )
    conn.commit()
    finish_load_batch(conn, batch_id, row_count=len(rows), notes=f"{len(rows)} regulatory events")
    return {"batch_id": batch_id, "events": len(rows), "skipped": False}
