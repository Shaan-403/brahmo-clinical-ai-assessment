"""Module C -- one runnable script/endpoint tying Module A (drug master +
deterministic Safety Rail) and Module B (grounded STW/local-protocol Q&A)
together into a single JSON trace, for one draft prescription + one clinical
question. This is the integration proof the brief asks for: deliberately
thin, adding no new clinical logic of its own. Every substantive piece --
prescription normalization, each Safety Rail check, the grounded answer --
is Module A's or Module B's own existing code, called as-is and assembled.

The Safety Rail's four required checks (a: duplicate active ingredient,
b: prohibited/restricted FDC, c: severe interaction, d: cumulative
same-ingredient exposure) are exactly the four check functions Module A's
engine (src.module_a.rail.engine.CHECKS) already runs -- this trace does no
re-derivation of any of them, just calls run_safety_rail() and reports what
it returns. (d) is deliberately its own check with its own 8-state result,
distinct from (a): per D-011, a duplicate_active_ingredient HIT still
separately carries the same cumulative per-ingredient daily total as ITS
OWN evidence (the brief ties (a) and (d) together: "a duplicate-ingredient
HIT must carry this aggregate as its evidence"); (d) surfaces that same
computation independently so it is visible in the trace even when (a)
doesn't fire, and so all four A.6-named checks are explicit. (d) never
returns HIT -- see src.module_a.rail.cumulative_exposure and DESIGN.md
D-019 -- its state reflects only whether cumulative-exposure coverage for
this prescription is complete or partial.
"""
from __future__ import annotations
import argparse
import json
import sys
from datetime import date, datetime, timezone

from src.db.connection import get_connection
from src.module_a.rail.cumulative_exposure import RULE_VERSION as CUMULATIVE_EXPOSURE_RULE_VERSION
from src.module_a.rail.duplicate_ingredient import RULE_VERSION as DUPLICATE_INGREDIENT_RULE_VERSION
from src.module_a.rail.duplicate_ingredient import _resolve_items as _resolve_prescription_items
from src.module_a.rail.engine import run_safety_rail
from src.module_a.rail.prohibited_fdc import RULE_VERSION as PROHIBITED_FDC_RULE_VERSION
from src.module_a.rail.provenance import current_source_versions
from src.module_a.rail.severe_interaction import RULE_VERSION as SEVERE_INTERACTION_RULE_VERSION
from src.module_b.answering.qa import answer_question

DATASET_SOURCES = ["cdci", "nlem", "jan_aushadhi", "regulatory_events", "severe_interactions",
                   "pharmacy_stock", "stw_corpus"]


def _normalization_section(conn, item_rows: list[dict]) -> dict:
    """Reuses the exact same resolution+decomposition logic every Safety
    Rail check already runs against this prescription (see
    src.module_a.rail.duplicate_ingredient._resolve_items) -- this section
    is not a second, parallel implementation of prescription normalization,
    just the same result surfaced as its own top-level trace field rather
    than buried inside one check's evidence."""
    resolved, unresolved = _resolve_prescription_items(conn, item_rows)
    return {
        "resolved_items": [
            {"item_no": r["item_no"], "written_product": r["written_product"], "product_id": r["product_id"],
             "dose_frequency_raw": r["dose_frequency_raw"], "doses_per_day": r["doses_per_day"],
             "ingredients": r["ingredients"]}
            for r in resolved
        ],
        "unresolved_items": unresolved,
    }


def build_trace(conn, rx_id: str, item_rows: list[dict], question: str,
                 as_of_date: str | None = None, persist: bool = True) -> dict:
    """The single entry point Module C exists to provide: {draft
    prescription + one clinical question} in, one JSON trace out. `conn`
    must already be migrated and have both Module A's data pack and Module
    B's STW corpus ingested (see README.md fresh-machine setup) -- this
    function does no ingestion of its own."""
    as_of_date = as_of_date or date.today().isoformat()

    normalization = _normalization_section(conn, item_rows)
    safety_rail = run_safety_rail(conn, rx_id, item_rows, as_of_date)
    module_b_answer = answer_question(conn, question, persist=persist)

    return {
        "rx_id": rx_id,
        "question": question,
        "as_of_date": as_of_date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "prescription_normalization": normalization,
        "safety_rail": safety_rail,
        "safety_rail_note": (
            "All four checks required by the brief are present above, each under the mandated 8-state "
            "contract (config/thresholds.yaml rail.states): (a) duplicate_active_ingredient, "
            "(b) prohibited_restricted_fdc, (c) severe_interaction, (d) cumulative_daily_exposure. "
            "(d) is a distinct check from (a) -- see DESIGN.md D-011 (why no threshold is invented) and "
            "D-019 (why (d) is also reported independently, and why it can never itself return HIT)."
        ),
        "module_b_answer": module_b_answer,
        "versions": {
            "dataset_versions": current_source_versions(conn, DATASET_SOURCES),
            "safety_rail_rule_versions": {
                "duplicate_active_ingredient": DUPLICATE_INGREDIENT_RULE_VERSION,
                "prohibited_restricted_fdc": PROHIBITED_FDC_RULE_VERSION,
                "severe_interaction": SEVERE_INTERACTION_RULE_VERSION,
                "cumulative_daily_exposure": CUMULATIVE_EXPOSURE_RULE_VERSION,
            },
            "module_b_retrieval_method": module_b_answer["retrieval_method"],
            "prompt_model_versions": {
                "llm_used": False,
                "note": (
                    "No LLM or prompt is invoked anywhere in this trace. The Safety Rail is pure "
                    "deterministic lookup logic (binding law -- no LLM anywhere in the check path). "
                    "Module B's answering step is retrieval-and-quote only, never generation (DESIGN.md "
                    "D-018). There is no prompt or model version to report because none runs."
                ),
            },
        },
    }


def _load_input(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Module C: single end-to-end trace for one draft prescription + one clinical question.",
    )
    parser.add_argument("input_json", help=(
        "Path to a JSON file: "
        '{"rx_id": "DRAFT-1", "items": [{"item_no": 1, "written_product": "...", "dose_frequency": "..."}, ...], '
        '"question": "...", "as_of_date": "YYYY-MM-DD" (optional)}'
    ))
    parser.add_argument("--out", help="Write the trace JSON here instead of stdout.")
    parser.add_argument("--no-persist", action="store_true",
                         help="Don't persist rail_check_results/rag_answers rows for this run.")
    args = parser.parse_args(argv)

    payload = _load_input(args.input_json)
    item_rows = [
        {"item_no": item.get("item_no", i + 1), "written_product": item["written_product"],
         "dose_frequency": item.get("dose_frequency", "")}
        for i, item in enumerate(payload["items"])
    ]

    conn = get_connection()
    trace = build_trace(conn, payload.get("rx_id", "DRAFT"), item_rows, payload["question"],
                         as_of_date=payload.get("as_of_date"), persist=not args.no_persist)
    conn.close()

    output = json.dumps(trace, indent=2, default=str)
    if args.out:
        with open(args.out, "w") as f:
            f.write(output)
    else:
        print(output)


if __name__ == "__main__":
    sys.exit(main())
