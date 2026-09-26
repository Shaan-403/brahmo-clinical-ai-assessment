"""Loads pharmacy_stock.csv verbatim (untrusted real-world input), then
attempts to resolve every row against the drug master via pharmacy_matcher."""
from __future__ import annotations
import csv
import sqlite3
from datetime import datetime, timezone

from src.config import data_path
from src.module_a.ingest.load_batch import start_load_batch, finish_load_batch
from src.module_a.normalize.pharmacy_matcher import resolve_pharmacy_item

SOURCE_NAME = "pharmacy_stock"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_pharmacy_stock(conn: sqlite3.Connection, csv_path=None) -> dict:
    csv_path = csv_path or data_path("pharmacy_stock")
    rows = list(csv.DictReader(open(csv_path, newline="")))
    batch_id = start_load_batch(conn, SOURCE_NAME, None, str(csv_path))

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
    return {"batch_id": batch_id, "rows": len(rows), "auto_resolved": auto_resolved, "queued": queued}
