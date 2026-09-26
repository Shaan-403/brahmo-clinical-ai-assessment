"""Engineering decision (2026-09-27): cross-check CDCI's structured
ingredient_N/strength_N_mg columns against its own free-text strength_text
field. A mismatch (or an unparseable strength_text) must be surfaced to the
review queue, never silently trusted either way. See DESIGN.md D-006."""
import csv
import json

from src.module_a.ingest.cdci_loader import load_cdci

HEADER = ["product_id", "brand_name", "manufacturer", "dose_form", "strength_text", "source",
          "source_version", "effective_from", "ingredient_1", "strength_1_mg",
          "ingredient_2", "strength_2_mg", "ingredient_3", "strength_3_mg"]


def _write_csv(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        for row in rows:
            w.writerow(row)


def test_real_data_pack_has_zero_mismatches(conn):
    """Pinned against the actual provided cdci_drug_subset.csv: the free-text
    strength_text field was generated consistently with the structured
    columns for all 2,000 rows, so this check should find nothing to flag."""
    load_cdci(conn)
    mismatches = conn.execute(
        "SELECT COUNT(*) c FROM review_queue WHERE reason_code = 'STRENGTH_TEXT_STRUCTURED_MISMATCH'"
    ).fetchone()["c"]
    assert mismatches == 0


def test_matching_fdc_is_not_flagged(conn, tmp_path):
    path = tmp_path / "cdci.csv"
    _write_csv(path, [
        ["CD9001", "Testorest", "TestPharma", "Tablet",
         "Paracetamol 500 mg + Chlorpheniramine 2 mg", "CDCI-TEST", "2026-01-01", "2026-01-01",
         "Paracetamol", "500", "Chlorpheniramine", "2", "", ""],
    ])
    load_cdci(conn, csv_path=path)
    flagged = conn.execute(
        "SELECT COUNT(*) c FROM review_queue WHERE reason_code = 'STRENGTH_TEXT_STRUCTURED_MISMATCH'"
    ).fetchone()["c"]
    assert flagged == 0


def test_order_independent_match_is_not_flagged(conn, tmp_path):
    """strength_text lists ingredients in a different order than the
    structured columns -- same underlying facts, so this should NOT be
    treated as a mismatch (order alone isn't the thing being verified)."""
    path = tmp_path / "cdci.csv"
    _write_csv(path, [
        ["CD9002", "Testorest2", "TestPharma", "Tablet",
         "Chlorpheniramine 2 mg + Paracetamol 500 mg",  # reversed order vs. structured columns below
         "CDCI-TEST", "2026-01-01", "2026-01-01",
         "Paracetamol", "500", "Chlorpheniramine", "2", "", ""],
    ])
    load_cdci(conn, csv_path=path)
    flagged = conn.execute(
        "SELECT COUNT(*) c FROM review_queue WHERE reason_code = 'STRENGTH_TEXT_STRUCTURED_MISMATCH'"
    ).fetchone()["c"]
    assert flagged == 0


def test_strength_value_mismatch_is_flagged_not_silently_trusted(conn, tmp_path):
    path = tmp_path / "cdci.csv"
    _write_csv(path, [
        ["CD9003", "Testorest3", "TestPharma", "Tablet",
         "Paracetamol 999 mg",  # disagrees with the structured column below (500)
         "CDCI-TEST", "2026-01-01", "2026-01-01",
         "Paracetamol", "500", "", "", "", ""],
    ])
    load_cdci(conn, csv_path=path)

    product = conn.execute("SELECT id FROM products WHERE external_product_id = 'CD9003'").fetchone()
    row = conn.execute(
        "SELECT * FROM review_queue WHERE entity_type='product' AND entity_id=? AND reason_code='STRENGTH_TEXT_STRUCTURED_MISMATCH'",
        (product["id"],),
    ).fetchone()
    assert row is not None
    details = json.loads(row["candidates_json"])
    assert details["parsed_from_strength_text"] == [["Paracetamol", 999.0]]
    assert details["structured_pairs"] == [["Paracetamol", 500.0]]

    # The structured columns are still what's loaded -- the review queue entry
    # is what surfaces the disagreement, not a silent override of either side.
    stored = conn.execute(
        "SELECT strength_mg FROM product_ingredients WHERE product_id = ?", (product["id"],)
    ).fetchone()
    assert stored["strength_mg"] == 500.0


def test_unparseable_strength_text_is_flagged(conn, tmp_path):
    path = tmp_path / "cdci.csv"
    _write_csv(path, [
        ["CD9004", "Testorest4", "TestPharma", "Tablet",
         "Paracetamol five hundred milligrams",  # doesn't match "<name> <number> mg"
         "CDCI-TEST", "2026-01-01", "2026-01-01",
         "Paracetamol", "500", "", "", "", ""],
    ])
    load_cdci(conn, csv_path=path)

    product = conn.execute("SELECT id FROM products WHERE external_product_id = 'CD9004'").fetchone()
    row = conn.execute(
        "SELECT * FROM review_queue WHERE entity_type='product' AND entity_id=? AND reason_code='STRENGTH_TEXT_STRUCTURED_MISMATCH'",
        (product["id"],),
    ).fetchone()
    assert row is not None
    assert "did not parse" in json.loads(row["candidates_json"])["issue"]


def test_ingredient_count_mismatch_is_flagged(conn, tmp_path):
    """strength_text names only 1 ingredient but the structured columns
    declare 2 -- must be flagged, not silently accepted as 'close enough'."""
    path = tmp_path / "cdci.csv"
    _write_csv(path, [
        ["CD9005", "Testorest5", "TestPharma", "Tablet",
         "Paracetamol 500 mg",  # missing the second ingredient entirely
         "CDCI-TEST", "2026-01-01", "2026-01-01",
         "Paracetamol", "500", "Chlorpheniramine", "2", "", ""],
    ])
    load_cdci(conn, csv_path=path)
    product = conn.execute("SELECT id FROM products WHERE external_product_id = 'CD9005'").fetchone()
    row = conn.execute(
        "SELECT id FROM review_queue WHERE entity_type='product' AND entity_id=? AND reason_code='STRENGTH_TEXT_STRUCTURED_MISMATCH'",
        (product["id"],),
    ).fetchone()
    assert row is not None
