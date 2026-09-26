-- Event-sourced regulatory status (A.5 / A.6 check b). We never update a
-- status in place -- each gazette action is its own immutable event row.
-- "Current status" for a target ingredient/FDC set as of a given date is
-- derived at query time by picking the event with the latest effective_date
-- <= that date among events matching the same parsed target (see
-- src/module_a/regulatory/target_parser.py and DESIGN.md D-009). This lets a
-- later STAY_GRANTED or re-PROHIBITED event correctly override an earlier
-- one without ever mutating history.
CREATE TABLE regulatory_events (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id                 TEXT NOT NULL,
    notification_id          TEXT,
    date_published           TEXT,
    effective_date           TEXT NOT NULL,
    action                   TEXT NOT NULL,   -- PROHIBITED | RESTRICTED | STAY_GRANTED | WITHDRAWN (as declared by source)
    target_type              TEXT NOT NULL,   -- FDC | INGREDIENT | PRODUCT
    target_description       TEXT NOT NULL,
    target_ingredients_json  TEXT,            -- deterministic split of target_description into ingredient names; NULL for target_type=PRODUCT (see DESIGN.md D-012)
    scope_note                TEXT,           -- parenthetical qualifier extracted from target_description, if any (e.g. "paediatric suspensions only")
    supersedes_event_id      TEXT,            -- provenance/lineage only -- NOT used to compute current status, see connection.py-style note above
    note                     TEXT,
    source                   TEXT NOT NULL,
    load_batch_id            INTEGER NOT NULL REFERENCES load_batches(id),
    created_at                TEXT NOT NULL,
    UNIQUE(event_id, source)
);
CREATE INDEX idx_regulatory_events_target_type ON regulatory_events(target_type);
