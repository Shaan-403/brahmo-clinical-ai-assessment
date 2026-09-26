"""Severe-interaction seed ingestion. Ingredient names go through the same
exact-match-only discipline as any other untrusted secondary source -- see
DESIGN.md D-010."""
from src.module_a.ingest.cdci_loader import load_cdci
from src.module_a.ingest.interaction_loader import load_severe_interactions


def test_loads_all_rows_and_is_idempotent(conn):
    load_cdci(conn)
    first = load_severe_interactions(conn)
    assert first["skipped"] is False
    assert first["rows"] == 15

    second = load_severe_interactions(conn)
    assert second["skipped"] is True
    assert second["rows"] == 15
    assert conn.execute("SELECT COUNT(*) c FROM severe_interactions").fetchone()["c"] == 15


def test_warfarin_azithromycin_pair_resolves_against_cdci_vocabulary(conn):
    """Both ingredients are already canonical from CDCI (Warf 5, Azee 500) --
    this pair must auto-resolve via exact match, not get queued."""
    load_cdci(conn)
    load_severe_interactions(conn)
    row = conn.execute(
        "SELECT * FROM severe_interactions WHERE ingredient_a_raw='Warfarin' AND ingredient_b_raw='Azithromycin'"
    ).fetchone()
    assert row["ingredient_a_id"] is not None
    assert row["ingredient_b_id"] is not None


def test_an_unresolvable_ingredient_is_queued_not_silently_linked(conn):
    """An interaction-seed ingredient name that doesn't exactly match anything
    in the canonical registry must be queued for review and left NULL, never
    guessed at via fuzzy matching (no fuzzy-auto-accept tier exists anywhere
    in this codebase -- DESIGN.md D-002)."""
    load_cdci(conn)
    result = load_severe_interactions(conn)
    unresolved_rows = conn.execute(
        "SELECT * FROM severe_interactions WHERE ingredient_a_id IS NULL OR ingredient_b_id IS NULL"
    ).fetchall()
    assert result["unresolved"] == len(unresolved_rows)
    for row in unresolved_rows:
        queued = conn.execute(
            "SELECT * FROM review_queue WHERE entity_type='severe_interaction_ingredient'"
        ).fetchall()
        assert len(queued) > 0
