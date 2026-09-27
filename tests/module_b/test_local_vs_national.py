"""Local-vs-national comparison: the local protocol addresses one condition
(adult acute undifferentiated fever) that the national STW pack does not
separately cover in this corpus. The brief requires the missing side to be
named explicitly, never silently dropped, and never merged into one
synthesized recommendation."""
from src.module_b.answering.qa import answer_question


def test_local_protocol_question_is_partial_with_national_side_named_missing(stw_conn):
    result = answer_question(
        stw_conn,
        "Per the clinic's own protocol, when are empirical antibiotics started in adult acute undifferentiated "
        "fever, and does the national workflow pack say the same?",
    )
    assert result["state"] == "PARTIAL"
    assert "local_protocol" in result["answer"]
    assert "national_stw" not in result["answer"]
    assert result["abstention_reason"]
    assert "national" in result["abstention_reason"].lower()


def test_local_protocol_block_is_labeled_as_the_clinics_own_not_national_guidance(stw_conn):
    result = answer_question(
        stw_conn,
        "Per the clinic's own protocol, when are empirical antibiotics started in adult acute undifferentiated "
        "fever, and does the national workflow pack say the same?",
    )
    label = result["answer"]["local_protocol"]["label"]
    assert "clinic" in label.lower()


def test_local_and_national_are_never_merged_into_one_statement_list(stw_conn):
    """Even in the (not-present-in-this-corpus) case where both sides
    matched, the contract is separate blocks per source_type -- this test
    pins that shape so a future change can't quietly flatten it."""
    result = answer_question(
        stw_conn,
        "Per the clinic's own protocol, when are empirical antibiotics started in adult acute undifferentiated "
        "fever, and does the national workflow pack say the same?",
    )
    assert isinstance(result["answer"], dict)
    for source_type, block in result["answer"].items():
        assert block["source_type"] == source_type


def test_source_type_filter_scopes_to_national_only_and_finds_nothing_here(stw_conn):
    """Explicitly filtering to national_stw for this fever question must not
    fall back to the local protocol -- it should abstain, since the filter
    is a hard scope, not a preference."""
    result = answer_question(
        stw_conn,
        "When are empirical antibiotics started in adult acute undifferentiated fever?",
        source_type_filter="national_stw",
    )
    assert result["state"] == "ABSTAINED"
