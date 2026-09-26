-- Jan Aushadhi extract, kept 1:1 as reference data, cross-linked to the
-- canonical ingredient registry where a mapping could be made.
CREATE TABLE reference_jan_aushadhi (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    generic_name            TEXT NOT NULL,
    strength                TEXT,
    pack                    TEXT,
    mrp_inr                 REAL,
    catalog_version         TEXT,
    matched_ingredient_id   INTEGER REFERENCES ingredients(id),
    match_status            TEXT NOT NULL CHECK (match_status IN ('EXACT','QUEUED')),
    source                  TEXT NOT NULL,
    source_version          TEXT,
    load_batch_id           INTEGER NOT NULL REFERENCES load_batches(id),
    created_at              TEXT NOT NULL
);
