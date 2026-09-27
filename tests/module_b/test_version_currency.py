"""Version-currency filtering: STW-GP-02 exists in this corpus as both the
current 2025.2 edition and an archived 2021.1 edition. The default path must
always answer from the current edition and never silently blend the two."""
from src.module_b.answering.qa import answer_question
from src.module_b.retrieval.hybrid import hybrid_search


def _versions_cited(answer: dict) -> set[str]:
    versions = set()
    for block in answer.values():
        for stmt in block["statements"]:
            versions.add(stmt["citation"]["version"])
    return versions


def test_default_answer_cites_only_the_current_edition(stw_conn):
    result = answer_question(stw_conn, "What is the first-line initial drug therapy for newly diagnosed adult hypertension?")
    assert result["state"] == "ANSWERED"
    versions = _versions_cited(result["answer"])
    assert versions == {"2025.2"}


def test_default_hybrid_search_excludes_the_archived_edition_entirely(stw_conn):
    hits = hybrid_search(stw_conn, "hypertension first-line drug therapy", top_k=49)
    gp02_versions = {h["version"] for h in hits if h["doc_code"] == "STW-GP-02"}
    assert gp02_versions == {"2025.2"}


def test_include_superseded_makes_the_archived_edition_reachable_but_explicit(stw_conn):
    """The archived edition must never surface silently -- but it must still
    be reachable when explicitly asked for (replayability), each chunk
    carrying its own version/is_current so the two editions are never
    conflated."""
    hits = hybrid_search(stw_conn, "hypertension first-line drug therapy", top_k=49, include_superseded=True)
    gp02_versions = {h["version"] for h in hits if h["doc_code"] == "STW-GP-02"}
    assert gp02_versions == {"2025.2", "2021.1"}
    for h in hits:
        if h["doc_code"] == "STW-GP-02":
            assert h["is_current"] == (h["version"] == "2025.2")
