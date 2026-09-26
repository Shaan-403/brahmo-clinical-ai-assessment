"""Loads severe_interaction_seed.csv. Both ingredient columns are resolved
through resolve_reference_ingredient -- the SAME exact-match-only-auto-
resolve / fuzzy-always-queued discipline used for NLEM and Jan Aushadhi (see
ingredient_normalizer.py). This file is not treated as authoritative enough
to mint new canonical ingredients; a name that doesn't exactly match the
existing registry is queued like any other alias, and the pair is left with
a NULL ingredient_a_id/ingredient_b_id until resolved. See DESIGN.md D-010
for how the rail check accounts for that.

Idempotent: re-running against the same file content is a no-op (see
DESIGN.md D-006 / load_batch.find_completed_batch).
"""
from __future__ import annotations
import csv
import sqlite3
from datetime import datetime, timezone

from src.config import data_path
from src.module_a.ingest.load_batch import start_load_batch, finish_load_batch, compute_file_hash, find_completed_batch
from src.module_a.normalize.ingredient_normalizer import resolve_reference_ingredient

SOURCE_NAME = "severe_interactions"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_severe_interactions(conn: sqlite3.Connection, csv_path=None) -> dict:
    csv_path = csv_path or data_path("severe_interactions")
    file_hash = compute_file_hash(csv_path)

    existing = find_completed_batch(conn, SOURCE_NAME, file_hash)
    if existing:
        rows = conn.execute(
            "SELECT COUNT(*) c FROM severe_interactions WHERE load_batch_id=?", (existing["id"],)
        ).fetchone()["c"]
        unresolved = conn.execute(
            """SELECT COUNT(*) c FROM severe_interactions
               WHERE load_batch_id=? AND (ingredient_a_id IS NULL OR ingredient_b_id IS NULL)""",
            (existing["id"],),
        ).fetchone()["c"]
        return {"batch_id": existing["id"], "rows": rows, "unresolved": unresolved, "skipped": True}

    rows = list(csv.DictReader(open(csv_path, newline="")))
    if not rows:
        raise ValueError(f"{csv_path} is empty")

    batch_id = start_load_batch(conn, SOURCE_NAME, None, str(csv_path), file_hash)

    unresolved = 0
    for row in rows:
        id_a, _ = resolve_reference_ingredient(
            conn, row["ingredient_a"], SOURCE_NAME, None, batch_id,
            entity_type_for_queue="severe_interaction_ingredient",
        )
        id_b, _ = resolve_reference_ingredient(
            conn, row["ingredient_b"], SOURCE_NAME, None, batch_id,
            entity_type_for_queue="severe_interaction_ingredient",
        )
        if id_a is None or id_b is None:
            unresolved += 1
        conn.execute(
            """
            INSERT INTO severe_interactions
                (ingredient_a_raw, ingredient_b_raw, ingredient_a_id, ingredient_b_id,
                 severity, note, source_tag, source, load_batch_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (row["ingredient_a"], row["ingredient_b"], id_a, id_b,
             row["severity"], row.get("note"), row.get("source_tag"), SOURCE_NAME, batch_id, _now()),
        )
    conn.commit()
    finish_load_batch(conn, batch_id, row_count=len(rows), notes=f"{unresolved} row(s) with an unresolved ingredient")
    return {"batch_id": batch_id, "rows": len(rows), "unresolved": unresolved, "skipped": False}
