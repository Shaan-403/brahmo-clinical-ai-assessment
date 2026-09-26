import json

from src.module_a.ingest.cdci_loader import load_cdci
from src.module_a.normalize.ingredient_normalizer import normalize_key, resolve_reference_ingredient


def test_normalize_key_collapses_case_and_whitespace():
    assert normalize_key("  Paracetamol  ") == "paracetamol"
    assert normalize_key("PARACETAMOL") == normalize_key("paracetamol")


def test_exact_reference_match_auto_resolves(conn):
    load_cdci(conn)  # establishes "Paracetamol" as canonical
    batch_id = conn.execute("SELECT id FROM load_batches LIMIT 1").fetchone()["id"]
    ingredient_id, status = resolve_reference_ingredient(
        conn, "Paracetamol", "nlem", "NLEM 2022", batch_id, "nlem_ingredient"
    )
    assert status == "EXACT"
    assert ingredient_id is not None
    # no review_queue entry should have been created for a confident match
    open_count = conn.execute("SELECT COUNT(*) c FROM review_queue WHERE entity_type='nlem_ingredient'").fetchone()["c"]
    assert open_count == 0


def test_unknown_ingredient_is_queued_never_merged(conn):
    load_cdci(conn)
    batch_id = conn.execute("SELECT id FROM load_batches LIMIT 1").fetchone()["id"]
    ingredient_id, status = resolve_reference_ingredient(
        conn, "Zinc Sulphate", "nlem", "NLEM 2022", batch_id, "nlem_ingredient"
    )
    assert status == "QUEUED"
    assert ingredient_id is None, "an uncertain mapping must never be silently resolved"
    item = conn.execute(
        "SELECT * FROM review_queue WHERE entity_type='nlem_ingredient' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert item is not None
    assert item["reason_code"] in ("AMBIGUOUS_INGREDIENT_ALIAS", "NO_CANDIDATE_INGREDIENT_ALIAS")
    candidates = json.loads(item["candidates_json"])
    assert candidates["raw_text"] == "Zinc Sulphate"
