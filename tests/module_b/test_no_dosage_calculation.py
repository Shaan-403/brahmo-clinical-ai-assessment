"""No patient-specific dosing calculation, ever: answer_question() is a
retrieval-and-quote function with no arithmetic step, so it cannot compute a
per-patient dose (e.g. weight-based mg) even when asked to. This is a
structural guarantee, not a prompt -- there is no code path in qa.py that
performs arithmetic on a number pulled from a chunk."""
import ast
import inspect

from src.module_b.answering import qa
from src.module_b.answering.qa import answer_question


def test_statement_text_is_never_built_from_arithmetic():
    """AST-level check (not a brittle string grep) scoped to the two
    functions that actually build what gets returned as answer text
    (_citation, _block): zero Mult/Div/FloorDiv/Pow/Mod nodes anywhere in
    them -- the exact operations a weight-based dose computation (mg/kg *
    patient weight) would require. answer_question()'s own
    best_score * ratio is a retrieval-confidence cutoff over scores, not a
    clinical value, and is deliberately outside this scope -- it never
    touches chunk_text or is reflected in a statement's text."""
    tree = ast.parse(inspect.getsource(qa))
    banned = (ast.Mult, ast.Div, ast.FloorDiv, ast.Pow, ast.Mod)
    text_building_fns = [n for n in ast.walk(tree)
                          if isinstance(n, ast.FunctionDef) and n.name in ("_citation", "_block")]
    assert len(text_building_fns) == 2
    offending = [n for fn in text_building_fns for n in ast.walk(fn)
                 if isinstance(n, ast.BinOp) and isinstance(n.op, banned)]
    assert offending == []


def test_answer_text_is_always_a_verbatim_chunk_never_a_computed_value(stw_conn):
    """Every statement returned is retrieved chunk text -- the answer never
    contains a number that isn't already sitting in the source text as-is
    (proving nothing was computed from it, e.g. multiplying a mg/kg figure
    by an assumed weight)."""
    result = answer_question(
        stw_conn,
        "A 6-year-old with non-severe community pneumonia: what is the amoxicillin dose exactly as the workflow states it?",
    )
    assert result["state"] == "ANSWERED"
    for block in result["answer"].values():
        for stmt in block["statements"]:
            match = stw_conn.execute("SELECT 1 FROM stw_chunks WHERE chunk_text=?", (stmt["text"],)).fetchone()
            assert match is not None, f"statement text is not an exact stored chunk: {stmt['text']!r}"
