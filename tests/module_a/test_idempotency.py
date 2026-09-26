"""Engineering decision (2026-09-27): ingestion must be idempotent -- re-running
against the same source files must not duplicate products, pharmacy records,
aliases, or review items. See DESIGN.md D-006."""
from src.module_a.ingest.cdci_loader import load_cdci
from src.module_a.ingest.reference_loader import load_nlem, load_jan_aushadhi
from src.module_a.ingest.pharmacy_loader import load_pharmacy_stock


def _count(conn, table):
    return conn.execute(f"SELECT COUNT(*) c FROM {table}").fetchone()["c"]


def test_cdci_load_twice_does_not_duplicate_anything(conn):
    first = load_cdci(conn)
    assert first["skipped"] is False
    counts_after_first = {t: _count(conn, t) for t in
                           ("products", "product_ingredients", "ingredients", "ingredient_aliases", "load_batches")}

    second = load_cdci(conn)
    assert second["skipped"] is True
    assert second["products"] == first["products"]
    assert second["fdc_products"] == first["fdc_products"]

    counts_after_second = {t: _count(conn, t) for t in counts_after_first}
    assert counts_after_second == counts_after_first, "second run must not add or change any rows"


def test_pharmacy_load_twice_does_not_duplicate_anything(conn):
    load_cdci(conn)  # products must exist for resolution to have something to match against
    first = load_pharmacy_stock(conn)
    assert first["skipped"] is False
    counts_after_first = {t: _count(conn, t) for t in
                           ("pharmacy_stock_items", "product_resolutions", "review_queue", "load_batches")}

    second = load_pharmacy_stock(conn)
    assert second["skipped"] is True
    assert second["rows"] == first["rows"]
    assert second["auto_resolved"] == first["auto_resolved"]
    assert second["queued"] == first["queued"]

    counts_after_second = {t: _count(conn, t) for t in counts_after_first}
    assert counts_after_second == counts_after_first


def test_nlem_load_twice_does_not_duplicate_anything(conn):
    load_cdci(conn)
    first = load_nlem(conn)
    assert first["skipped"] is False
    before = {t: _count(conn, t) for t in ("reference_nlem", "ingredient_aliases", "review_queue", "load_batches")}

    second = load_nlem(conn)
    assert second["skipped"] is True
    assert second == {**first, "skipped": True}

    after = {t: _count(conn, t) for t in before}
    assert after == before


def test_jan_aushadhi_load_twice_does_not_duplicate_anything(conn):
    load_cdci(conn)
    first = load_jan_aushadhi(conn)
    assert first["skipped"] is False
    before = {t: _count(conn, t) for t in ("reference_jan_aushadhi", "ingredient_aliases", "load_batches")}

    second = load_jan_aushadhi(conn)
    assert second["skipped"] is True

    after = {t: _count(conn, t) for t in before}
    assert after == before


def test_full_pipeline_run_twice_is_stable(conn):
    """The end-to-end scenario a reviewer is most likely to actually try:
    running the fresh-machine setup instructions twice in a row."""
    load_cdci(conn)
    load_nlem(conn)
    load_jan_aushadhi(conn)
    load_pharmacy_stock(conn)
    before = {t: _count(conn, t) for t in (
        "products", "product_ingredients", "ingredients", "ingredient_aliases",
        "pharmacy_stock_items", "product_resolutions", "review_queue",
        "reference_nlem", "reference_jan_aushadhi", "load_batches",
    )}

    load_cdci(conn)
    load_nlem(conn)
    load_jan_aushadhi(conn)
    load_pharmacy_stock(conn)
    after = {t: _count(conn, t) for t in before}

    assert after == before
    open_review = conn.execute("SELECT COUNT(*) c FROM review_queue WHERE status='OPEN'").fetchone()["c"]
    assert open_review == 577  # pinned to the known shape of this data pack (see test_pharmacy_resolution.py)


def test_different_content_is_not_treated_as_already_loaded(conn, tmp_path):
    """Idempotency must key off file CONTENT, not just source name -- loading
    a genuinely different file for the same source must not be skipped."""
    import csv
    header = ["product_id", "brand_name", "manufacturer", "dose_form", "strength_text", "source",
              "source_version", "effective_from", "ingredient_1", "strength_1_mg",
              "ingredient_2", "strength_2_mg", "ingredient_3", "strength_3_mg"]

    def write_csv(path, product_id, version):
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerow([product_id, "Testol", "TestPharma", "Tablet", "Paracetamol 500 mg",
                        "CDCI-TEST", version, "2026-01-01", "Paracetamol", "500", "", "", "", ""])

    v1 = tmp_path / "cdci_v1.csv"
    v2 = tmp_path / "cdci_v2.csv"
    write_csv(v1, "CDX1", "2026-01-01")
    write_csv(v2, "CDX2", "2026-02-01")  # different product_id -> different content -> different hash

    r1 = load_cdci(conn, csv_path=v1)
    assert r1["skipped"] is False
    r2 = load_cdci(conn, csv_path=v2)
    assert r2["skipped"] is False, "different file content must never be treated as already-loaded"
    assert _count(conn, "products") == 2
