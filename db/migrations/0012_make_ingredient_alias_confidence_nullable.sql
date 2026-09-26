-- ingredient_aliases.confidence was NOT NULL, forcing a 0.0 sentinel for
-- "not resolved" -- indistinguishable from a genuine zero-confidence score.
-- Recreated with confidence nullable so "unresolved" is represented as NULL,
-- consistent with product_resolutions.confidence (already nullable).
-- See DESIGN.md D-008.
PRAGMA foreign_keys = OFF;

CREATE TABLE ingredient_aliases_new (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_text        TEXT NOT NULL,
    ingredient_id   INTEGER REFERENCES ingredients(id),
    confidence      REAL,
    method          TEXT NOT NULL,
    source          TEXT NOT NULL,
    source_version  TEXT,
    load_batch_id   INTEGER NOT NULL REFERENCES load_batches(id),
    created_at      TEXT NOT NULL
);

INSERT INTO ingredient_aliases_new
    (id, raw_text, ingredient_id, confidence, method, source, source_version, load_batch_id, created_at)
SELECT
    id, raw_text, ingredient_id, NULLIF(confidence, 0.0), method, source, source_version, load_batch_id, created_at
FROM ingredient_aliases;

DROP TABLE ingredient_aliases;
ALTER TABLE ingredient_aliases_new RENAME TO ingredient_aliases;
CREATE INDEX idx_ingredient_aliases_raw ON ingredient_aliases(raw_text);

PRAGMA foreign_keys = ON;
