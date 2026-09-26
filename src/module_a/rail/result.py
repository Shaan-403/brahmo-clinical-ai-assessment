"""Shared shape for every Safety Rail check result. See config/thresholds.yaml
rail.states for the 8 mandated states (validated here) and DESIGN.md for why
there is deliberately no overall_state rollup across checks.
"""
from __future__ import annotations
from datetime import datetime, timezone

from src.config import load_config

VALID_STATES = set(load_config()["rail"]["states"])


def build_result(check_name: str, rx_id: str, state: str, evidence: dict,
                  rule_version: str, data_versions: dict, as_of_date: str,
                  severity: str | None = None) -> dict:
    if state not in VALID_STATES:
        raise ValueError(f"{state!r} is not one of the 8 mandated rail states: {sorted(VALID_STATES)}")
    return {
        "check": check_name,
        "rx_id": rx_id,
        "state": state,
        "severity": severity,
        "evidence": evidence,
        "rule_version": rule_version,
        "data_versions": data_versions,
        "as_of_date": as_of_date,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
    }
