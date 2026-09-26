-- Canonical active-ingredient (salt) registry. One row per distinct molecule.
CREATE TABLE ingredients (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_name              TEXT NOT NULL UNIQUE,   -- first-seen display casing
    normalized_key              TEXT NOT NULL UNIQUE,   -- casefolded/whitespace-collapsed match key
    first_seen_source           TEXT NOT NULL,
    first_seen_source_version   TEXT,
    first_seen_load_batch_id    INTEGER NOT NULL REFERENCES load_batches(id),
    created_at                  TEXT NOT NULL
);
