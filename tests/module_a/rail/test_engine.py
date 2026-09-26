"""run_safety_rail: ties the three checks together, persists every result
(append-only, replayable -- binding law), and deliberately returns NO
combined overall_state, per the finalized engineering decision."""
import json

from src.module_a.rail.engine import run_safety_rail, run_safety_rail_for_all_seed_prescriptions
from src.module_a.rail.prescription_resolver import load_seed_prescriptions

TODAY = "2026-09-27"


def test_returns_exactly_the_three_checks_and_nothing_else(loaded_conn):
    rows = load_seed_prescriptions()["RX01"]
    result = run_safety_rail(loaded_conn, "RX01", rows, TODAY)
    assert set(result.keys()) == {"duplicate_active_ingredient", "prohibited_restricted_fdc", "severe_interaction"}
    assert "overall_state" not in result
    for check_results in result.values():
        assert isinstance(check_results, list) and len(check_results) >= 1


def test_every_result_is_persisted_and_replayable(loaded_conn):
    rows = load_seed_prescriptions()["RX01"]
    result = run_safety_rail(loaded_conn, "RX01", rows, TODAY)
    dup_result = result["duplicate_active_ingredient"][0]
    assert dup_result["id"] is not None

    persisted = loaded_conn.execute(
        "SELECT * FROM rail_check_results WHERE id = ?", (dup_result["id"],)
    ).fetchone()
    assert persisted is not None
    assert persisted["rx_id"] == "RX01"
    assert persisted["check_name"] == "duplicate_active_ingredient"
    assert persisted["state"] == dup_result["state"]
    assert json.loads(persisted["evidence_json"]) == dup_result["evidence"]
    assert json.loads(persisted["data_versions_json"]) == dup_result["data_versions"]


def test_rail_results_are_append_only_across_repeated_runs(loaded_conn):
    """Running the rail twice for the same prescription must not overwrite
    or delete the first run's results -- each run is its own immutable
    record (binding law: everything versioned, everything replayable)."""
    rows = load_seed_prescriptions()["RX01"]
    run_safety_rail(loaded_conn, "RX01", rows, TODAY)
    first_count = loaded_conn.execute(
        "SELECT COUNT(*) c FROM rail_check_results WHERE rx_id='RX01'"
    ).fetchone()["c"]
    run_safety_rail(loaded_conn, "RX01", rows, TODAY)
    second_count = loaded_conn.execute(
        "SELECT COUNT(*) c FROM rail_check_results WHERE rx_id='RX01'"
    ).fetchone()["c"]
    assert second_count == 2 * first_count


def test_every_persisted_state_is_one_of_the_eight_mandated_states(loaded_conn):
    from src.config import load_config
    valid_states = set(load_config()["rail"]["states"])
    run_safety_rail_for_all_seed_prescriptions(loaded_conn, as_of_date=TODAY)
    states = {r["state"] for r in loaded_conn.execute("SELECT DISTINCT state FROM rail_check_results")}
    assert states <= valid_states
    assert len(states) >= 3, "the demonstration set should exercise more than one state"


def test_runs_all_ten_seed_prescriptions(loaded_conn):
    result = run_safety_rail_for_all_seed_prescriptions(loaded_conn, as_of_date=TODAY)
    assert len(result) == 10
    for rx_id, checks in result.items():
        assert set(checks.keys()) == {"duplicate_active_ingredient", "prohibited_restricted_fdc", "severe_interaction"}
