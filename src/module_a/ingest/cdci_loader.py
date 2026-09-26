"""Loads cdci_drug_subset.csv into products + product_ingredients.

FDC decomposition here is a structured parse: CDCI already declares up to 3
(ingredient, strength) pairs per row. That parse is deterministic and gets
confidence=1.0 / method='structured_source_field' -- no matching is being
performed, the source is simply being reshaped into normalized rows.

That structured parse is cross-checked against the row's own free-text
strength_text field (parsed independently via
src.module_a.normalize.strength_text). A mismatch -- or a strength_text that
doesn't even parse -- is surfaced to the review queue rather than silently
trusting either side (see DESIGN.md D-006). The structured columns remain
what's loaded into product_ingredients either way; the review queue entry is
what makes the disagreement visible for a human to resolve.

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
from src.module_a.normalize.ingredient_normalizer import get_or_create_canonical_ingredient
from src.module_a.normalize.text import normalize_brand_key
from src.module_a.normalize.strength_text import parse_strength_text, as_comparable_multiset
from src.module_a.review_queue.queue import add_review_item

SOURCE_NAME = "cdci"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fdc_count_for_batch(conn: sqlite3.Connection, batch_id: int) -> int:
    return conn.execute(
        """
        SELECT COUNT(*) c FROM (
            SELECT product_id FROM product_ingredients
            WHERE load_batch_id = ? GROUP BY product_id HAVING COUNT(*) >= 2
        )
        """,
        (batch_id,),
    ).fetchone()["c"]


def _check_strength_text_consistency(conn: sqlite3.Connection, product_id: int, external_product_id: str,
                                      brand_name: str, strength_text: str,
                                      structured_pairs: list[tuple[str, float]]) -> None:
    parsed = parse_strength_text(strength_text)
    if parsed is None:
        add_review_item(conn, "product", product_id, "STRENGTH_TEXT_STRUCTURED_MISMATCH", {
            "external_product_id": external_product_id, "brand_name": brand_name,
            "strength_text": strength_text, "structured_pairs": structured_pairs,
            "issue": "strength_text did not parse into <ingredient> <number> mg segments",
        })
        return
    if as_comparable_multiset(parsed) != as_comparable_multiset(structured_pairs):
        add_review_item(conn, "product", product_id, "STRENGTH_TEXT_STRUCTURED_MISMATCH", {
            "external_product_id": external_product_id, "brand_name": brand_name,
            "strength_text": strength_text, "parsed_from_strength_text": parsed,
            "structured_pairs": structured_pairs,
            "issue": "strength_text disagrees with the structured ingredient_N/strength_N_mg columns",
        })


def load_cdci(conn: sqlite3.Connection, csv_path=None) -> dict:
    csv_path = csv_path or data_path("cdci")
    file_hash = compute_file_hash(csv_path)

    existing = find_completed_batch(conn, SOURCE_NAME, file_hash)
    if existing:
        products = conn.execute(
            "SELECT COUNT(*) c FROM products WHERE load_batch_id = ?", (existing["id"],)
        ).fetchone()["c"]
        return {"batch_id": existing["id"], "products": products,
                "fdc_products": _fdc_count_for_batch(conn, existing["id"]), "skipped": True}

    rows = list(csv.DictReader(open(csv_path, newline="")))
    if not rows:
        raise ValueError(f"{csv_path} is empty")
    source_version = rows[0]["source_version"]

    batch_id = start_load_batch(conn, SOURCE_NAME, source_version, str(csv_path), file_hash)

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

        structured_pairs = []
        n_ingredients = 0
        for position in (1, 2, 3):
            ing_raw = row.get(f"ingredient_{position}", "").strip()
            if not ing_raw:
                continue
            n_ingredients += 1
            strength_raw = row.get(f"strength_{position}_mg", "").strip()
            strength_mg = float(strength_raw) if strength_raw else None
            structured_pairs.append((ing_raw, strength_mg))
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

        _check_strength_text_consistency(conn, product_id, row["product_id"], row["brand_name"],
                                          row["strength_text"], structured_pairs)
    conn.commit()

    finish_load_batch(conn, batch_id, row_count=len(rows), notes=f"{fdc_count} FDC (2+ ingredient) products")
    return {"batch_id": batch_id, "products": len(rows), "fdc_products": fdc_count, "skipped": False}
