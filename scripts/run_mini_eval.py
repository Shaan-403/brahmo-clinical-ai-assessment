"""Reproducible artifact generator for the Module B mini-eval harness (B.4):
runs the 11 provided sample questions and writes a system-generated results
file a reviewer can read directly, with no test suite required.

Field provenance, kept explicit in every row so the two are never conflated:
  - expected_state / the sample question itself come from BRAHMO's own
    provided key (src/module_b/eval/sample_questions.py) -- fixed in advance,
    not produced by this run.
  - actual_state / verdict / citations_ok / text_ok / g6_problems are what
    the system actually produced THIS run.

Reuses run_eval() and answer_question() exactly as-is -- no scoring or
retrieval logic is duplicated here.

Usage:
    python -m scripts.run_mini_eval [--out PATH]
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

from src.config import REPO_ROOT
from src.db.connection import get_connection, migrate
from src.module_b.chunking.stw_loader import load_stw_corpus
from src.module_b.retrieval.semantic import build_chunk_embeddings
from src.module_b.eval.harness import run_eval

DEFAULT_OUT = REPO_ROOT / "eval_results" / "mini_eval_output.json"


def _ensure_module_b_loaded(conn) -> None:
    """Idempotent (content-hash keyed, see src/module_b/chunking/stw_loader.py);
    identical to what src/module_b/ingest/run_all.py does -- reused, not
    duplicated."""
    corpus_result = load_stw_corpus(conn)
    if corpus_result["skipped"]:
        row = conn.execute("SELECT 1 FROM stw_chunk_embeddings LIMIT 1").fetchone()
        if row is None:
            build_chunk_embeddings(conn, corpus_result["batch_id"])
    else:
        build_chunk_embeddings(conn, corpus_result["batch_id"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    conn = get_connection()
    migrate(conn)
    _ensure_module_b_loaded(conn)
    report = run_eval(conn)
    conn.close()

    payload = {
        "_generated_by": "scripts/run_mini_eval.py -- system-generated, do not hand-edit",
        "_field_note": ("expected_state and the question text come from BRAHMO's provided sample-question "
                         "key (src/module_b/eval/sample_questions.py), fixed in advance. actual_state, "
                         "verdict, citations_ok, text_ok and g6_problems are what the system produced on "
                         "this run."),
        "n_total": report["n_total"],
        "n_correct": report["n_correct"],
        "n_wrong": report["n_wrong"],
        "n_abstained_incorrectly": report["n_abstained_incorrectly"],
        "accuracy": report["accuracy"],
        "rows": report["rows"],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"{report['n_correct']}/{report['n_total']} correct ({report['accuracy']:.0%}) -> wrote {args.out}")


if __name__ == "__main__":
    sys.exit(main())
