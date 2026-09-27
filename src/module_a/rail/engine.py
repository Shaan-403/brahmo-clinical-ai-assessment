"""A.6 -- the deterministic Safety Rail. Pure lookup logic, no LLM anywhere
in the check path (binding requirement).

run_safety_rail() runs the four independent checks (a-d, see cumulative_exposure.py
for why (d) is a separate check from (a) despite D-011) for one prescription and
persists every result to rail_check_results (append-only, never updated --
binding law: everything versioned, everything replayable). There is
DELIBERATELY no combined overall_state: each check keeps its own state, per
the finalized engineering decision, so a caller (or Part 2's presentation
layer) must look at all four rather than trust a single collapsed verdict.
"""
from __future__ import annotations
import json
import sqlite3
from datetime import date

from src.module_a.rail.cumulative_exposure import check_cumulative_exposure
from src.module_a.rail.duplicate_ingredient import check_duplicate_ingredient
from src.module_a.rail.prohibited_fdc import check_prohibited_fdc
from src.module_a.rail.severe_interaction import check_severe_interaction
from src.module_a.rail.prescription_resolver import load_seed_prescriptions

CHECKS = {
    "duplicate_active_ingredient": check_duplicate_ingredient,
    "prohibited_restricted_fdc": check_prohibited_fdc,
    "severe_interaction": check_severe_interaction,
    # Check (d): cumulative same-ingredient exposure, reported as its own
    # coverage-only check that never returns HIT (see cumulative_exposure.py
    # module docstring, DESIGN.md D-011/D-019). Distinct from (a): (a) still
    # separately carries the same cumulative total as ITS OWN HIT evidence
    # per D-011 -- this is that same computation surfaced independently so
    # all four A.6-named checks are explicit in every run's output.
    "cumulative_daily_exposure": check_cumulative_exposure,
}


def _persist(conn: sqlite3.Connection, result: dict) -> dict:
    cur = conn.execute(
        """
        INSERT INTO rail_check_results
            (rx_id, check_name, state, severity, evidence_json, rule_version, data_versions_json,
             as_of_date, evaluated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (result["rx_id"], result["check"], result["state"], result["severity"],
         json.dumps(result["evidence"]), result["rule_version"], json.dumps(result["data_versions"]),
         result["as_of_date"], result["evaluated_at"]),
    )
    conn.commit()
    return {**result, "id": cur.lastrowid}


def run_safety_rail(conn: sqlite3.Connection, rx_id: str, item_rows: list[dict],
                     as_of_date: str | None = None) -> dict:
    as_of_date = as_of_date or date.today().isoformat()
    return {
        name: [_persist(conn, r) for r in fn(conn, rx_id, item_rows, as_of_date)]
        for name, fn in CHECKS.items()
    }


def run_safety_rail_for_all_seed_prescriptions(conn: sqlite3.Connection, csv_path=None,
                                                as_of_date: str | None = None) -> dict:
    by_rx = load_seed_prescriptions(csv_path)
    return {rx_id: run_safety_rail(conn, rx_id, rows, as_of_date) for rx_id, rows in by_rx.items()}
