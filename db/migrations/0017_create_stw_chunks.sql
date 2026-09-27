-- One row per clinically meaningful decision unit -- a structural split on
-- each document's own printed section headings (ASSESS, FIRST-LINE
-- MANAGEMENT, RED FLAGS, DO NOT, REFER, etc. for the STWs; each numbered
-- step for the local protocol). Never a blind token slice.
CREATE TABLE stw_chunks (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id       INTEGER NOT NULL REFERENCES stw_documents(id),
    section_heading   TEXT NOT NULL,
    chunk_text        TEXT NOT NULL,
    position          INTEGER NOT NULL,
    page              INTEGER NOT NULL DEFAULT 1,
    created_at        TEXT NOT NULL,
    UNIQUE(document_id, position)
);
CREATE INDEX idx_stw_chunks_document ON stw_chunks(document_id);
