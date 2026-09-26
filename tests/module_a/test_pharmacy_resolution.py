import json

from src.module_a.ingest.cdci_loader import load_cdci
from src.module_a.normalize.pharmacy_matcher import resolve_pharmacy_item


def _insert_item(conn, name):
    cur = conn.execute(
        """
        INSERT INTO pharmacy_stock_items
            (item_name_as_billed, qty_units, mrp_inr, batch, expiry, source, source_version, load_batch_id, created_at)
        VALUES (?, 10, 100.0, 'B1', '2027-01', 'pharmacy_stock', NULL, 1, datetime('now'))
        """,
        (name,),
    )
    conn.commit()
    return cur.lastrowid


def test_unique_brand_match_auto_resolves(conn):
    """'RADOL STRIP' cleans to 'RADOL', which is a unique brand in the
    provided CDCI subset (CD2279, Iron (Ferrous Ascorbate) 500mg)."""
    load_cdci(conn)
    item_id = _insert_item(conn, "RADOL STRIP")
    result = resolve_pharmacy_item(conn, item_id, "RADOL STRIP")
    assert result["status"] == "AUTO_RESOLVED"
    product = conn.execute("SELECT external_product_id FROM products WHERE id = ?", (result["product_id"],)).fetchone()
    assert product["external_product_id"] == "CD2279"


def test_ambiguous_brand_is_queued_never_guessed(conn):
    """'MIZITH-FORTE STRIP' cleans to 'MIZITH FORTE', which matches THREE
    unrelated CDCI products (two different Montelukast rows plus a
    Nitrofurantoin row). Auto-picking any one of these would be a silent,
    potentially dangerous, wrong guess -- must be queued instead."""
    load_cdci(conn)
    item_id = _insert_item(conn, "MIZITH-FORTE STRIP")
    result = resolve_pharmacy_item(conn, item_id, "MIZITH-FORTE STRIP")
    assert result["status"] == "QUEUED_FOR_REVIEW"
    assert result["reason"] == "AMBIGUOUS_BRAND_MULTIPLE_FORMULATIONS"
    assert result["n_candidates"] >= 2

    queue_row = conn.execute(
        "SELECT * FROM review_queue WHERE entity_type='pharmacy_stock_item' AND entity_id=?", (item_id,)
    ).fetchone()
    assert queue_row["reason_code"] == "AMBIGUOUS_BRAND_MULTIPLE_FORMULATIONS"
    candidates = json.loads(queue_row["candidates_json"])["candidates"]
    ingredient_texts = {c["strength_text"] for c in candidates}
    assert len(ingredient_texts) >= 2, "candidates must be genuinely different formulations, evidencing the ambiguity"

    resolution_row = conn.execute(
        "SELECT resolved_product_id, status FROM product_resolutions WHERE entity_id=?", (item_id,)
    ).fetchone()
    assert resolution_row["status"] == "QUEUED_FOR_REVIEW"
    assert resolution_row["resolved_product_id"] is None, "must not silently pick a product_id"


def test_no_exact_match_still_queued_even_with_high_fuzzy_score(conn):
    """'CMOX TAB 10'S' has no exact normalized-brand match anywhere in CDCI
    (confirmed by direct query against the loaded data). Fuzzy candidates may
    exist, but per design (D-002) a fuzzy match is NEVER auto-accepted,
    however high the score."""
    load_cdci(conn)
    item_id = _insert_item(conn, "CMOX TAB 10'S")
    result = resolve_pharmacy_item(conn, item_id, "CMOX TAB 10'S")
    assert result["status"] == "QUEUED_FOR_REVIEW"
    assert result["reason"] == "NO_EXACT_BRAND_MATCH"


def test_no_pharmacy_row_is_ever_dropped(loaded_conn):
    """Every pharmacy_stock_items row must have exactly one product_resolutions
    row (auto-resolved or queued) -- never zero, never silently skipped."""
    total_items = loaded_conn.execute("SELECT COUNT(*) c FROM pharmacy_stock_items").fetchone()["c"]
    total_resolutions = loaded_conn.execute("SELECT COUNT(*) c FROM product_resolutions").fetchone()["c"]
    assert total_items == 783
    assert total_resolutions == total_items


def test_full_pharmacy_run_matches_known_data_shape(loaded_conn):
    """Pins the exact split found by manual analysis of the provided file:
    209 unique exact matches, 554 ambiguous exact matches, 20 with no exact
    match at all (554 + 20 = 574 queued)."""
    auto = loaded_conn.execute(
        "SELECT COUNT(*) c FROM product_resolutions WHERE status='AUTO_RESOLVED'"
    ).fetchone()["c"]
    queued = loaded_conn.execute(
        "SELECT COUNT(*) c FROM product_resolutions WHERE status='QUEUED_FOR_REVIEW'"
    ).fetchone()["c"]
    assert auto == 209
    assert queued == 574


def test_no_silent_auto_resolution_of_a_known_ambiguous_case(loaded_conn):
    """Regression guard for the confirmed MIZITH-FORTE case (3 unrelated
    candidates: two different Montelukast rows and a Nitrofurantoin row) plus
    the general invariant: every AUTO_RESOLVED row must have used
    method='exact_normalized_brand_unique', meaning exactly one exact
    candidate existed. No exception, however the item was named."""
    row = loaded_conn.execute(
        """
        SELECT pr.status FROM pharmacy_stock_items psi
        JOIN product_resolutions pr ON pr.entity_id = psi.id
        WHERE psi.item_name_as_billed = 'MIZITH-FORTE STRIP'
        """
    ).fetchone()
    assert row is not None
    assert row["status"] == "QUEUED_FOR_REVIEW"

    bad = loaded_conn.execute(
        "SELECT id FROM product_resolutions WHERE status='AUTO_RESOLVED' AND method != 'exact_normalized_brand_unique'"
    ).fetchall()
    assert bad == []
