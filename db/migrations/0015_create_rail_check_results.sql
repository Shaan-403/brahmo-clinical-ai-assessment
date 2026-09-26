-- Append-only log of every Safety Rail check run. Never updated in place --
-- binding law "everything versioned, everything replayable" applies to rail
-- verdicts exactly as it does to ingested data rows. rule_version identifies
-- the check logic version; data_versions_json pins the exact load_batches
-- (source + file_hash/source_version) the verdict was computed against, so
-- any past result can be explained or replayed later.
--
-- Deliberately NO overall_state / prescription-level rollup column -- each
-- check keeps its own independent state, per explicit engineering decision.
CREATE TABLE rail_check_results (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    rx_id               TEXT NOT NULL,
    check_name          TEXT NOT NULL,   -- duplicate_active_ingredient | prohibited_restricted_fdc | severe_interaction
    state               TEXT NOT NULL,   -- one of the 8 mandated rail states
    severity            TEXT,
    evidence_json       TEXT NOT NULL,
    rule_version        TEXT NOT NULL,
    data_versions_json  TEXT NOT NULL,
    as_of_date          TEXT NOT NULL,
    evaluated_at        TEXT NOT NULL
);
CREATE INDEX idx_rail_check_results_rx ON rail_check_results(rx_id);
CREATE INDEX idx_rail_check_results_check ON rail_check_results(check_name);
