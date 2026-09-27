"""Check (d): cumulative same-ingredient daily exposure, reported as its
own coverage-only check that must NEVER return HIT (D-011/D-019). These
tests exercise both the complete-coverage case (RX09: Telma-H 40 + Telma 40,
both dose_frequency values parse cleanly) and the unparseable/"SOS" case
(RX07: Calpol 650 + Crocin 650 SOS), plus the unresolved-input and
no-shared-ingredient paths."""
from src.module_a.rail.cumulative_exposure import check_cumulative_exposure
from src.module_a.rail.prescription_resolver import load_seed_prescriptions

TODAY = "2026-09-27"


def test_never_returns_hit_across_every_seed_prescription(loaded_conn):
    """The structural guarantee D-011/D-019 requires: whatever else is true
    about a prescription (including RX01, which DOES produce a HIT on the
    separate duplicate_active_ingredient check for this same Paracetamol
    overlap), this check itself can never emit HIT."""
    by_rx = load_seed_prescriptions()
    for rx_id, rows in by_rx.items():
        for result in check_cumulative_exposure(loaded_conn, rx_id, rows, TODAY):
            assert result["state"] != "HIT", f"{rx_id} produced a HIT from the cumulative-exposure check"
            assert result["state"] in {"CHECKED_NO_HIT", "PARTIAL_COVERAGE", "UNVERIFIED_INPUT"}
            assert result["severity"] is None


def test_complete_coverage_is_checked_no_hit_with_full_cumulative_total(loaded_conn):
    """RX09: Telma-H 40 (Telmisartan+Hydrochlorothiazide, 1-0-0) + Telma 40
    (Telmisartan, 0-0-1) -- both items resolve, both dose_frequency values
    parse, so coverage is complete."""
    rows = load_seed_prescriptions()["RX09"]
    results = check_cumulative_exposure(loaded_conn, "RX09", rows, TODAY)
    assert len(results) == 1
    result = results[0]
    assert result["state"] == "CHECKED_NO_HIT"
    exposure = result["evidence"]["shared_ingredient_exposure"]
    telmisartan = next(e for e in exposure if e["ingredient"] == "Telmisartan")
    assert telmisartan["cumulative_is_partial"] is False
    assert telmisartan["cumulative_daily_mg"] == 80.0  # 40mg x1/day + 40mg x1/day
    assert telmisartan["items_excluded_from_total_due_to_unparseable_frequency"] == []
    assert "unresolved_items" not in result["evidence"]


def test_unparseable_sos_frequency_is_partial_coverage_not_dropped(loaded_conn):
    """RX07: Calpol 650 (1-1-1 x 3d, parses to 3/day) + Crocin 650 (SOS,
    unparseable) -- both share Paracetamol, but one contribution can't be
    totaled, so coverage must be PARTIAL_COVERAGE, and the SOS item must be
    named explicitly rather than silently excluded or assumed to be zero."""
    rows = load_seed_prescriptions()["RX07"]
    results = check_cumulative_exposure(loaded_conn, "RX07", rows, TODAY)
    assert len(results) == 1
    result = results[0]
    assert result["state"] == "PARTIAL_COVERAGE"
    exposure = result["evidence"]["shared_ingredient_exposure"]
    paracetamol = next(e for e in exposure if e["ingredient"] == "Paracetamol")
    assert paracetamol["cumulative_is_partial"] is True
    # the parseable Calpol contribution (650mg x3/day) is still totaled...
    assert paracetamol["cumulative_daily_mg"] == 1950.0
    # ...but the SOS item is named, not silently folded in as zero
    excluded = paracetamol["items_excluded_from_total_due_to_unparseable_frequency"]
    assert len(excluded) == 1
    assert excluded[0]["written_product"] == "Crocin 650"
    assert excluded[0]["dose_frequency_raw"] == "SOS"


def test_no_items_resolved_is_unverified_input(loaded_conn):
    rows = [{"item_no": "1", "written_product": "Totally Unknown Brand XYZ-9000", "dose_frequency": "1-0-1"}]
    results = check_cumulative_exposure(loaded_conn, "DRAFT-UNRESOLVED", rows, TODAY)
    assert len(results) == 1
    assert results[0]["state"] == "UNVERIFIED_INPUT"
    assert results[0]["evidence"]["unresolved_items"]


def test_no_shared_ingredient_is_still_checked_no_hit_with_empty_exposure(loaded_conn):
    """RX05: Glycomet 500 (Metformin) + Atorva 10 (Atorvastatin) -- two
    different resolved items with no overlapping ingredient at all. The
    check still runs to completion: complete coverage, just nothing to
    report in shared_ingredient_exposure."""
    rows = load_seed_prescriptions()["RX05"]
    results = check_cumulative_exposure(loaded_conn, "RX05", rows, TODAY)
    assert len(results) == 1
    assert results[0]["state"] == "CHECKED_NO_HIT"
    assert results[0]["evidence"]["shared_ingredient_exposure"] == []


def test_no_dose_limit_or_clinical_criterion_anywhere_in_the_code():
    """Structural guard against D-011 creeping back in as an actual
    threshold: no comparison operator anywhere in this module's code
    compares a value against a numeric literal (which is what a "cumulative
    > safe limit" check would require). Explanatory prose in the module's
    own docstrings/evidence strings (e.g. the word "threshold" used to
    describe that none is applied) is not code and is deliberately not
    scanned here -- this checks the actual logic, not the vocabulary."""
    import ast
    import inspect
    from src.module_a.rail import cumulative_exposure

    def _is_len_call(node) -> bool:
        return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "len"

    tree = ast.parse(inspect.getsource(cumulative_exposure))
    comparisons_against_numbers = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Compare)
        and any(isinstance(op, (ast.Gt, ast.Lt, ast.GtE, ast.LtE)) for op in n.ops)
        and (isinstance(n.left, ast.Constant) and isinstance(n.left.value, (int, float))
             or any(isinstance(c, ast.Constant) and isinstance(c.value, (int, float)) for c in n.comparators))
        # exclude len(...) >= 2 -- that's the structural definition of "shared"
        # (appears in 2+ resolved items, straight from the brief's own wording),
        # never a clinical/dose comparison.
        and not _is_len_call(n.left)
    ]
    assert comparisons_against_numbers == []
