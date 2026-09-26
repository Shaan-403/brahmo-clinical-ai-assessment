"""Check (c): severe interaction against severe_interaction_seed.csv.

Ground truth verified directly against the real data pack: several seed
pairs (e.g. Warfarin/Amiodarone, Methotrexate/Trimethoprim, Digoxin/
Clarithromycin) have at least one ingredient that never resolves to a
canonical ingredient in this CDCI subset. Per DESIGN.md D-010, that means a
"no hit" result on this data pack is always PARTIAL_COVERAGE, never a bare
CHECKED_NO_HIT -- this system will not claim full interaction coverage while
part of the seed list is unmatchable.
"""
from src.module_a.rail.prescription_resolver import load_seed_prescriptions
from src.module_a.rail.severe_interaction import check_severe_interaction

TODAY = "2026-09-27"


def test_rx03_warfarin_azithromycin_is_a_hit(loaded_conn):
    """Warf 5 (Warfarin) + Azee 500 (Azithromycin) is an exact match for a
    seed row (SEVERE, INR elevation; bleeding) -- both ingredients are
    already canonical from CDCI, so this must resolve and HIT."""
    rows = load_seed_prescriptions()["RX03"]
    results = check_severe_interaction(loaded_conn, "RX03", rows, TODAY)
    hits = [r for r in results if r["state"] == "HIT"]
    assert len(hits) == 1
    assert hits[0]["severity"] == "SEVERE"
    assert {hits[0]["evidence"]["ingredient_a"], hits[0]["evidence"]["ingredient_b"]} == {"Warfarin", "Azithromycin"}


def test_no_known_pair_is_partial_coverage_not_clean_negative(loaded_conn):
    """RX10 (Pan 40 + Thyronorm 50: Pantoprazole + Thyroxine) matches no seed
    pair -- but because several seed rows have an unresolved ingredient
    globally, this must be PARTIAL_COVERAGE, not a falsely-confident
    CHECKED_NO_HIT."""
    rows = load_seed_prescriptions()["RX10"]
    results = check_severe_interaction(loaded_conn, "RX10", rows, TODAY)
    assert len(results) == 1
    assert results[0]["state"] == "PARTIAL_COVERAGE"
    assert "never resolved" in results[0]["evidence"]["note"].lower()


def test_unresolved_item_is_unverified_input(loaded_conn):
    rows = [{"item_no": "1", "written_product": "Zqtrixon Forte", "dose_frequency": ""}]
    results = check_severe_interaction(loaded_conn, "RX08", rows, TODAY)
    assert len(results) == 1
    assert results[0]["state"] == "UNVERIFIED_INPUT"
