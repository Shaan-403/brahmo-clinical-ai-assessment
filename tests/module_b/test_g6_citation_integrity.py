"""G6: no uncited consequential clinical number in Module B output. Every
statement must carry a citation, and that citation's text must be a
genuine, verbatim (whitespace aside) substring of the cited document's
stored raw text -- proving it was retrieved, not generated or paraphrased."""
from src.module_b.answering.qa import answer_question
from src.module_b.eval.harness import check_no_uncited_numeric_claims, _normalize_ws


def test_real_answers_are_always_g6_clean(stw_conn):
    for question in [
        "What is the first-line antibiotic, dose basis, and duration for acute otitis media in a child?",
        "At what HbA1c threshold at diagnosis does the workflow add a second agent to metformin, and which agent?",
        "Which urinary antibiotic is avoided at 36+ weeks of pregnancy, and what is the stated alternative?",
    ]:
        result = answer_question(stw_conn, question)
        assert result["state"] == "ANSWERED"
        problems = check_no_uncited_numeric_claims(stw_conn, result["answer"])
        assert problems == [], f"{question!r} -> {problems}"


def test_a_statement_with_no_citation_is_flagged(stw_conn):
    fake_answer = {"national_stw": {"source_type": "national_stw", "label": "national workflow",
                                     "statements": [{"text": "Amoxicillin 40 mg/kg/day", "citation": None}]}}
    problems = check_no_uncited_numeric_claims(stw_conn, fake_answer)
    assert len(problems) == 1
    assert "no citation" in problems[0]


def test_a_fabricated_statement_text_is_flagged_even_with_a_real_citation(stw_conn):
    real = answer_question(stw_conn, "At what HbA1c threshold at diagnosis does the workflow add a second agent to metformin, and which agent?")
    real_citation = next(iter(real["answer"].values()))["statements"][0]["citation"]
    fabricated_answer = {"national_stw": {"source_type": "national_stw", "label": "national workflow",
                                           "statements": [{"text": "Metformin 2000 mg immediately, no titration",
                                                            "citation": real_citation}]}}
    problems = check_no_uncited_numeric_claims(stw_conn, fabricated_answer)
    assert len(problems) == 1
    assert "not found verbatim" in problems[0]


def test_normalize_ws_only_touches_whitespace_never_wording():
    a = "line one\n   line two  with   extra spaces"
    b = "line one line two with extra spaces"
    assert _normalize_ws(a) == _normalize_ws(b)
    assert _normalize_ws("Amoxicillin") != _normalize_ws("Azithromycin")
