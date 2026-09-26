"""Check (b): prohibited/restricted FDC or ingredient, per the event-sourced
regulatory data (see src/module_a/regulatory).

Matching:
  - target_type == 'INGREDIENT' events match any item whose decomposed
    ingredient set CONTAINS that ingredient (it need not be the item's only
    ingredient -- a banned ingredient inside a larger FDC is still banned).
  - target_type == 'FDC' events match any item whose decomposed ingredient
    set is a SUPERSET of the event's ingredient set (not an exact-set match)
    -- a 3-way product containing a banned pair is still caught. This is a
    deliberate choice: an exact-set match would under-detect (a false
    negative on a real prohibited combination), which is worse in a safety
    rail than the alternative of a superset match that a reviewer can
    dismiss (see DESIGN.md D-009).
  - target_type == 'PRODUCT' events (e.g. a named suspension formulation)
    are NOT matched by this check -- there is no reliable, non-guessing way
    to link free-text product descriptions to CDCI's product_id without
    fuzzy matching a regulatory action, which this system will not do (see
    DESIGN.md D-012 / gaps_register.md). This is a documented coverage gap,
    not a silent one.

Current status as of a given date is resolved by grouping events with the
same parsed target ingredient set + target_type and taking the one with the
latest effective_date <= as_of_date (see target_parser.py, DESIGN.md D-009).
PROHIBITED / RESTRICTED / WITHDRAWN are treated as a positive match;
STAY_GRANTED is not. Two events tied at the same latest effective_date with
different actions is a SOURCE_CONFLICT, surfaced rather than arbitrarily
picking one.

Scope qualifiers in target_description (e.g. "paediatric suspensions only")
are classified in target_parser.classify_scope:
  - UNLIMITED     -> matched normally.
  - SUSPENSION    -> resolved deterministically against the matched
                     product's own dose_form column; if the product is not a
                     suspension, the event does not apply to it and is
                     skipped for that item.
  - UNVERIFIABLE  -> this system has no structured field to confirm or rule
                     out the qualifier (e.g. an age group, "specific ratio").
                     Rather than asserting a HIT it cannot fully justify, or
                     silently dropping a real regulatory match, this renders
                     as PARTIAL_COVERAGE with the qualifier quoted in
                     evidence for a human to resolve.
"""
from __future__ import annotations
import json
import sqlite3

from src.module_a.normalize.ingredient_normalizer import normalize_key
from src.module_a.rail.prescription_resolver import resolve_prescription_item
from src.module_a.rail.provenance import current_source_versions
from src.module_a.rail.result import build_result
from src.module_a.regulatory.target_parser import classify_scope

RULE_VERSION = "prohibited_restricted_fdc_v1"
_POSITIVE_ACTIONS = {"PROHIBITED", "RESTRICTED", "WITHDRAWN"}


def _ingredient_id_for_name(conn: sqlite3.Connection, name: str) -> int | None:
    row = conn.execute("SELECT id FROM ingredients WHERE normalized_key = ?", (normalize_key(name),)).fetchone()
    return row["id"] if row else None


def _load_event_groups(conn: sqlite3.Connection) -> tuple[list[dict], bool]:
    """Groups regulatory_events by (target_type, frozenset(ingredient_ids)).
    Returns (groups, any_unmappable) where any_unmappable is True if any
    FDC/INGREDIENT event references an ingredient name with no canonical
    match in the ingredient registry -- such an event can never be matched,
    which means a clean CHECKED_NO_HIT elsewhere can only ever be
    PARTIAL_COVERAGE (see module docstring / DESIGN.md D-010's sibling
    treatment for severe_interactions)."""
    rows = conn.execute(
        "SELECT * FROM regulatory_events WHERE target_type IN ('FDC','INGREDIENT')"
    ).fetchall()
    groups: dict[tuple, dict] = {}
    any_unmappable = False
    for row in rows:
        names = json.loads(row["target_ingredients_json"])
        ids = [_ingredient_id_for_name(conn, n) for n in names]
        if any(i is None for i in ids):
            any_unmappable = True
            continue
        key = (row["target_type"], frozenset(ids))
        groups.setdefault(key, {"target_type": row["target_type"], "ingredient_ids": frozenset(ids),
                                 "ingredient_names": names, "scope_note": row["scope_note"],
                                 "target_description": row["target_description"], "events": []})
        groups[key]["events"].append(dict(row))
    return list(groups.values()), any_unmappable


def _current_status(events: list[dict], as_of_date: str) -> tuple[str | None, list[dict]]:
    """Returns (action_or_None, [the event(s) that decided it]). action is
    None if no event is effective yet as of as_of_date. Multiple events
    returned together means a tie -> SOURCE_CONFLICT."""
    effective = [e for e in events if e["effective_date"] <= as_of_date]
    if not effective:
        return None, []
    latest_date = max(e["effective_date"] for e in effective)
    at_latest = [e for e in effective if e["effective_date"] == latest_date]
    actions = {e["action"] for e in at_latest}
    if len(actions) > 1:
        return "CONFLICT", at_latest
    return at_latest[0]["action"], at_latest


