-- Module B, document-level metadata. Two editions of the same workflow (e.g.
-- STW-GP-02 2025.2 and its archived 2021.1 predecessor) share doc_code but
-- are separate rows -- current-vs-superseded is resolved the same way as
-- Module A's regulatory events (latest effective_date wins), not by
-- assuming a doc_code is unique. See DESIGN.md D-015.
CREATE TABLE stw_documents (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_code              TEXT NOT NULL,
    title                 TEXT NOT NULL,
    specialty             TEXT,
    condition             TEXT,
    source_type           TEXT NOT NULL CHECK (source_type IN ('national_stw', 'local_protocol')),
    version               TEXT NOT NULL,
    effective_date        TEXT NOT NULL,
    is_current            INTEGER NOT NULL DEFAULT 1,   -- computed at ingest: 1 for the latest effective_date per doc_code, else 0
    org                   TEXT,                          -- e.g. "Sunrise Multi-speciality Clinic" for local_protocol rows
    file_path             TEXT NOT NULL,
    source                TEXT NOT NULL,
    load_batch_id         INTEGER NOT NULL REFERENCES load_batches(id),
    raw_text              TEXT NOT NULL,
    created_at            TEXT NOT NULL,
    UNIQUE(doc_code, version)
);
CREATE INDEX idx_stw_documents_doc_code ON stw_documents(doc_code);
CREATE INDEX idx_stw_documents_source_type ON stw_documents(source_type);
