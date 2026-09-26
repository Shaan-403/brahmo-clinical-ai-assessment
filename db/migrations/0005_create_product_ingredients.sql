-- FDC decomposition: one row per (product, ingredient) pair. A product with
-- 3 rows here is a 3-ingredient fixed-dose combination.
CREATE TABLE product_ingredients (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id      INTEGER NOT NULL REFERENCES products(id),
    ingredient_id   INTEGER NOT NULL REFERENCES ingredients(id),
    position        INTEGER NOT NULL,   -- 1, 2, 3 = order within the FDC as declared by source
    strength_mg     REAL,
    strength_raw    TEXT,
    confidence      REAL NOT NULL,
    method          TEXT NOT NULL,
    source          TEXT NOT NULL,
    source_version  TEXT,
    load_batch_id   INTEGER NOT NULL REFERENCES load_batches(id),
    created_at      TEXT NOT NULL,
    UNIQUE(product_id, position)
);
CREATE INDEX idx_product_ingredients_ingredient ON product_ingredients(ingredient_id);
