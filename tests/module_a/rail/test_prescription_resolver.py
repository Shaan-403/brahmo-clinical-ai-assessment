from src.module_a.ingest.cdci_loader import load_cdci
from src.module_a.rail.prescription_resolver import resolve_prescription_item, load_seed_prescriptions


def test_resolves_unique_brand(loaded_conn):
    res = resolve_prescription_item(loaded_conn, "Dolo 650")
    assert res["status"] == "RESOLVED"
    row = loaded_conn.execute("SELECT brand_name FROM products WHERE id=?", (res["product_id"],)).fetchone()
    assert row["brand_name"] == "Dolo 650"


def test_no_match_for_unknown_brand(loaded_conn):
    assert resolve_prescription_item(loaded_conn, "Zqtrixon Forte")["status"] == "NO_MATCH"


def test_ambiguous_brand_is_not_guessed(loaded_conn):
    """'Becet 1' is 3 unrelated formulations in the real data pack
    (Sertraline / Cefixime / Aspirin) -- must never silently pick one."""
    res = resolve_prescription_item(loaded_conn, "Becet 1")
    assert res["status"] == "AMBIGUOUS"
    assert len(res["candidates"]) >= 2


def test_load_seed_prescriptions_groups_by_rx_id():
    by_rx = load_seed_prescriptions()
    assert "RX01" in by_rx
    assert len(by_rx["RX01"]) == 2
    assert by_rx["RX01"][0]["written_product"] == "Dolo 650"
    assert len(by_rx) == 10
