-- Semantic retrieval channel. `method` records which embedding backend
-- actually produced this vector (e.g. "fastembed:BAAI/bge-small-en-v1.5" or
-- the offline fallback "offline_tfidf_v1") -- see DESIGN.md D-016 for why a
-- fallback exists and is expected to be the one actually used in this
-- environment.
CREATE TABLE stw_chunk_embeddings (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    chunk_id     INTEGER NOT NULL UNIQUE REFERENCES stw_chunks(id),
    method       TEXT NOT NULL,
    vector_json  TEXT NOT NULL,
    dim          INTEGER NOT NULL,
    created_at   TEXT NOT NULL
);