def check_prohibited_fdc(conn: sqlite3.Connection, rx_id: str, item_rows: list[dict], as_of_date: str) -> list[dict]:
    data_versions = current_source_versions(conn, ["cdci", "regulatory_events"])
    groups, any_unmappable = _load_event_groups(conn)

    def _result(state, evidence, severity=None):
        return build_result("prohibited_restricted_fdc", rx_id, state, evidence,
                             RULE_VERSION, data_versions, as_of_date, severity)

    resolved, unresolved = [], []
    for row in item_rows:
        res = resolve_prescription_item(conn, row["written_product"])
        if res["status"] != "RESOLVED":
            unresolved.append({"item_no": row["item_no"], "written_product": row["written_product"], "resolution": res})
            continue
        product = conn.execute("SELECT id, external_product_id, brand_name, dose_form FROM products WHERE id=?",
                                (res["product_id"],)).fetchone()
        ingredient_ids = {r["ingredient_id"] for r in conn.execute(
            "SELECT ingredient_id FROM product_ingredients WHERE product_id=?", (product["id"],)).fetchall()}
        resolved.append({"item_no": row["item_no"], "written_product": row["written_product"],
                          "product_id": product["id"], "external_product_id": product["external_product_id"],
                          "brand_name": product["brand_name"], "dose_form": product["dose_form"],
                          "ingredient_ids": ingredient_ids})

    if not resolved:
        return [_result("UNVERIFIED_INPUT", {
            "reason": "No item's written_product could be resolved to exactly one product; "
                      "nothing could be matched against regulatory data.",
            "unresolved_items": unresolved,
        })]

    findings = []
    any_source_conflict = False
    for item in resolved:
        for group in groups:
            if group["target_type"] == "INGREDIENT":
                matches = bool(group["ingredient_ids"] & item["ingredient_ids"])
            else:  # FDC
                matches = group["ingredient_ids"].issubset(item["ingredient_ids"]) and len(group["ingredient_ids"]) >= 2
            if not matches:
                continue

            scope = classify_scope(group["scope_note"])
            if scope == "SUSPENSION":
                dose_form = (item["dose_form"] or "").casefold()
                if "suspension" not in dose_form:
                    continue  # deterministically does not apply to this dose form

            action, deciding_events = _current_status(group["events"], as_of_date)
            if action is None:
                continue  # nothing effective yet as of as_of_date
            evidence_base = {
                "item_no": item["item_no"], "written_product": item["written_product"],
                "external_product_id": item["external_product_id"], "brand_name": item["brand_name"],
                "dose_form": item["dose_form"], "matched_target": group["target_description"],
                "target_type": group["target_type"],
                "deciding_events": [{"event_id": e["event_id"], "action": e["action"],
                                      "effective_date": e["effective_date"], "notification_id": e["notification_id"],
                                      "note": e["note"]} for e in deciding_events],
                "all_events_for_target": [{"event_id": e["event_id"], "action": e["action"],
                                            "effective_date": e["effective_date"],
                                            "supersedes_event_id": e["supersedes_event_id"]} for e in group["events"]],
            }
            if action == "CONFLICT":
                any_source_conflict = True
                findings.append(_result("SOURCE_CONFLICT", {
                    **evidence_base,
                    "issue": "Multiple regulatory events share the latest effective_date for this target "
                             "with different actions; current status cannot be determined deterministically.",
                }))
                continue
            if action not in _POSITIVE_ACTIONS:
                continue  # e.g. STAY_GRANTED as of this date -- not currently prohibited/restricted
            if scope == "UNVERIFIABLE":
                findings.append(_result("PARTIAL_COVERAGE", {
                    **evidence_base, "action": action, "scope_note": group["scope_note"],
                    "issue": f"Regulatory action {action!r} matches this item's ingredients, but its scope "
                             f"qualifier ({group['scope_note']!r}) cannot be verified against any structured "
                             f"field this system has -- a human must confirm applicability.",
                }))
                continue
            findings.append(_result("HIT", {**evidence_base, "action": action}, severity=action))

    if findings:
        return findings

    evidence = {"checked_items": [{"item_no": r["item_no"], "written_product": r["written_product"],
                                    "external_product_id": r["external_product_id"]} for r in resolved],
                "product_type_events_out_of_scope": "regulatory_events rows with target_type=PRODUCT are not "
                                                     "matched by this check (see DESIGN.md D-012); this run is "
                                                     "only conclusive for FDC/INGREDIENT-scoped actions."}
    if unresolved:
        evidence["unresolved_items"] = unresolved
        return [_result("PARTIAL_COVERAGE", evidence)]
    if any_unmappable:
        evidence["note"] = ("One or more regulatory events reference an ingredient name with no canonical "
                             "match in the ingredient registry and could never be matched; coverage is not "
                             "provably complete.")
        return [_result("PARTIAL_COVERAGE", evidence)]
    return [_result("CHECKED_NO_HIT", evidence)]
