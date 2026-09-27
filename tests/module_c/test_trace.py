"""Module C end-to-end: build_trace() is the single integration point tying
Module A's Safety Rail and Module B's grounded answering together. These
tests exercise it exactly as the brief's "one script or endpoint" would be
used: a draft prescription (not one of the seed CSV rx_ids -- a fresh draft,
entered directly) plus one clinical question, in, one JSON-shaped trace out.
"""
from src.module_c.trace import build_trace

# Same real composition as the seed pack's RX01 (Dolo 650 + Sinarest Tablet,
# both contain Paracetamol) -- a known duplicate-active-ingredient HIT,
# entered here as a fresh draft rather than read from the CSV, since Module
# C's contract is "takes a draft prescription", not "takes an rx_id".
KNOWN_BAD_ITEMS = [
    {"item_no": 1, "written_product": "Dolo 650", "dose_frequency": "1-0-1 x 5d"},
    {"item_no": 2, "written_product": "Sinarest Tablet", "dose_frequency": "1-0-1 x 5d"},
]
SUPPORTED_QUESTION = "What is the first-line antibiotic, dose basis, and duration for acute otitis media in a child?"

UNRESOLVED_ITEMS = [
    {"item_no": 1, "written_product": "Totally Unknown Brand XYZ-9000", "dose_frequency": "1-0-1"},
]
UNSUPPORTED_QUESTION = "What is the standard drug regimen for newly diagnosed pulmonary tuberculosis?"

# Same real composition as the seed pack's RX07 (Calpol 650 x3/day + Crocin
# 650 SOS) -- both share Paracetamol, but Crocin's "SOS" frequency doesn't
# parse to a doses-per-day count, so the cumulative exposure check must
# report PARTIAL_COVERAGE, never silently drop the item or treat it as zero.
UNPARSEABLE_EXPOSURE_ITEMS = [
    {"item_no": 1, "written_product": "Calpol 650", "dose_frequency": "1-1-1 x 3d"},
    {"item_no": 2, "written_product": "Crocin 650", "dose_frequency": "SOS"},
]


def test_known_bad_prescription_with_supported_question(full_conn):
    trace = build_trace(full_conn, "DRAFT-KNOWN-BAD", KNOWN_BAD_ITEMS, SUPPORTED_QUESTION, persist=False)

    # prescription normalization: both items resolve, ingredients decomposed
    assert trace["prescription_normalization"]["unresolved_items"] == []
    resolved = trace["prescription_normalization"]["resolved_items"]
    assert {r["written_product"] for r in resolved} == {"Dolo 650", "Sinarest Tablet"}
    assert all(r["ingredients"] for r in resolved)

    # all safety-rail checks ran and returned a mandated 8-state value
    valid_states = {"HIT", "CHECKED_NO_HIT", "PARTIAL_COVERAGE", "UNVERIFIED_INPUT",
                     "NOT_CHECKED", "DATA_EXPIRED", "SOURCE_CONFLICT", "SERVICE_UNAVAILABLE"}
    assert set(trace["safety_rail"].keys()) == {
        "duplicate_active_ingredient", "prohibited_restricted_fdc", "severe_interaction",
        "cumulative_daily_exposure",
    }
    for check_name, results in trace["safety_rail"].items():
        for r in results:
            assert r["state"] in valid_states
            assert r["rule_version"]
            assert r["data_versions"]

    # the known-bad duplicate-paracetamol case is actually caught, with the
    # cumulative daily total attached as evidence per D-011
    dup_results = trace["safety_rail"]["duplicate_active_ingredient"]
    assert any(r["state"] == "HIT" for r in dup_results)
    hit = next(r for r in dup_results if r["state"] == "HIT")
    assert hit["evidence"]["ingredient"] == "Paracetamol"
    assert hit["evidence"]["cumulative_daily_mg"] is not None

    # check (d), cumulative_daily_exposure, is a SEPARATE check from (a) above:
    # both Dolo 650 and Sinarest Tablet have parseable dose_frequency values,
    # so exposure coverage is complete -- CHECKED_NO_HIT, never HIT (D-011/D-019).
    exposure_results = trace["safety_rail"]["cumulative_daily_exposure"]
    assert len(exposure_results) == 1
    assert exposure_results[0]["state"] == "CHECKED_NO_HIT"
    assert exposure_results[0]["severity"] is None
    paracetamol = next(e for e in exposure_results[0]["evidence"]["shared_ingredient_exposure"]
                        if e["ingredient"] == "Paracetamol")
    assert paracetamol["cumulative_is_partial"] is False
    assert paracetamol["cumulative_daily_mg"] is not None

    # module B answered the supported question with a real citation
    answer = trace["module_b_answer"]
    assert answer["state"] == "ANSWERED"
    assert answer["answer"]

    # versions block is populated: datasets, rail rule versions, and an
    # explicit (not silently missing) statement about prompt/model usage
    versions = trace["versions"]
    assert versions["dataset_versions"]["cdci"] is not None
    assert versions["safety_rail_rule_versions"]["duplicate_active_ingredient"]
    assert versions["safety_rail_rule_versions"]["cumulative_daily_exposure"]
    assert versions["module_b_retrieval_method"]
    assert versions["prompt_model_versions"]["llm_used"] is False


