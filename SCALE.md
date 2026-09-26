# SCALE.md — where this design strains at 100x data volume / 100 concurrent users

_One page maximum. Feeds directly into the Part 2 plan._

## Data volume (100x)
- SQLite is fine for 2,000 products / ~800 stock rows; it is not fine for a national drug catalog (hundreds of thousands of products) with concurrent writers. First thing to change: Postgres, with the same migration SQL ported (they're plain DDL, no SQLite-specific syntax used deliberately).
- The pharmacy-item resolver currently loads the full `products` table into memory once per unmatched item to build the fuzzy-search index (`src/module_a/normalize/pharmacy_matcher.py`). Fine at 2,000 rows; needs a persistent search index (e.g. a trigram or phonetic index in Postgres, or a proper search service) at 100x.
- The review queue itself becomes an operational surface at scale, not just a table — 574/783 rows queued from a single 2,000-product subset suggests a national dataset would produce a review queue in the tens of thousands. That needs its own triage UI, assignment, and SLA tracking, not just a SQL table.

## Concurrency (100 simultaneous doctors)
- SQLite's single-writer model is the first hard wall — any concurrent ingestion run (a new gazette notification, a new pharmacy upload) would serialize against reads. Postgres with proper row-level locking is required before real concurrent load.
- The ingestion pipeline is currently a synchronous, single-process script (`run_all.py`). At scale this needs to be an idempotent, queue-driven job (so a partial failure mid-file doesn't require re-running the whole batch) with per-row retry rather than per-file all-or-nothing.

## What I'd change first
1. Postgres instead of SQLite (migrations are already portable SQL).
2. Turn the ambiguous-brand problem (D-001) into a first-class product-family concept with a real disambiguation UI for doctors, rather than leaving every ambiguous brand mention to land in an internal review queue — at national-catalog scale, doctors themselves are the fastest disambiguation signal (they know what they meant to prescribe), not a back-office queue.
3. A resolved-alias feedback loop (gaps register #5) so a human's resolution of one ambiguous case actually reduces future queue volume, instead of the queue regrowing identically on every ingestion run.
