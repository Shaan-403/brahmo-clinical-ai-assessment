"""Fresh-machine entry point: applies migrations, then ingests every Module A
source in dependency order (CDCI first, since it defines the canonical
ingredient vocabulary; reference sources and pharmacy stock after).

Idempotent: running this twice against unchanged source files performs no
duplicate inserts -- each loader detects it via load_batches.file_hash and
reports skipped=True (see DESIGN.md D-006)."""
from __future__ import annotations
import sys

from src.db.connection import get_connection, migrate
from src.module_a.ingest.cdci_loader import load_cdci
from src.module_a.ingest.reference_loader import load_nlem, load_jan_aushadhi
from src.module_a.ingest.pharmacy_loader import load_pharmacy_stock


def _tag(result: dict) -> str:
    return " (skipped, already loaded)" if result.get("skipped") else ""


def main() -> None:
    conn = get_connection()
    applied = migrate(conn)
    print(f"Applied {len(applied)} migration(s): {applied or '(none pending)'}")

    cdci_result = load_cdci(conn)
    print(f"CDCI: {cdci_result['products']} products loaded, {cdci_result['fdc_products']} are FDCs (2+ ingredients)"
          f"{_tag(cdci_result)}")

    nlem_result = load_nlem(conn)
    print(f"NLEM: {nlem_result['rows']} rows, {nlem_result['exact']} exact-matched, {nlem_result['queued']} queued"
          f"{_tag(nlem_result)}")

    ja_result = load_jan_aushadhi(conn)
    print(f"Jan Aushadhi: {ja_result['rows']} rows, {ja_result['exact']} exact-matched, {ja_result['queued']} queued"
          f"{_tag(ja_result)}")

    stock_result = load_pharmacy_stock(conn)
    print(f"Pharmacy stock: {stock_result['rows']} rows, "
          f"{stock_result['auto_resolved']} auto-resolved, {stock_result['queued']} queued for review"
          f"{_tag(stock_result)}")

    open_review_count = conn.execute("SELECT COUNT(*) AS c FROM review_queue WHERE status='OPEN'").fetchone()["c"]
    print(f"Review queue: {open_review_count} open items")
    conn.close()


if __name__ == "__main__":
    sys.exit(main())
