"""B.4 -- mini-eval: a small runnable harness scoring the system against the
11 provided sample questions (correct / abstained / wrong), plus a structural
G6 check (no uncited consequential clinical number).

"correct" requires more than the right ANSWERED/ABSTAINED/PARTIAL state: for
an ANSWERED/PARTIAL question it also requires every expected citation to
appear and every expected verbatim substring to appear in the returned text.
A right state with a missing citation or a paraphrased-away number is scored
"wrong", not "correct" -- state alone is not enough to claim quality.
"""
from __future__ import annotations
import re
import sqlite3

from src.module_b.answering.qa import answer_question
from src.module_b.eval.sample_questions import SAMPLE_QUESTIONS


def _all_statement_texts(answer: dict | None) -> list[tuple[str, dict]]:
    if not answer:
        return []
    out = []
    for block in answer.values():
        for stmt in block["statements"]:
            out.append((stmt["text"], stmt["citation"]))
    return out


def _all_citations_doc_codes(answer: dict | None) -> set[str]:
    return {c["doc_code"] for _, c in _all_statement_texts(answer)}


def _normalize_ws(s: str) -> str:
    """Collapse all whitespace runs to a single space so a verbatim-content
    comparison is not defeated by pdftotext's original indentation/line
    breaks vs. the stripped-and-rejoined chunk_text stored in stw_chunks.
    This does not touch wording -- only whitespace -- so it cannot let a
    fabricated or paraphrased claim pass as verbatim."""
    return re.sub(r"\s+", " ", s).strip()


def check_no_uncited_numeric_claims(conn: sqlite3.Connection, answer: dict | None) -> list[str]:
    """G6 structural check: every statement must carry a citation, and its
    text must be a verbatim substring of the cited document's stored raw
    text (whitespace-normalized on both sides) -- i.e. it was retrieved, not
    generated. Returns a list of problems (empty = clean)."""
    problems = []
    for text, citation in _all_statement_texts(answer):
        if not citation or not citation.get("doc_code"):
            problems.append(f"statement has no citation: {text!r}")
            continue
        row = conn.execute("SELECT raw_text FROM stw_documents WHERE doc_code=? AND version=?",
                            (citation["doc_code"], citation["version"])).fetchone()
        if row is None or _normalize_ws(text) not in _normalize_ws(row["raw_text"]):
            problems.append(f"statement text not found verbatim in cited document {citation['doc_code']} "
                             f"v{citation['version']}: {text!r}")
    return problems


def _score_one(conn: sqlite3.Connection, spec: dict) -> dict:
    result = answer_question(conn, spec["question"], persist=True)
    actual_state = result["state"]
    state_ok = actual_state == spec["expected_state"]

    citations_ok, text_ok, missing_source_ok = True, True, True
    if spec["expected_state"] in ("ANSWERED", "PARTIAL"):
        got_codes = _all_citations_doc_codes(result.get("answer"))
        citations_ok = set(spec.get("expect_doc_codes", [])) <= got_codes

        all_text = " ".join(t for t, _ in _all_statement_texts(result.get("answer")))
        text_ok = all(substr in all_text for substr in spec.get("expect_text_contains", []))

        if spec["expected_state"] == "PARTIAL" and "expect_missing_source_type" in spec:
            missing_source_ok = spec["expect_missing_source_type"] not in (result.get("answer") or {})

        if "expect_version" in spec:
            versions_used = {c["version"] for _, c in _all_statement_texts(result.get("answer"))}
            citations_ok = citations_ok and spec["expect_version"] in versions_used

    g6_problems = check_no_uncited_numeric_claims(conn, result.get("answer"))

    passed = state_ok and citations_ok and text_ok and missing_source_ok and not g6_problems
    verdict = "correct" if passed else ("abstained" if actual_state == "ABSTAINED" else "wrong")

    return {
        "id": spec["id"], "question": spec["question"], "expected_state": spec["expected_state"],
        "actual_state": actual_state, "verdict": verdict, "state_ok": state_ok,
        "citations_ok": citations_ok, "text_ok": text_ok, "missing_source_ok": missing_source_ok,
        "g6_problems": g6_problems, "rag_answer_id": result.get("id"),
    }


def run_eval(conn: sqlite3.Connection) -> dict:
    rows = [_score_one(conn, spec) for spec in SAMPLE_QUESTIONS]
    n_correct = sum(1 for r in rows if r["verdict"] == "correct")
    return {
        "rows": rows,
        "n_total": len(rows),
        "n_correct": n_correct,
        "n_abstained_incorrectly": sum(1 for r in rows if r["verdict"] == "abstained"),
        "n_wrong": sum(1 for r in rows if r["verdict"] == "wrong"),
        "accuracy": n_correct / len(rows) if rows else 0.0,
    }


def print_report(report: dict) -> None:
    for r in report["rows"]:
        print(f"[{r['verdict'].upper():9}] {r['id']}: expected={r['expected_state']:9} actual={r['actual_state']:9} "
              f"citations_ok={r['citations_ok']} text_ok={r['text_ok']}"
              + (f" g6_problems={r['g6_problems']}" if r["g6_problems"] else ""))
    print(f"\n{report['n_correct']}/{report['n_total']} correct ({report['accuracy']:.0%})")
