"""Check (c): severe interaction against the provided seed list
(severe_interaction_seed.csv, loaded into severe_interactions -- see
src/module_a/ingest/interaction_loader.py).

Interactions are evaluated across the WHOLE prescription's decomposed
ingredient set (union across all resolvable items), not just within a single
product's FDC -- an interaction between two different brands is exactly the
case this check exists for.

Coverage: any severe_interactions row with an unresolved ingredient name can
never be matched (see interaction_loader.py / DESIGN.md D-010). That is a
global data-completeness fact, not specific to any one prescription, so a
clean negative result on ANY prescription is downgraded from CHECKED_NO_HIT
to PARTIAL_COVERAGE whenever that global gap exists -- this system will
never claim "no severe interaction" with unresolved rows sitting in the seed
list unmatched. A real HIT is unaffected by this and is still reported as
HIT.
"""
from __future__ import annotations
import sqlite3

from src.module_a.rail.prescription_resolver import resolve_prescription_item
from src.module_a.rail.provenance import current_source_versions
from src.module_a.rail.result import build_result

RULE_VERSION = "severe_interaction_v1"


def _any_unresolved_interaction_rows(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT COUNT(*) c FROM severe_interactions WHERE ingredient_a_id IS NULL OR ingredient_b_id IS NULL"
    ).fetchone()
    return row["c"] > 0


def check_severe_interaction(conn: sqlite3.Connection, rx_id: str, item_rows: list[dict],
                              as_of_date: str) -> list[dict]:
    data_versions = current_source_versions(conn, ["cdci", "severe_interactions"])

    def _result(state, evidence, severity=None):
        return build_result("severe_interaction", rx_id, state, evidence, RULE_VERSION, data_versions,
                             as_of_date, severity)

    resolved, unresolved = [], []
    ingredient_sources: dict[int, list[dict]] = {}
    for row in item_rows:
        res = resolve_prescription_item(conn, row["written_product"])
        if res["status"] != "RESOLVED":
            unresolved.append({"item_no": row["item_no"], "written_product": row["written_product"], "resolution": res})
            continue
        resolved.append({"item_no": row["item_no"], "written_product": row["written_product"],
                          "product_id": res["product_id"]})
        for r in conn.execute(
            "SELECT pi.ingredient_id, i.canonical_name FROM product_ingredients pi "
            "JOIN ingredients i ON i.id = pi.ingredient_id WHERE pi.product_id=?", (res["product_id"],)
        ).fetchall():
            ingredient_sources.setdefault(r["ingredient_id"], []).append(
                {"item_no": row["item_no"], "written_product": row["written_product"],
                 "canonical_name": r["canonical_name"]})

    if not resolved:
        return [_result("UNVERIFIED_INPUT", {
            "reason": "No item's written_product could be resolved to exactly one product; "
                      "nothing could be checked against the interaction seed list.",
            "unresolved_items": unresolved,
        })]

    present_ids = set(ingredient_sources.keys())
    interaction_rows = conn.execute(
        "SELECT * FROM severe_interactions WHERE ingredient_a_id IS NOT NULL AND ingredient_b_id IS NOT NULL"
    ).fetchall()

    findings = []
    for pair in interaction_rows:
        if pair["ingredient_a_id"] in present_ids and pair["ingredient_b_id"] in present_ids:
            evidence = {
                "ingredient_a": pair["ingredient_a_raw"], "ingredient_b": pair["ingredient_b_raw"],
                "note": pair["note"], "source_tag": pair["source_tag"],
                "contributing_items_a": ingredient_sources[pair["ingredient_a_id"]],
                "contributing_items_b": ingredient_sources[pair["ingredient_b_id"]],
            }
            if unresolved:
                evidence["unresolved_items"] = unresolved
            findings.append(_result("HIT", evidence, severity=pair["severity"]))

    if findings:
        return findings

    evidence = {"checked_items": [{"item_no": r["item_no"], "written_product": r["written_product"]} for r in resolved]}
    partial = bool(unresolved) or _any_unresolved_interaction_rows(conn)
    if unresolved:
        evidence["unresolved_items"] = unresolved
    if _any_unresolved_interaction_rows(conn):
        evidence["note"] = ("One or more rows in the severe-interaction seed list have an ingredient name "
                             "that never resolved to a canonical ingredient and can never be matched; "
                             "coverage against the full seed list is not provably complete.")
    return [_result("PARTIAL_COVERAGE" if partial else "CHECKED_NO_HIT", evidence)]