def test_unresolved_input_with_unsupported_question(full_conn):
    trace = build_trace(full_conn, "DRAFT-UNRESOLVED", UNRESOLVED_ITEMS, UNSUPPORTED_QUESTION, persist=False)

    # the written_product never resolves -- surfaced directly, not silently dropped
    assert trace["prescription_normalization"]["resolved_items"] == []
    assert len(trace["prescription_normalization"]["unresolved_items"]) == 1
    assert trace["prescription_normalization"]["unresolved_items"][0]["written_product"] == \
        "Totally Unknown Brand XYZ-9000"

    # every rail check must report UNVERIFIED_INPUT, never silently skip or
    # render missing data as safe (e.g. never CHECKED_NO_HIT)
    for check_name, results in trace["safety_rail"].items():
        assert all(r["state"] == "UNVERIFIED_INPUT" for r in results), (check_name, results)

    # the corpus has no coverage for tuberculosis -- module B must abstain
    # cleanly rather than stretch a weak match into an answer
    answer = trace["module_b_answer"]
    assert answer["state"] == "ABSTAINED"
    assert answer["answer"] is None
    assert answer["abstention_reason"]

    # the trace is still fully populated even though nothing could be
    # checked/answered -- provenance/versions are never silently dropped
    assert trace["versions"]["dataset_versions"]["cdci"] is not None
    assert trace["versions"]["prompt_model_versions"]["llm_used"] is False


def test_trace_is_json_serializable(full_conn):
    """The whole point is a JSON trace -- guard against a future evidence
    field accidentally carrying a non-serializable value (e.g. a raw sqlite
    Row or a set)."""
    import json
    trace = build_trace(full_conn, "DRAFT-KNOWN-BAD", KNOWN_BAD_ITEMS, SUPPORTED_QUESTION, persist=False)
    json.dumps(trace)  # must not raise


def test_unparseable_sos_exposure_is_partial_coverage_never_hit(full_conn):
    """The unparseable/"SOS"-frequency edge case for check (d): coverage is
    incomplete (one contribution can't be totaled), so the state must be
    PARTIAL_COVERAGE -- and it must still never be HIT, per D-011/D-019,
    even though the SAME overlap is enough to make check (a) fire a real
    duplicate_active_ingredient HIT on this exact prescription."""
    trace = build_trace(full_conn, "DRAFT-SOS-EXPOSURE", UNPARSEABLE_EXPOSURE_ITEMS,
                         SUPPORTED_QUESTION, persist=False)

    assert trace["prescription_normalization"]["unresolved_items"] == []

    # check (a) still fires its own HIT for this Paracetamol overlap...
    dup_results = trace["safety_rail"]["duplicate_active_ingredient"]
    assert any(r["state"] == "HIT" for r in dup_results)

    # ...but check (d) is independent: PARTIAL_COVERAGE (not HIT, not
    # CHECKED_NO_HIT), with the SOS item named explicitly, not dropped or
    # assumed to contribute zero.
    exposure_results = trace["safety_rail"]["cumulative_daily_exposure"]
    assert len(exposure_results) == 1
    exposure = exposure_results[0]
    assert exposure["state"] == "PARTIAL_COVERAGE"
    assert exposure["severity"] is None
    paracetamol = next(e for e in exposure["evidence"]["shared_ingredient_exposure"]
                        if e["ingredient"] == "Paracetamol")
    assert paracetamol["cumulative_is_partial"] is True
    assert paracetamol["cumulative_daily_mg"] is not None  # the parseable Calpol contribution is still totaled
    excluded = paracetamol["items_excluded_from_total_due_to_unparseable_frequency"]
    assert len(excluded) == 1
    assert excluded[0]["written_product"] == "Crocin 650"
    assert excluded[0]["dose_frequency_raw"] == "SOS"
