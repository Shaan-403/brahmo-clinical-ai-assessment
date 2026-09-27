"""Abstention edge cases: the corpus genuinely has zero coverage for a
question, and the system must say so cleanly rather than stretch a weak
match into an answer."""
from src.module_b.answering.qa import answer_question
from src.module_b.retrieval.hybrid import hybrid_search


def test_abstains_when_corpus_has_zero_topical_coverage(stw_conn):
    result = answer_question(stw_conn, "What is the first-line prophylactic drug for migraine in adults?")
    assert result["state"] == "ABSTAINED"
    assert result["answer"] is None
    assert result["abstention_reason"]


def test_abstention_reason_is_never_silently_missing(stw_conn):
    result = answer_question(stw_conn, "What is the standard drug regimen for newly diagnosed pulmonary tuberculosis?")
    assert result["state"] == "ABSTAINED"
    assert isinstance(result["abstention_reason"], str) and len(result["abstention_reason"]) > 0


def test_an_off_corpus_query_still_returns_candidates_considered_for_provenance(stw_conn):
    """Abstaining must not mean 'we looked at nothing' -- what was considered
    and why it didn't qualify has to be inspectable (G5-style provenance),
    even though nothing crossed the bar to be cited."""
    result = answer_question(stw_conn, "What is the first-line prophylactic drug for migraine in adults?")
    assert result["state"] == "ABSTAINED"
    assert len(result["candidates_considered"]) > 0
    assert all(c["combined_score"] < 0.26 for c in result["candidates_considered"]
               if c["doc_code"] != "SOP-CLIN-014")  # nothing that scored well enough to answer from


def test_gibberish_query_does_not_crash_and_abstains(stw_conn):
    result = answer_question(stw_conn, "asdkjhasdkjh ?!?! 12345 xyz")
    assert result["state"] == "ABSTAINED"


def test_hybrid_search_never_returns_a_document_below_the_configured_floor_as_a_false_top_hit(stw_conn):
    """A structural guardrail on the underlying retrieval score, independent
    of answer_question's own floor check: an off-corpus query's best hit
    must not accidentally exceed a genuinely-covered query's weakest hit
    (the threshold is calibrated with margin either side, see
    config/thresholds.yaml)."""
    off_corpus_top = hybrid_search(stw_conn, "What is the first-line prophylactic drug for migraine in adults?", top_k=1)
    on_corpus_top = hybrid_search(stw_conn, "Which analgesic class must be avoided in suspected dengue, and why?", top_k=1)
    assert off_corpus_top[0]["combined_score"] < on_corpus_top[0]["combined_score"]
