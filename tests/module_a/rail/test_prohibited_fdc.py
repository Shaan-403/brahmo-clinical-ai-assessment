"""Check (b): prohibited/restricted FDC or ingredient against event-sourced
regulatory data. Ground truth for every assertion here was verified directly
against the real data pack before writing the test (see conversation
record) -- nothing here is a guess about what the data contains.

Important, verified fact about this data pack: two regulatory_events rows
(EV004, EV007, EV011) reference "Caffeine" or "Codeine-based cough FDCs" --
neither maps to any canonical ingredient in the CDCI subset. Per DESIGN.md
D-010 (a check can never claim full coverage while part of its source data
is unmatchable), this means a "no hit" result on THIS data pack is always
PARTIAL_COVERAGE, never a bare CHECKED_NO_HIT -- see
test_negative_result_is_partial_coverage_not_clean_due_to_unmappable_events.
"""
from src.module_a.rail.prescription_resolver import load_seed_prescriptions
from src.module_a.rail.prohibited_fdc import check_prohibited_fdc

TODAY = "2026-09-27"


def _row(item_no, written_product):
    return {"item_no": item_no, "written_product": written_product, "dose_frequency": ""}


def test_rx02_nimupar_p_is_currently_prohibited(loaded_conn):
    """NimuPar-P = Nimesulide+Paracetamol. As of today the applicable event is
    EV003 (re-prohibition, 2023-06-15), which supersedes the 2019 court stay
    (EV002) which itself had superseded the original 2018 ban (EV001) --
    picking the event with the latest effective_date <= today must resolve
    this correctly without any special-cased chain-walking."""
    rows = load_seed_prescriptions()["RX02"]
    results = check_prohibited_fdc(loaded_conn, "RX02", rows, TODAY)
    hits = [r for r in results if r["state"] == "HIT"]
    assert len(hits) == 1
    assert hits[0]["evidence"]["action"] == "PROHIBITED"
    assert hits[0]["evidence"]["deciding_events"][0]["event_id"] == "EV003"


def test_event_sourcing_respects_the_court_stay_at_its_own_point_in_time(loaded_conn):
    """As of a date during the 2019 stay (after EV002, before EV003), the
    same product must NOT be reported as a HIT -- the historical status was
    genuinely not-prohibited at that point in time."""
    rows = load_seed_prescriptions()["RX02"]
    results = check_prohibited_fdc(loaded_conn, "RX02", rows, "2019-06-01")
    assert all(r["state"] != "HIT" for r in results)


def test_event_sourcing_finds_the_original_2018_prohibition(loaded_conn):
    """As of a date before the stay was even granted, EV001 alone is
    effective and must produce a HIT."""
    rows = load_seed_prescriptions()["RX02"]
    results = check_prohibited_fdc(loaded_conn, "RX02", rows, "2019-01-01")
    hits = [r for r in results if r["state"] == "HIT"]
    assert len(hits) == 1
    assert hits[0]["evidence"]["deciding_events"][0]["event_id"] == "EV001"


def test_ranitidine_ingredient_prohibition_hits(loaded_conn):
    """'Ducor Forte' = Ranitidine 250mg solo. EV006 (PROHIBITED, superseding
    the 2024 RESTRICTED EV005) is current as of today."""
    rows = [_row("1", "Ducor Forte")]
    results = check_prohibited_fdc(loaded_conn, "RX_RANITIDINE", rows, TODAY)
    hits = [r for r in results if r["state"] == "HIT"]
    assert len(hits) == 1
    assert hits[0]["evidence"]["target_type"] == "INGREDIENT"
    assert hits[0]["evidence"]["deciding_events"][0]["event_id"] == "EV006"


def test_suspension_scope_is_resolved_via_dose_form_not_asserted_blindly(loaded_conn):
    """'Combiflam' is Ibuprofen+Paracetamol as a TABLET. EV012 restricts that
    exact combination but only for paediatric SUSPENSIONS, and its own note
    says outright "adult tablets unaffected". Since dose_form is a structured
    field this system already has, the event must be recognized as not
    applying to this product -- it must not become a HIT, and it must not
    even surface as an event-specific PARTIAL_COVERAGE finding (the only
    PARTIAL_COVERAGE this run should produce is the pack-wide unmappable-data
    caveat, unrelated to Combiflam specifically)."""
    rows = [_row("1", "Combiflam")]
    results = check_prohibited_fdc(loaded_conn, "RX_COMBIFLAM", rows, TODAY)
    assert all(r["state"] != "HIT" for r in results)
    assert not any("EV012" in str(r["evidence"]) for r in results if r["state"] == "PARTIAL_COVERAGE"
                   and "matched_target" in r["evidence"])


