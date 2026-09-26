"""Loads cdci_drug_subset.csv into products + product_ingredients.

FDC decomposition here is a structured parse: CDCI already declares up to 3
(ingredient, strength) pairs per row. That parse is deterministic and gets
confidence=1.0 / method='structured_source_field' — no matching is being
performed, the source is simply being reshaped into normalized rows.
"""
from __future__ import annotations
import csv
import json
import sqlite3
from datetime import datetime, timezone

from src.config import data_path
from src.module_a.ingest.load_batch import start_load_batch, finish_load_batch
from src.module_a.normalize.ingredient_normalizer import get_or_create_canonical_ingredient
from src.module_a.normalize.text import normalize_brand_key

SOURCE_NAME = "cdci"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_cdci(conn: sqlite3.Connection, csv_path=None) -> dict:
    csv_path = csv_path or data_path("cdci")
    rows = list(csv.DictReader(open(csv_path, newline="")))
    if not rows:
        raise ValueError(f"{csv_path} is empty")
    source_version = rows[0]["source_version"]

    batch_id = start_load_batch(conn, SOURCE_NAME, source_version, str(csv_path))

    fdc_count = 0
    for row in rows:
        cur = conn.execute(
            """
            INSERT INTO products
                (external_product_id, brand_name, brand_name_normalized, manufacturer, dose_form,
                 strength_text, source, source_version, effective_from, load_batch_id, raw_row_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["product_id"], row["brand_name"], normalize_brand_key(row["brand_name"]),
                row["manufacturer"], row["dose_form"], row["strength_text"],
                SOURCE_NAME, source_version, row["effective_from"], batch_id,
                json.dumps(row), _now(),
            ),
        )
        product_id = cur.lastrowid

        n_ingredients = 0
        for position in (1, 2, 3):
            ing_raw = row.get(f"ingredient_{position}", "").strip()
            if not ing_raw:
                continue
            n_ingredients += 1
            strength_raw = row.get(f"strength_{position}_mg", "").strip()
            strength_mg = float(strength_raw) if strength_raw else None
            ingredient_id = get_or_create_canonical_ingredient(conn, ing_raw, SOURCE_NAME, source_version, batch_id)
            conn.execute(
                """
                INSERT INTO product_ingredients
                    (product_id, ingredient_id, position, strength_mg, strength_raw,
                     confidence, method, source, source_version, load_batch_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (product_id, ingredient_id, position, strength_mg, strength_raw,
                 1.0, "structured_source_field", SOURCE_NAME, source_version, batch_id, _now()),
            )
        if n_ingredients >= 2:
            fdc_count += 1
    conn.commit()

    finish_load_batch(conn, batch_id, row_count=len(rows), notes=f"{fdc_count} FDC (2+ ingredient) products")
    return {"batch_id": batch_id, "products": len(rows), "fdc_products": fdc_count}
