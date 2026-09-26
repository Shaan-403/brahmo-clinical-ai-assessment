"""Loads seed_prescriptions_template.csv and resolves each item's free-text
written_product against the drug master.

The written_product string is untrusted input (binding law), exactly like a
pharmacy-billed name -- so it gets the SAME discipline as
pharmacy_matcher.resolve_pharmacy_item: an exact normalized-brand match that
is unique auto-resolves; zero or 2+ matches do not. Unlike pharmacy intake,
this is not persisted ingestion data (there is no seed_prescription_items
table -- a rail run is an analytical query, not a new data row), so an
unresolved item is surfaced directly in the calling check's evidence/state
rather than written to review_queue (see DESIGN.md D-013). Never fuzzy-
matched: a rail check acting on a guessed product would be exactly the
"confident wrong answer" the whole design avoids elsewhere.
"""
from __future__ import annotations
import csv
import sqlite3
from collections import OrderedDict

from src.config import data_path
from src.module_a.normalize.text import normalize_brand_key


def load_seed_prescriptions(csv_path=None) -> "OrderedDict[str, list[dict]]":
    csv_path = csv_path or data_path("seed_prescriptions")
    rows = list(csv.DictReader(open(csv_path, newline="")))
    by_rx: "OrderedDict[str, list[dict]]" = OrderedDict()
    for row in rows:
        by_rx.setdefault(row["rx_id"], []).append(row)
    return by_rx


def resolve_prescription_item(conn: sqlite3.Connection, written_product: str) -> dict:
    """Returns {"status": "RESOLVED", "product_id": int} or
    {"status": "NO_MATCH"} or {"status": "AMBIGUOUS", "candidates": [...]}."""
    key = normalize_brand_key(written_product)
    rows = conn.execute(
        "SELECT id, external_product_id, brand_name, strength_text FROM products WHERE brand_name_normalized = ?",
        (key,),
    ).fetchall()
    distinct = {r["id"]: r for r in rows}
    if len(distinct) == 1:
        (product_id,) = distinct.keys()
        return {"status": "RESOLVED", "product_id": product_id}
    if len(distinct) == 0:
        return {"status": "NO_MATCH"}
    return {
        "status": "AMBIGUOUS",
        "candidates": [
            {"product_id": r["id"], "external_product_id": r["external_product_id"],
             "brand_name": r["brand_name"], "strength_text": r["strength_text"]}
            for r in distinct.values()
        ],
    }
