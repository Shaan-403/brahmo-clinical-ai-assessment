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
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.lock.txt   # pinned, reproducible (use requirements.txt for loose ranges)
cp .env.example .env            # fill in any required keys (e.g. LLM API key for AI-assisted mapping/answering)
alembic upgrade head            # run schema migrations
python -m src.module_a.ingest.run_all      # load the data pack
pytest                                     # run tests
python -m src.module_c.trace --help        # end-to-end trace
```

All dependencies are pure-Python/ONNX (no `torch`), so this installs in well under a minute on a normal connection. `fastembed` (ONNX-based) is used for local embeddings instead of `sentence-transformers`/`torch` — same hybrid-retrieval capability, far lighter — see `DESIGN.md` D-00x for the rationale.

## Repository layout

```
config/           thresholds, source paths, review-queue rules — no hardcoded constants in src/
db/migrations/    numbered schema migrations (drug master, review queue, regulatory events, ...)
data/             provided data pack, unmodified (source of truth for ingestion)
corpus/           provided STW one-pagers (PDF) for Module B
src/module_a/     drug master, normalization, regulatory event engine, safety rail, review queue
src/module_b/     chunking, hybrid retrieval, grounded answering, mini-eval harness
src/module_c/     single end-to-end trace script/endpoint
prompts/          the actual prompt library used, organized and replayable
tests/            unit + integration tests
eval_results/     mini-eval output, seeded rail outputs (checked in)
docs/             Part 2 plan
```

## Status
Scaffold only — see `gaps_register.md` for what's implemented vs. pending.
