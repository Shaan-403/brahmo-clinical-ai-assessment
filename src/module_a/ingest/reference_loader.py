"""Loads NLEM and Jan Aushadhi extracts as reference data, cross-linked to
the canonical ingredient registry where a confident (exact) mapping exists.
Uncertain mappings are queued, never merged (see ingredient_normalizer)."""
from __future__ import annotations
import csv
import re
import sqlite3
from datetime import datetime, timezone

from src.config import data_path
from src.module_a.ingest.load_batch import start_load_batch, finish_load_batch
from src.module_a.normalize.ingredient_normalizer import resolve_reference_ingredient


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _split_combo(name: str) -> list[str]:
    """NLEM sometimes writes a combination as one cell, e.g.
    'Amoxicillin + Clavulanic Acid'. This is a deterministic split on '+', not
    a guess about drug identity -- each resulting token still goes through the
    normal exact/fuzzy resolution path below."""
    return [part.strip() for part in re.split(r"\s*\+\s*", name) if part.strip()]


def load_nlem(conn: sqlite3.Connection, csv_path=None) -> dict:
    csv_path = csv_path or data_path("nlem")
    rows = list(csv.DictReader(open(csv_path, newline="")))
    source_version = rows[0].get("nlem_edition") if rows else None
    batch_id = start_load_batch(conn, "nlem", source_version, str(csv_path))

    exact, queued = 0, 0
    for row in rows:
        tokens = _split_combo(row["medicine"])
        statuses = []
        matched_ids = []
        for tok in tokens:
            ingredient_id, status = resolve_reference_ingredient(
                conn, tok, "nlem", row.get("nlem_edition"), batch_id, entity_type_for_queue="nlem_ingredient"
            )
            statuses.append(status)
            matched_ids.append(ingredient_id)
        overall_status = "EXACT" if all(s == "EXACT" for s in statuses) else "QUEUED"
        if overall_status == "EXACT":
            exact += 1
        else:
            queued += 1
        conn.execute(
            """
            INSERT INTO reference_nlem
                (medicine, therapeutic_category, care_levels, nlem_edition, matched_ingredient_id,
                 match_status, source, source_version, load_batch_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (row["medicine"], row["therapeutic_category"], row["care_levels"], row["nlem_edition"],
             matched_ids[0] if len(matched_ids) == 1 else None, overall_status,
             "nlem", row.get("nlem_edition"), batch_id, _now()),
        )
    conn.commit()
    finish_load_batch(conn, batch_id, row_count=len(rows), notes=f"{exact} exact, {queued} queued")
    return {"batch_id": batch_id, "rows": len(rows), "exact": exact, "queued": queued}


def load_jan_aushadhi(conn: sqlite3.Connection, csv_path=None) -> dict:
    csv_path = csv_path or data_path("jan_aushadhi")
    rows = list(csv.DictReader(open(csv_path, newline="")))
    source_version = rows[0].get("catalog_version") if rows else None
    batch_id = start_load_batch(conn, "jan_aushadhi", source_version, str(csv_path))

    exact, queued = 0, 0
    for row in rows:
        ingredient_id, status = resolve_reference_ingredient(
            conn, row["generic_name"], "jan_aushadhi", row.get("catalog_version"), batch_id,
            entity_type_for_queue="jan_aushadhi_ingredient",
        )
        if status == "EXACT":
            exact += 1
        else:
            queued += 1
        conn.execute(
            """
            INSERT INTO reference_jan_aushadhi
                (generic_name, strength, pack, mrp_inr, catalog_version, matched_ingredient_id,
                 match_status, source, source_version, load_batch_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (row["generic_name"], row["strength"], row["pack"], float(row["mrp_inr"]), row["catalog_version"],
             ingredient_id, status, "jan_aushadhi", row.get("catalog_version"), batch_id, _now()),
        )
    conn.commit()
    finish_load_batch(conn, batch_id, row_count=len(rows), notes=f"{exact} exact, {queued} queued")
    return {"batch_id": batch_id, "rows": len(rows), "exact": exact, "queued": queued}
