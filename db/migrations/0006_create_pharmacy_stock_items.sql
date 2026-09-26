-- Raw pharmacy stock rows, stored verbatim. Untrusted real-world input:
-- never mutated in place, only referenced by downstream resolution attempts.
CREATE TABLE pharmacy_stock_items (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    item_name_as_billed    TEXT NOT NULL,
    qty_units              INTEGER,
    mrp_inr                REAL,
    batch                  TEXT,
    expiry                 TEXT,
    source                 TEXT NOT NULL,
    source_version         TEXT,
    load_batch_id          INTEGER NOT NULL REFERENCES load_batches(id),
    created_at             TEXT NOT NULL
);
