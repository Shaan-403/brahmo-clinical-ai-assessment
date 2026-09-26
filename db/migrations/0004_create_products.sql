-- One row per source product row (CDCI's product_id is the real identity).
-- brand_name is deliberately NOT unique: this dataset has 565 brand names
-- shared by 2+ unrelated formulations (see DESIGN.md D-001). Never join on
-- brand_name alone and treat the result as resolved.
CREATE TABLE products (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    external_product_id    TEXT NOT NULL,
    brand_name              TEXT NOT NULL,
    brand_name_normalized   TEXT NOT NULL,
    manufacturer            TEXT,
    dose_form               TEXT,
    strength_text           TEXT,
    source                  TEXT NOT NULL,
    source_version          TEXT NOT NULL,
    effective_from          TEXT,
    load_batch_id           INTEGER NOT NULL REFERENCES load_batches(id),
    raw_row_json            TEXT NOT NULL,
    created_at               TEXT NOT NULL,
    UNIQUE(external_product_id, source)
);
CREATE INDEX idx_products_brand_normalized ON products(brand_name_normalized);
