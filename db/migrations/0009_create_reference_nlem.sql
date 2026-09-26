-- NLEM extract, kept 1:1 as reference data, cross-linked to the canonical
-- ingredient registry where a mapping could be made.
CREATE TABLE reference_nlem (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    medicine                TEXT NOT NULL,
    therapeutic_category    TEXT,
    care_levels             TEXT,
    nlem_edition            TEXT,
    matched_ingredient_id   INTEGER REFERENCES ingredients(id),
    match_status            TEXT NOT NULL CHECK (match_status IN ('EXACT','QUEUED')),
    source                  TEXT NOT NULL,
    source_version          TEXT,
    load_batch_id           INTEGER NOT NULL REFERENCES load_batches(id),
    created_at              TEXT NOT NULL
);
