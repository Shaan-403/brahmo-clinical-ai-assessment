-- Append-only log of every Module B answer, mirroring rail_check_results'
-- provenance discipline (binding law: everything versioned, everything
-- replayable). state is one of ANSWERED | ABSTAINED | PARTIAL (a comparison
-- answer where one side -- almost always the national side -- has no
-- matching document in the corpus).
CREATE TABLE rag_answers (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    question              TEXT NOT NULL,
    state                 TEXT NOT NULL,
    answer_json           TEXT NOT NULL,
    abstention_reason     TEXT,
    retrieval_method      TEXT NOT NULL,
    filters_applied_json  TEXT,
    evaluated_at          TEXT NOT NULL
);
