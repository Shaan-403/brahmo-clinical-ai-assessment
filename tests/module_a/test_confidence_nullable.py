"""Engineering decision (2026-09-27): an unresolved ingredient alias records
confidence=NULL, not 0.0 -- "not resolved" is not the same thing as "resolved
with zero confidence". See DESIGN.md D-008."""
from src.module_a.ingest.cdci_loader import load_cdci
from src.module_a.normalize.ingredient_normalizer import resolve_reference_ingredient


def test_unresolved_alias_confidence_is_null_not_zero(conn):
    load_cdci(conn)
    batch_id = conn.execute("SELECT id FROM load_batches LIMIT 1").fetchone()["id"]

    ingredient_id, status = resolve_reference_ingredient(
        conn, "Zinc Sulphate", "nlem", "NLEM 2022", batch_id, "nlem_ingredient"
    )
    assert status == "QUEUED"

    alias = conn.execute(
        "SELECT confidence FROM ingredient_aliases WHERE raw_text = 'Zinc Sulphate' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert alias["confidence"] is None


def test_resolved_alias_confidence_is_still_a_real_number(conn):
    """Guards against a NULL-everywhere regression: only unresolved rows
    should be NULL; exact/structured matches must still carry a real score."""
    load_cdci(conn)
    batch_id = conn.execute("SELECT id FROM load_batches LIMIT 1").fetchone()["id"]

    ingredient_id, status = resolve_reference_ingredient(
        conn, "Paracetamol", "nlem", "NLEM 2022", batch_id, "nlem_ingredient"
    )
    assert status == "EXACT"
    alias = conn.execute(
        "SELECT confidence FROM ingredient_aliases WHERE raw_text = 'Paracetamol' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert alias["confidence"] == 0.9


def test_no_zero_confidence_sentinel_remains_anywhere(loaded_conn):
    """After a full real-data run, no ingredient_aliases row should carry the
    old 0.0 sentinel: every row is either a genuine positive confidence
    (resolved) or NULL (unresolved)."""
    zero_conf_rows = loaded_conn.execute(
        "SELECT COUNT(*) c FROM ingredient_aliases WHERE confidence = 0.0"
    ).fetchone()["c"]
    assert zero_conf_rows == 0

    unresolved_but_scored = loaded_conn.execute(
        "SELECT COUNT(*) c FROM ingredient_aliases WHERE ingredient_id IS NULL AND confidence IS NOT NULL"
    ).fetchone()["c"]
    assert unresolved_but_scored == 0
