-- Every ingested file gets one load_batches row. All downstream rows carry a
-- load_batch_id so any check result is reproducible against the exact data
-- version used to produce it.
CREATE TABLE load_batches (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name     TEXT NOT NULL,
    source_version  TEXT,
    file_path       TEXT NOT NULL,
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    row_count       INTEGER,
    status          TEXT NOT NULL DEFAULT 'RUNNING' CHECK (status IN ('RUNNING','COMPLETE','FAILED')),
    notes           TEXT
);
