# SUBMISSION.md

- [x] **How to run:** see `README.md` (target < 1 hour), including migrations and data loads -- verified end-to-end multiple times; the two prior README defects (dead `.env.example` step, stale status line) are fixed.
- [x] **DESIGN.md** (system restatement + 3 riskiest assumptions + decision log) -- present, 20 decision entries (D-001-D-019/D-020+), each with why + rejected alternative(s).
- [x] **SCALE.md** (where this strains at 100x and 100 concurrent users) -- complete, one page.
- [x] **Gaps register** -- `gaps_register.md` -- 13 entries, including the G2 accuracy-vs-coverage distinction and the disclosed gap on unrecoverable early-development prompts (see `prompts/00_README.md`).
- [x] **Prompt library** -- `prompts/` + conventions file -- `CLAUDE.md`. Both present: `CLAUDE.md` is complete, and `prompts/` contains the actual prompts used, grouped by development phase (Module A, Safety Rail, Module B, Module C, Part 2, final audit). The one honest gap -- prompts from the earliest development phase were lost to a context-compaction event and are not recoverable -- is disclosed in `prompts/00_README.md` and in gap #13 of `gaps_register.md`, rather than backfilled with reconstructed text.
- [x] **Mini-eval results** -- `eval_results/mini_eval_output.json` -- checked in; 11/11 correct on this run.
- [x] **Seeded-prescription rail outputs** -- `eval_results/seeded_rail_outputs.csv` (all 10, states + evidence) -- checked in, alongside the candidate's own predicted states in `data/seed_prescriptions_template.csv`.
- [x] **End-to-end trace** -- sample JSON checked into `eval_results/sample_trace.json` -- a known-bad prescription (Warfarin + Azithromycin, `severe_interaction` HIT) against a supported clinical question, covering normalization, all four A.6 checks, and a grounded, cited Module B answer.
- [x] **Part 2 plan** -- `docs/PART2_PLAN.md` -- complete, all 9 required sections (completion architecture, week-by-week plan with binary gates, sources/data strategy, gap analysis, doctor's reality, quality system, dependencies, fences, top-10 risks).
- [x] Anything unfinished + prioritization reasoning (see `gaps_register.md`) -- with Part 2 and the prompt library both now complete, the only genuinely outstanding item is repo access (below), a manual step rather than a build gap. The one disclosed content gap -- unrecoverable early-development prompts (gap #13) -- is documentation of a permanent limitation, not unfinished work.
- [ ] Repo access granted to the BRAHMO reviewing team account -- manual step, not yet done.
