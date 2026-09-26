"""Check (a)+(d): duplicate active ingredient, with cumulative daily total as
evidence. Engineering decisions under test: duplication (not magnitude)
triggers the HIT; no dose-limit threshold is ever applied; an uninterpretable
frequency (e.g. "SOS") contributes an unknown, never a silent zero, to the
total; an unresolved item degrades a clean result to PARTIAL_COVERAGE rather
than a confident (and possibly wrong) CHECKED_NO_HIT."""
from src.module_a.rail.prescription_resolver import load_seed_prescriptions
from src.module_a.rail.duplicate_ingredient import check_duplicate_ingredient

AS_OF = "2026-09-27"


def _rows(loaded_conn, rx_id):
    return load_seed_prescriptions()[rx_id]


def test_rx01_dolo650_plus_sinarest_is_a_full_hit_with_precise_total(loaded_conn):
    """Dolo 650 (Paracetamol 650mg, 1-0-1x5d) + Sinarest (Paracetamol 500mg,
    1-0-1x5d): both frequencies parse cleanly, so the cumulative total must be
    exact and not marked partial. 650*2 + 500*2 = 2300mg/day paracetamol."""
    results = check_duplicate_ingredient(loaded_conn, "RX01", _rows(loaded_conn, "RX01"), AS_OF)
    assert len(results) == 1
    r = results[0]
    assert r["state"] == "HIT"
    assert r["evidence"]["ingredient"] == "Paracetamol"
    assert r["evidence"]["cumulative_daily_mg"] == 2300
    assert r["evidence"]["cumulative_is_partial"] is False
    assert len(r["evidence"]["contributing_items"]) == 2


def test_rx07_calpol_crocin_hit_with_partial_total_due_to_sos(loaded_conn):
    """Calpol 650 (1-1-1x3d, parses to 3/day) + Crocin 650 (SOS, unparseable):
    still a HIT on duplication alone, but the cumulative total must be marked
    partial and must NOT silently treat Crocin's contribution as zero."""
    results = check_duplicate_ingredient(loaded_conn, "RX07", _rows(loaded_conn, "RX07"), AS_OF)
    assert len(results) == 1
    r = results[0]
    assert r["state"] == "HIT"
    assert r["evidence"]["ingredient"] == "Paracetamol"
    assert r["evidence"]["cumulative_is_partial"] is True
    assert r["evidence"]["cumulative_daily_mg"] == 1950  # only Calpol's 650*3 -- Crocin excluded, not zeroed
    excluded = r["evidence"]["items_excluded_from_total_due_to_unparseable_frequency"]
    assert len(excluded) == 1
    assert excluded[0]["written_product"] == "Crocin 650"


def test_rx09_telma_h_plus_telma_hits_on_telmisartan_only(loaded_conn):
    """Telma-H 40 (Telmisartan+HCTZ) + Telma 40 (Telmisartan): duplication is
    on Telmisartan specifically -- HCTZ appears once and must not be flagged.
    Both frequencies parse (1/day each) so the total is exact: 40+40=80mg/day."""
    results = check_duplicate_ingredient(loaded_conn, "RX09", _rows(loaded_conn, "RX09"), AS_OF)
    assert len(results) == 1
    r = results[0]
    assert r["state"] == "HIT"
    assert r["evidence"]["ingredient"] == "Telmisartan"
    assert r["evidence"]["cumulative_daily_mg"] == 80
    assert r["evidence"]["cumulative_is_partial"] is False


def test_rx04_single_unresolvable_item_is_unverified_input(loaded_conn):
    """'Telma' (no strength) matches none of Telma 20/40/80 exactly -- the
    written brand string is untrusted input and must not be guessed at."""
    results = check_duplicate_ingredient(loaded_conn, "RX04", _rows(loaded_conn, "RX04"), AS_OF)
    assert len(results) == 1
    assert results[0]["state"] == "UNVERIFIED_INPUT"


def test_rx08_fictitious_product_is_unverified_input(loaded_conn):
    results = check_duplicate_ingredient(loaded_conn, "RX08", _rows(loaded_conn, "RX08"), AS_OF)
    assert len(results) == 1
    assert results[0]["state"] == "UNVERIFIED_INPUT"


def test_no_duplicate_among_resolved_items_is_checked_no_hit(loaded_conn):
    """RX05 (Glycomet 500 + Atorva 10) shares no ingredient -- a real,
    fully-resolved negative."""
    results = check_duplicate_ingredient(loaded_conn, "RX05", _rows(loaded_conn, "RX05"), AS_OF)
    assert len(results) == 1
    assert results[0]["state"] == "CHECKED_NO_HIT"


def test_one_unresolved_item_downgrades_clean_negative_to_partial_coverage(loaded_conn):
    """Synthetic prescription: one resolvable, non-duplicating item plus one
    item that can't be resolved at all -- must not be reported as a clean
    CHECKED_NO_HIT, since the unresolved item's ingredients are unknown and
    could duplicate something."""
    rows = [
        {"rx_id": "RXTEST", "item_no": "1", "written_product": "Glycomet 500", "dose_frequency": "1-0-1"},
        {"rx_id": "RXTEST", "item_no": "2", "written_product": "Totally Unknown Brand XYZ", "dose_frequency": "1-0-0"},
    ]
    results = check_duplicate_ingredient(loaded_conn, "RXTEST", rows, AS_OF)
    assert len(results) == 1
    assert results[0]["state"] == "PARTIAL_COVERAGE"
    assert results[0]["evidence"]["unresolved_items"][0]["written_product"] == "Totally Unknown Brand XYZ"


def test_no_threshold_language_present_and_no_verdict_based_on_magnitude(loaded_conn):
    """Direct check against the explicit instruction: no dose limit is ever
    created or applied. A HIT with a huge total and a HIT with a tiny total
    must both simply be HIT -- there is no severity gate on the number."""
    r1 = check_duplicate_ingredient(loaded_conn, "RX01", _rows(loaded_conn, "RX01"), AS_OF)[0]
    r9 = check_duplicate_ingredient(loaded_conn, "RX09", _rows(loaded_conn, "RX09"), AS_OF)[0]
    assert r1["state"] == r9["state"] == "HIT"
    assert r1["severity"] is None and r9["severity"] is None
    assert "no maximum-safe-daily-dose threshold" in r1["evidence"]["note"].lower()
