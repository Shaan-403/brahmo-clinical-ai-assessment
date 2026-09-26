-- Seed list of known severe pairwise interactions. Ingredient names go
-- through the SAME exact-match-only-auto-resolve discipline as any other
-- untrusted secondary source (resolve_reference_ingredient) -- this file is
-- not treated as authoritative enough to mint new canonical ingredients.
-- A pair with an ingredient that doesn't exactly match the canonical
-- registry is queued for review like any other alias, and is excluded from
-- automated interaction matching until resolved -- see DESIGN.md D-010 for
-- why that makes the interaction check report PARTIAL_COVERAGE rather than
-- CHECKED_NO_HIT whenever any interaction row is unresolved.
CREATE TABLE severe_interactions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    ingredient_a_raw    TEXT NOT NULL,
    ingredient_b_raw    TEXT NOT NULL,
    ingredient_a_id     INTEGER REFERENCES ingredients(id),
    ingredient_b_id     INTEGER REFERENCES ingredients(id),
    severity            TEXT NOT NULL,
    note                TEXT,
    source_tag          TEXT,
    source              TEXT NOT NULL,
    load_batch_id       INTEGER NOT NULL REFERENCES load_batches(id),
    created_at           TEXT NOT NULL
);
