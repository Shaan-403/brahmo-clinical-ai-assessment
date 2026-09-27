-- Persisted vocabulary/IDF for the offline TF-IDF fallback embedder, so a
-- query embedded later uses the exact same vocabulary the corpus vectors
-- were built from (see DESIGN.md D-016) rather than an inconsistent
-- recompute. Irrelevant when the fastembed backend is actually available.
CREATE TABLE stw_tfidf_vocab (
    term            TEXT PRIMARY KEY,
    idf             REAL NOT NULL,
    load_batch_id   INTEGER NOT NULL REFERENCES load_batches(id)
);
