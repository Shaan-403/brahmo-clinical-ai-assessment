"""Check (d): cumulative same-ingredient daily exposure across the whole
prescription -- reported as its own, independent A.6 check, alongside (and
never overlapping with) checks (a)/(b)/(c).

This check NEVER returns HIT, by construction: there is no branch in this
function that can produce it (per the finalized engineering decision,
D-011/D-019 -- no maximum-safe-daily-dose threshold exists in the provided
data pack and none is invented here, so this check has no clinical
criterion to trigger a HIT against in the first place). Its 8-state result
reflects ONLY whether cumulative-exposure coverage for this prescription is
complete or partial:
  - UNVERIFIED_INPUT  -- no item's written_product resolved to exactly one
                         product; nothing could be decomposed or totaled.
  - PARTIAL_COVERAGE  -- at least one item resolved, but coverage is
                         incomplete: some item(s) didn't resolve (their
                         ingredients are unknown and could hide a shared
                         ingredient we never saw), and/or some resolved
                         item's dose_frequency didn't parse (e.g. "SOS"),
                         so at least one shared ingredient's cumulative
                         total is itself incomplete.
  - CHECKED_NO_HIT    -- every item resolved and every resolved item's
                         dose_frequency parsed; cumulative-exposure
                         coverage for this prescription is complete. (This
                         state name is the rail's fixed 8-value vocabulary,
                         not a claim that anything was screened for
                         pass/fail here -- see the module-level note in the
                         evidence of every result.)

The actual per-shared-ingredient totals (in mg/day, verbatim from the same
computation duplicate_ingredient.py uses for its own HIT evidence) are
always attached as evidence, at whichever state above applies -- this check
exists specifically so that evidence is visible on its own, independent of
whether check (a) happens to fire a HIT for the same prescription.

Per D-011 (kept untouched): no maximum-safe-daily-dose threshold is applied
to any total here, and none is invented. The total is data for a human
reviewer, never a pass/fail criterion -- structurally guaranteed by this
check never having a state that means "exceeded"."""
from __future__ import annotations
import sqlite3

from src.module_a.rail.duplicate_ingredient import _resolve_items
from src.module_a.rail.ingredient_totals import compute_ingredient_totals
from src.module_a.rail.provenance import current_source_versions
from src.module_a.rail.result import build_result

RULE_VERSION = "cumulative_daily_exposure_v1"

_NO_THRESHOLD_NOTE = (
    "This check reports cumulative per-ingredient daily exposure for ingredients shared across 2+ resolved "
    "items, as evidence only. No maximum-safe-daily-dose threshold is applied or invented (no such threshold "
    "exists in the provided data pack; see DESIGN.md D-011/D-019) -- this check cannot and does not return "
    "HIT under any circumstance. Its state reflects only whether this coverage is complete or partial."
)


def check_cumulative_exposure(conn: sqlite3.Connection, rx_id: str, item_rows: list[dict],
                               as_of_date: str) -> list[dict]:
    data_versions = current_source_versions(conn, ["cdci"])
    resolved, unresolved = _resolve_items(conn, item_rows)

    def _result(state, evidence):
        return build_result("cumulative_daily_exposure", rx_id, state, evidence,
                             RULE_VERSION, data_versions, as_of_date, severity=None)

    if not resolved:
        return [_result("UNVERIFIED_INPUT", {
            "reason": "No item's written_product could be resolved to exactly one product; cumulative "
                      "exposure could not be computed for any ingredient.",
            "unresolved_items": unresolved,
            "note": _NO_THRESHOLD_NOTE,
        })]

    totals = compute_ingredient_totals(resolved)
    shared = {ingredient_id: bucket for ingredient_id, bucket in totals.items()
              if len(bucket["contributions"]) >= 2}

    exposure_report = []
    any_unparseable = False
    for bucket in shared.values():
        contributions = list(bucket["contributions"].values())
        parseable = [c for c in contributions if c["daily_mg"] is not None]
        unparseable = [c for c in contributions if c["daily_mg"] is None]
        if unparseable:
            any_unparseable = True
        exposure_report.append({
            "ingredient": bucket["canonical_name"],
            "contributing_items": contributions,
            "cumulative_daily_mg": sum(c["daily_mg"] for c in parseable) if parseable else None,
            "cumulative_is_partial": bool(unparseable),
            "items_excluded_from_total_due_to_unparseable_frequency": [
                {"item_no": c["item_no"], "written_product": c["written_product"],
                 "dose_frequency_raw": c["dose_frequency_raw"]}
                for c in unparseable
            ],
        })

    evidence = {
        "checked_items": [{"item_no": r["item_no"], "written_product": r["written_product"],
                            "product_id": r["product_id"]} for r in resolved],
        "shared_ingredient_exposure": exposure_report,
        "note": _NO_THRESHOLD_NOTE,
    }
    if unresolved:
        evidence["unresolved_items"] = unresolved
        evidence["coverage_note"] = ("One or more prescription items could not be resolved and were excluded "
                                      "from every total above; an unresolved item could share an ingredient "
                                      "with a resolved one and this coverage gap would hide that.")

    if unresolved or any_unparseable:
        return [_result("PARTIAL_COVERAGE", evidence)]
    return [_result("CHECKED_NO_HIT", evidence)]
