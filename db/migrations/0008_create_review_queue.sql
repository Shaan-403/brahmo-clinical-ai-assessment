-- Every uncertain mapping lands here with a reason code. Nothing here is
-- ever auto-resolved by the pipeline; a human (or a later, explicit
-- decision) clears it.
CREATE TABLE review_queue (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type         TEXT NOT NULL,
    entity_id           INTEGER NOT NULL,
    reason_code         TEXT NOT NULL,
    candidates_json     TEXT,
    status              TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','RESOLVED','REJECTED')),
    created_at          TEXT NOT NULL,
    resolved_at         TEXT,
    resolved_by         TEXT,
    resolution_note     TEXT
);
CREATE INDEX idx_review_queue_status ON review_queue(status);
CREATE INDEX idx_review_queue_entity ON review_queue(entity_type, entity_id);
