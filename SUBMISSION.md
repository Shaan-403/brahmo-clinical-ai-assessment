# SUBMISSION.md

- [x] **How to run:** see `README.md` (target < 1 hour), including migrations and data loads -- verified end-to-end multiple times; the two prior README defects (dead `.env.example` step, stale status line) are fixed.
- [x] **DESIGN.md** (system restatement + 3 riskiest assumptions + decision log) -- present, 20 decision entries (D-001-D-019/D-020+), each with why + rejected alternative(s).
- [x] **SCALE.md** (where this strains at 100x and 100 concurrent users) -- complete, one page.
- [x] **Gaps register** -- `gaps_register.md` -- 13 entries, including the G2 accuracy-vs-coverage distinction and the empty-`prompts/` disclosure added this pass.
- [ ] **Prompt library** -- `prompts/` + conventions file -- `CLAUDE.md`. `CLAUDE.md` is complete; `prompts/` itself is empty -- no structured prompt log was kept during development, disclosed as gap #13 in `gaps_register.md` rather than backfilled with reconstructed prompts.
- [x] **Mini-eval results** -- `eval_results/mini_eval_output.json` -- checked in; 11/11 correct on this run.
- [x] **Seeded-prescription rail outputs** -- `eval_results/seeded_rail_outputs.csv` (all 10, states + evidence) -- checked in, alongside the candidate's own predicted states in `data/seed_prescriptions_template.csv`.
- [x] **End-to-end trace** -- sample JSON checked into `eval_results/sample_trace.json` -- a known-bad prescription (Warfarin + Azithromycin, `severe_interaction` HIT) against a supported clinical question, covering normalization, all four A.6 checks, and a grounded, cited Module B answer.
- [x] **Part 2 plan** -- `docs/PART2_PLAN.md` -- complete, all 9 required sections (completion architecture, week-by-week plan with binary gates, sources/data strategy, gap analysis, doctor's reality, quality system, dependencies, fences, top-10 risks).
- [x] Anything unfinished + prioritization reasoning (see `gaps_register.md`) -- with Part 2 now complete, the sole outstanding Part 1 item is the empty `prompts/` library (see gap #13): no structured prompt log was kept during development, disclosed honestly rather than backfilled with reconstructed prompts. Repo access (below) is the only other open item, a manual step rather than a build gap.
- [ ] Repo access granted to the BRAHMO reviewing team account -- manual step, not yet done.
