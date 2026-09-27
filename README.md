# BRAHMO Clinical AI — Senior Engineering Assessment

Independent codebase built for the BRAHMO senior engineering assessment (Part 1: build spec; Part 2: plan in `docs/PART2_PLAN.md`).

## What this is
- **Module A** — India drug master + deterministic medication-safety rail (`src/module_a/`)
- **Module B** — grounded clinical Q&A slice / mini-RAG over the STW corpus (`src/module_b/`)
- **Module C** — single end-to-end trace tying A + B together (`src/module_c/`)

See `DESIGN.md` for the system restatement, riskiest assumptions, and the full decision log. See `SCALE.md` for where this strains at 100x/100 concurrent users. See `gaps_register.md` for known cuts and data anomalies.

## Fresh-machine setup (target: < 1 hour)

```bash
git clone <this-repo>
cd brahmo-clinical-ai
sudo apt-get install poppler-utils     # provides `pdftotext`; required by Module B's STW-corpus loader (macOS: brew install poppler)
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.lock.txt   # pinned, reproducible (use requirements.txt for loose ranges)
python -m src.module_a.ingest.run_all      # migrate + load the drug-master data pack (Module A)
python -m src.module_b.ingest.run_all      # migrate + load the STW corpus + local protocol, build chunk embeddings (Module B)
pytest                                     # run tests
python -m src.module_c.trace --help        # end-to-end trace
```

All Python dependencies are pure-Python/ONNX (no `torch`), so this installs in well under a minute on a normal connection. `fastembed` (ONNX-based) is used for local embeddings instead of `sentence-transformers`/`torch` — same hybrid-retrieval capability, far lighter — see `DESIGN.md` D-016 for the rationale, including the environment-specific fallback: if `fastembed`'s model download is blocked (e.g. by an egress policy on the model hub), `python -m src.module_b.ingest.run_all` automatically and visibly falls back to a deterministic offline TF-IDF backend and reports which one it used — no separate setup step is needed either way.

The one non-Python system dependency is `pdftotext` (from `poppler-utils`), used only by Module B's STW-corpus loader to extract text from the provided PDFs. `python -m src.module_b.ingest.run_all` fails fast with an actionable error if it isn't on `PATH`.

Both `run_all` entry points run their own migrations, so there's no separate `alembic upgrade head` (or equivalent) step to run first.

## Repository layout

```
config/           thresholds, source paths, review-queue rules — no hardcoded constants in src/
db/migrations/    numbered schema migrations (drug master, review queue, regulatory events, ...)
data/             provided data pack, unmodified (source of truth for ingestion)
corpus/           provided STW one-pagers (PDF) for Module B
src/module_a/     drug master, normalization, regulatory event engine, safety rail, review queue
src/module_b/     chunking, hybrid retrieval, grounded answering, mini-eval harness
src/module_c/     single end-to-end trace script/endpoint
prompts/          actual prompt library used during development, grouped by phase -- see prompts/00_README.md for scope and the one disclosed gap (early prompts lost to a context-compaction event)
tests/            unit + integration tests
eval_results/     mini-eval output, seeded rail outputs (checked in)
docs/             Part 2 plan
```

## Status
Modules A, B and C are implemented and tested: **112/112 tests pass in a clean Python 3.10 environment** with `pdftotext` on `PATH` (see "Fresh-machine setup" above and `CLAUDE.md`'s Python 3.10+ target) -- this is the configuration the suite was verified against. Running on a different active Python version, or without `pdftotext` installed, will not reproduce 112/112: missing `pdftotext` alone produces 21 STW-ingestion test errors (a missing system dependency, not a code defect), and an incompatible Python version can fail dependency installation entirely before any test runs. See `eval_results/` for the checked-in mini-eval and seeded-rail outputs. Part 2 (`docs/PART2_PLAN.md`) is complete, covering all 9 required sections. See `gaps_register.md` for known cuts and data anomalies.
