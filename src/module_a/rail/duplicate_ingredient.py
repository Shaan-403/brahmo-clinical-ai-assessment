"""Check (a) + (d): duplicate active ingredient across products, with the
cumulative per-ingredient daily total attached as its evidence.

Per the finalized engineering decision, these are ONE check, not two: the
brief itself ties them together ("a duplicate-ingredient HIT must carry this
aggregate as its evidence"), and the HIT trigger is presence-based
(the same ingredient decomposed out of 2+ distinct products in the same
prescription) -- it never depends on the size of the total. No maximum-
safe-daily-dose threshold exists anywhere in the provided data pack and none
is invented here (see DESIGN.md D-011): the computed total is evidence for a
human, not itself a pass/fail criterion.

An item whose written_product cannot be resolved to exactly one product is
untrusted input for this check -- its ingredients are unknown, so it can
never be silently treated as "contributes nothing." If NO item resolves,
the whole check is UNVERIFIED_INPUT. If SOME items resolve and no duplicate
is found among them, the result is PARTIAL_COVERAGE (not CHECKED_NO_HIT) --
the unresolved item(s) could hide a duplicate we didn't get to see. A real
HIT among the resolved items is still reported as HIT (a confirmed problem
outranks an unrelated coverage gap), with the coverage gap noted alongside it.

An item whose dose_frequency doesn't parse (e.g. "SOS") contributes an
unknown, not a zero, to the cumulative total -- see
src/module_a/rail/dose_frequency.py.

The same per-ingredient cumulative-total computation is also reported
independently, as its own coverage-only, never-HIT-producing check (d) --
see src/module_a/rail/cumulative_exposure.py and DESIGN.md D-019. That
check exists so Module C's trace can show all four A.6-named checks
explicitly; it does not change anything about this check's own HIT logic
or D-011's original reasoning (no threshold invented, the total here is
this HIT's evidence, not its trigger).
"""
from __future__ import annotations
import sqlite3

from src.module_a.rail.dose_frequency import parse_doses_per_day
from src.module_a.rail.ingredient_totals import compute_ingredient_totals
from src.module_a.rail.prescription_resolver import resolve_prescription_item
from src.module_a.rail.provenance import current_source_versions
from src.module_a.rail.result import build_result

RULE_VERSION = "duplicate_active_ingredient_v1"


def _resolve_items(conn: sqlite3.Connection, item_rows: list[dict]) -> tuple[list[dict], list[dict]]:
    resolved, unresolved = [], []
    for row in item_rows:
        res = resolve_prescription_item(conn, row["written_product"])
        if res["status"] != "RESOLVED":
            unresolved.append({"item_no": row["item_no"], "written_product": row["written_product"],
                                "resolution": res})
            continue
        product_id = res["product_id"]
        ingredient_rows = conn.execute(
            """
            SELECT pi.ingredient_id, i.canonical_name, pi.strength_mg
            FROM product_ingredients pi JOIN ingredients i ON i.id = pi.ingredient_id
            WHERE pi.product_id = ?
            """,
            (product_id,),
        ).fetchall()
        doses_per_day = parse_doses_per_day(row["dose_frequency"])
        resolved.append({
            "item_no": row["item_no"], "written_product": row["written_product"], "product_id": product_id,
            "dose_frequency_raw": row["dose_frequency"], "doses_per_day": doses_per_day,
            "ingredients": [{"ingredient_id": r["ingredient_id"], "canonical_name": r["canonical_name"],
                              "strength_mg": r["strength_mg"]} for r in ingredient_rows],
        })
    return resolved, unresolved


def check_duplicate_ingredient(conn: sqlite3.Connection, rx_id: str, item_rows: list[dict],
                                as_of_date: str) -> list[dict]:
    data_versions = current_source_versions(conn, ["cdci"])
    resolved, unresolved = _resolve_items(conn, item_rows)

    def _result(state, evidence, severity=None):
        return build_result("duplicate_active_ingredient", rx_id, state, evidence,
                             RULE_VERSION, data_versions, as_of_date, severity)

    if not resolved:
        return [_result("UNVERIFIED_INPUT", {
            "reason": "No item's written_product could be resolved to exactly one product; "
                      "nothing could be decomposed to check.",
            "unresolved_items": unresolved,
        })]

    by_ingredient = compute_ingredient_totals(resolved)

    findings = []
    for ingredient_id, bucket in by_ingredient.items():
        contributions = list(bucket["contributions"].values())
        if len(contributions) < 2:
            continue
        parseable = [c for c in contributions if c["daily_mg"] is not None]
        unparseable = [c for c in contributions if c["daily_mg"] is None]
        evidence = {
            "ingredient": bucket["canonical_name"],
            "contributing_items": contributions,
            "cumulative_daily_mg": sum(c["daily_mg"] for c in parseable) if parseable else None,
            "cumulative_is_partial": bool(unparseable),
            "items_excluded_from_total_due_to_unparseable_frequency": [
                {"item_no": c["item_no"], "written_product": c["written_product"],
                 "dose_frequency_raw": c["dose_frequency_raw"]}
                for c in unparseable
            ],
            "note": "No maximum-safe-daily-dose threshold is applied here -- this total is evidence "
                    "for a human reviewer, not a pass/fail criterion (no such threshold exists in the "
                    "provided data pack; see DESIGN.md D-011).",
        }
        if unresolved:
            evidence["coverage_note"] = ("One or more prescription items could not be resolved and were "
                                          "excluded from this check; this HIT reflects only the resolvable items.")
            evidence["unresolved_items"] = unresolved
        findings.append(_result("HIT", evidence))

    if findings:
        return findings

    evidence = {"checked_items": [{"item_no": r["item_no"], "written_product": r["written_product"],
                                    "product_id": r["product_id"]} for r in resolved]}
    if unresolved:
        evidence["unresolved_items"] = unresolved
        return [_result("PARTIAL_COVERAGE", evidence)]
    return [_result("CHECKED_NO_HIT", evidence)]
