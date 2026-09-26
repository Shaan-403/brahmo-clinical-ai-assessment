-- Every raw ingredient-name string ever encountered, and which canonical
-- ingredient (if any) it was mapped to, plus how confident that mapping is.
-- ingredient_id is NULL when the mapping is unresolved (queued for review).
CREATE TABLE ingredient_aliases (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_text        TEXT NOT NULL,
    ingredient_id   INTEGER REFERENCES ingredients(id),
    confidence      REAL NOT NULL,
    method          TEXT NOT NULL,   -- structured_source_field | exact_normalized_match | fuzzy_candidate_unconfirmed
    source          TEXT NOT NULL,
    source_version  TEXT,
    load_batch_id   INTEGER NOT NULL REFERENCES load_batches(id),
    created_at      TEXT NOT NULL
);
CREATE INDEX idx_ingredient_aliases_raw ON ingredient_aliases(raw_text);
