"""Cross-cutting checks against the acceptance gates in 01_CANDIDATE_BRIEF.md
section 5 (as far as they apply to this normalization/ingestion slice)."""


def test_g3_zero_silent_resolutions(loaded_conn):
    """G3: every ambiguous mapping appears in the review queue with a reason
    code -- i.e. no pharmacy row was auto-resolved despite having 2+ exact
    brand candidates, and every queued row has a non-null reason_code."""
    bad = loaded_conn.execute(
        """
        SELECT pr.id FROM product_resolutions pr
        WHERE pr.status = 'AUTO_RESOLVED'
          AND pr.method != 'exact_normalized_brand_unique'
        """
    ).fetchall()
    assert bad == [], "only a genuinely unique exact match may auto-resolve"

    unreasoned = loaded_conn.execute(
        "SELECT id FROM review_queue WHERE reason_code IS NULL OR reason_code = ''"
    ).fetchall()
    assert unreasoned == []


def test_g5_full_provenance_on_products_and_ingredients(loaded_conn):
    """G5: 100% provenance on data rows -- every products/product_ingredients/
    ingredient_aliases/pharmacy_stock_items row traces to source + version +
    a valid load_batches row."""
    for table, needs_version in (
        ("products", True),
        ("product_ingredients", False),
        ("pharmacy_stock_items", False),
    ):
        rows = loaded_conn.execute(f"SELECT * FROM {table}").fetchall()
        assert rows, f"{table} should not be empty"
        for r in rows:
            assert r["source"], f"{table} row {r['id']} missing source"
            assert r["load_batch_id"] is not None, f"{table} row {r['id']} missing load_batch_id"
            batch = loaded_conn.execute(
                "SELECT id FROM load_batches WHERE id = ?", (r["load_batch_id"],)
            ).fetchone()
            assert batch is not None, f"{table} row {r['id']} references a nonexistent load batch"
            if needs_version:
                assert r["source_version"], f"{table} row {r['id']} missing source_version"


def test_load_batches_are_all_marked_complete(loaded_conn):
    incomplete = loaded_conn.execute(
        "SELECT * FROM load_batches WHERE status != 'COMPLETE'"
    ).fetchall()
    assert incomplete == []


def test_review_queue_reason_codes_are_all_known(loaded_conn):
    from src.module_a.review_queue.queue import VALID_REASON_CODES
    rows = loaded_conn.execute("SELECT DISTINCT reason_code FROM review_queue").fetchall()
    for r in rows:
        assert r["reason_code"] in VALID_REASON_CODES
