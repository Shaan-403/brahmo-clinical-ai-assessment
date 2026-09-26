"""Loads pharmacy_stock.csv verbatim (untrusted real-world input), then
attempts to resolve every row against the drug master via pharmacy_matcher.

pharmacy_stock.csv has no version/date column at all -- source_version is
NULL for every row here, by design (see DESIGN.md D-007): a fake version is
never invented. The load batch's content hash (file_hash) is the identity
this loader actually keys idempotency off of, and it is documented in
gaps_register.md as the provenance substitute for this source.

Idempotent: re-running against the same file content is a no-op -- no
duplicate pharmacy_stock_items, product_resolutions, or review_queue rows.
"""
from __future__ import annotations
import csv
import sqlite3
from datetime import datetime, timezone

from src.config import data_path
from src.module_a.ingest.load_batch import start_load_batch, finish_load_batch, compute_file_hash, find_completed_batch
from src.module_a.normalize.pharmacy_matcher import resolve_pharmacy_item

SOURCE_NAME = "pharmacy_stock"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_pharmacy_stock(conn: sqlite3.Connection, csv_path=None) -> dict:
    csv_path = csv_path or data_path("pharmacy_stock")
    file_hash = compute_file_hash(csv_path)

    existing = find_completed_batch(conn, SOURCE_NAME, file_hash)
    if existing:
        rows = conn.execute(
            "SELECT COUNT(*) c FROM pharmacy_stock_items WHERE load_batch_id=?", (existing["id"],)
        ).fetchone()["c"]
        auto_resolved = conn.execute(
            """
            SELECT COUNT(*) c FROM product_resolutions pr
            JOIN pharmacy_stock_items psi ON psi.id = pr.entity_id
            WHERE psi.load_batch_id = ? AND pr.status = 'AUTO_RESOLVED'
            """,
            (existing["id"],),
        ).fetchone()["c"]
        return {"batch_id": existing["id"], "rows": rows, "auto_resolved": auto_resolved,
                "queued": rows - auto_resolved, "skipped": True}

    rows = list(csv.DictReader(open(csv_path, newline="")))
    batch_id = start_load_batch(conn, SOURCE_NAME, None, str(csv_path), file_hash)

    auto_resolved, queued = 0, 0
    for row in rows:
        cur = conn.execute(
            """
            INSERT INTO pharmacy_stock_items
                (item_name_as_billed, qty_units, mrp_inr, batch, expiry, source, source_version,
                 load_batch_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (row["item_name_as_billed"], int(row["qty_units"]), float(row["mrp_inr"]),
             row["batch"], row["expiry"], SOURCE_NAME, None, batch_id, _now()),
        )
        item_id = cur.lastrowid
        result = resolve_pharmacy_item(conn, item_id, row["item_name_as_billed"])
        if result["status"] == "AUTO_RESOLVED":
            auto_resolved += 1
        else:
            queued += 1
    conn.commit()

    finish_load_batch(conn, batch_id, row_count=len(rows), notes=f"{auto_resolved} auto-resolved, {queued} queued")
    return {"batch_id": batch_id, "rows": len(rows), "auto_resolved": auto_resolved, "queued": queued, "skipped": False}
