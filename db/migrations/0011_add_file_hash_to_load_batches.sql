-- Supports idempotent ingestion: a loader hashes the source file's content
-- and checks whether a COMPLETE batch already exists for that exact
-- (source_name, file_hash) pair before inserting anything. This is also the
-- "load batch/content identity" fallback for sources with no declared
-- version (e.g. pharmacy_stock.csv has no version column at all) -- see
-- DESIGN.md D-007 and gaps_register.md.
ALTER TABLE load_batches ADD COLUMN file_hash TEXT;
CREATE INDEX idx_load_batches_source_hash ON load_batches(source_name, file_hash);
