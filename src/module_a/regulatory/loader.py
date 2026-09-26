"""A.5 -- loads regulatory_gazette_events.csv as an append-only event log.

This file has no version/date-of-extract column of its own (each row is
itself a dated legal event, which is different from a source-version). Like
pharmacy_stock.csv (DESIGN.md D-007), the load_batches.file_hash is the
provenance identity for "which exact extract of the gazette log produced
these rows" -- source_version is left NULL for the same honest-NULL reason.

Every FDC/INGREDIENT event's parsed target ingredient name(s) are checked
against the canonical ingredient registry AT INGESTION TIME (not just later,
implicitly, when a rail check happens to look them up). A name that doesn't
exactly match is queued to review_queue with reason code
REGULATORY_TARGET_INGREDIENT_UNMAPPED, carrying the event's own provenance
(event_id, notification_id, target_description, action, effective_date,
load_batch_id) as evidence -- this is a plain exact-match check only, no
fuzzy candidate search: a mismatch here means either a genuine vocabulary
gap or a non-standard target_description (e.g. a category description
rather than an ingredient list), not a spelling variant worth guessing at.
Nothing here mints a new canonical ingredient from this source, and nothing
here changes how the Safety Rail matches events (see DESIGN.md D-009/D-010,
unchanged) -- this only makes the same, already-existing coverage gap
visible in the review queue at ingestion time instead of discoverable only
by inspecting a check result's evidence (see DESIGN.md D-014).

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
from src.module_a.normalize.ingredient_normalizer import normalize_key
from src.module_a.regulatory.target_parser import parse_target_description
from src.module_a.review_queue.queue import add_review_item

SOURCE_NAME = "regulatory_events"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _unmapped_ingredient_names(conn: sqlite3.Connection, ingredient_names: list[str]) -> list[str]:
    unmapped = []
    for name in ingredient_names:
        row = conn.execute("SELECT id FROM ingredients WHERE normalized_key = ?", (normalize_key(name),)).fetchone()
        if row is None:
            unmapped.append(name)
    return unmapped


def load_regulatory_events(conn: sqlite3.Connection, csv_path=None) -> dict:
    csv_path = csv_path or data_path("regulatory_events")
    file_hash = compute_file_hash(csv_path)

    existing = find_completed_batch(conn, SOURCE_NAME, file_hash)
    if existing:
        rows = conn.execute(
            "SELECT COUNT(*) c FROM regulatory_events WHERE load_batch_id=?", (existing["id"],)
        ).fetchone()["c"]
        queued = conn.execute(
            "SELECT COUNT(*) c FROM review_queue WHERE entity_type='regulatory_event' "
            "AND entity_id IN (SELECT id FROM regulatory_events WHERE load_batch_id=?)", (existing["id"],)
        ).fetchone()["c"]
        return {"batch_id": existing["id"], "events": rows, "queued": queued, "skipped": True}

    rows = list(csv.DictReader(open(csv_path, newline="")))
    if not rows:
        raise ValueError(f"{csv_path} is empty")

    batch_id = start_load_batch(conn, SOURCE_NAME, None, str(csv_path), file_hash)

    queued = 0
    for row in rows:
        ingredient_names, scope_note = parse_target_description(row["target_description"], row["target_type"])
        cur = conn.execute(
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
        event_row_id = cur.lastrowid

        if ingredient_names:
            unmapped = _unmapped_ingredient_names(conn, ingredient_names)
            if unmapped:
                queued += 1
                add_review_item(conn, entity_type="regulatory_event", entity_id=event_row_id,
                                 reason_code="REGULATORY_TARGET_INGREDIENT_UNMAPPED", candidates={
                                     "event_id": row["event_id"], "notification_id": row.get("notification_id"),
                                     "target_type": row["target_type"],
                                     "target_description": row["target_description"],
                                     "action": row["action"], "effective_date": row["effective_date"],
                                     "load_batch_id": batch_id,
                                     "parsed_ingredient_names": ingredient_names,
                                     "unmapped_ingredient_names": unmapped,
                                 })
    conn.commit()
    finish_load_batch(conn, batch_id, row_count=len(rows),
                       notes=f"{len(rows)} regulatory events, {queued} with an unmapped target ingredient")
    return {"batch_id": batch_id, "events": len(rows), "queued": queued, "skipped": False}