def test_unverifiable_scope_qualifier_is_flagged_not_silently_dropped_or_hit(loaded_conn):
    """'Nitas-Plus' is Tramadol 100mg solo. EV008 restricts Tramadol but
    qualifies it with "Schedule H1 enforcement" -- a dispensing-control
    qualifier this system has no structured field to verify. It must not be
    silently ignored (that would hide a real regulatory action) and must not
    be asserted as a confident HIT either (that would overclaim something
    unverifiable) -- PARTIAL_COVERAGE with the qualifier quoted is correct."""
    rows = [_row("1", "Nitas-Plus")]
    results = check_prohibited_fdc(loaded_conn, "RX_TRAMADOL", rows, TODAY)
    matches = [r for r in results if r["evidence"].get("matched_target", "").startswith("Tramadol")]
    assert len(matches) == 1
    assert matches[0]["state"] == "PARTIAL_COVERAGE"
    assert matches[0]["evidence"]["scope_note"] == "Schedule H1 enforcement"
    assert matches[0]["evidence"]["action"] == "RESTRICTED"


def test_unresolved_item_is_unverified_input(loaded_conn):
    rows = [_row("1", "Zqtrixon Forte")]
    results = check_prohibited_fdc(loaded_conn, "RX08", rows, TODAY)
    assert len(results) == 1
    assert results[0]["state"] == "UNVERIFIED_INPUT"


def test_negative_result_is_partial_coverage_not_clean_due_to_unmappable_events(loaded_conn):
    """Ground truth (verified against the real data pack): EV004/EV007
    reference "Caffeine" and EV011 references "Codeine-based cough FDCs" --
    neither maps to any canonical ingredient, so this check can never claim
    its coverage of the regulatory data is complete. A prescription with no
    matching event at all (Glycomet 500 + Atorva 10, RX05) must therefore
    report PARTIAL_COVERAGE, not a falsely-confident CHECKED_NO_HIT."""
    rows = load_seed_prescriptions()["RX05"]
    results = check_prohibited_fdc(loaded_conn, "RX05", rows, TODAY)
    assert len(results) == 1
    assert results[0]["state"] == "PARTIAL_COVERAGE"
    assert "no canonical match" in results[0]["evidence"]["note"].lower()


def test_two_events_tied_at_the_same_effective_date_is_a_source_conflict(conn, tmp_path):
    """Synthetic scenario: two regulatory events for the same target with the
    SAME effective_date but different actions. Current status cannot be
    determined deterministically -- this must surface as SOURCE_CONFLICT,
    never an arbitrary pick of one action over the other."""
    import csv
    from src.module_a.ingest.cdci_loader import load_cdci
    from src.module_a.regulatory.loader import load_regulatory_events

    cdci_path = tmp_path / "cdci.csv"
    with open(cdci_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["product_id", "brand_name", "manufacturer", "dose_form", "strength_text", "source",
                    "source_version", "effective_from", "ingredient_1", "strength_1_mg",
                    "ingredient_2", "strength_2_mg", "ingredient_3", "strength_3_mg"])
        w.writerow(["CDX1", "Testadol", "TestPharma", "Tablet", "TestActive 100 mg", "CDCI-TEST",
                    "2026-01-01", "2026-01-01", "TestActive", "100", "", "", "", ""])
    load_cdci(conn, csv_path=cdci_path)

    events_path = tmp_path / "events.csv"
    with open(events_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["event_id", "notification_id", "date_published", "effective_date", "action",
                    "target_type", "target_description", "supersedes_event_id", "note"])
        w.writerow(["EVX1", "N1", "2026-01-01", "2026-02-01", "PROHIBITED", "INGREDIENT",
                    "TestActive (all products)", "", "conflict test A"])
        w.writerow(["EVX2", "N2", "2026-01-01", "2026-02-01", "STAY_GRANTED", "INGREDIENT",
                    "TestActive (all products)", "", "conflict test B"])
    load_regulatory_events(conn, csv_path=events_path)

    rows = [{"item_no": "1", "written_product": "Testadol", "dose_frequency": ""}]
    results = check_prohibited_fdc(conn, "RXCONFLICT", rows, "2026-09-27")
    conflicts = [r for r in results if r["state"] == "SOURCE_CONFLICT"]
    assert len(conflicts) == 1
