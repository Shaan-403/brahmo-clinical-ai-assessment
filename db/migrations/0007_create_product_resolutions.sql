-- Audit trail of every resolution ATTEMPT (not just the successful ones).
-- entity_type/entity_id point at the untrusted row being resolved (today:
-- pharmacy_stock_items; extensible later to prescription lines).
CREATE TABLE product_resolutions (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type             TEXT NOT NULL,
    entity_id               INTEGER NOT NULL,
    resolved_product_id     INTEGER REFERENCES products(id),   -- NULL if queued, not resolved
    status                  TEXT NOT NULL CHECK (status IN ('AUTO_RESOLVED','QUEUED_FOR_REVIEW')),
    confidence              REAL,
    method                  TEXT NOT NULL,
    candidates_json         TEXT NOT NULL,   -- every candidate considered, with scores
    created_at              TEXT NOT NULL
);
CREATE INDEX idx_product_resolutions_entity ON product_resolutions(entity_type, entity_id);
