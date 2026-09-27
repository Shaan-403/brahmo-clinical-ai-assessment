# Final-audit and documentation prompts

See `00_README.md` for what this file is and is not. This file groups
repo-wide audit requests (spanning multiple modules) and the documentation
fixes that followed from them, rather than any single module's build work.

---

### First full-repo audit against G1–G7

> Do not modify code and do not commit anything. Audit the repository against every mandatory assessment requirement and gates G1-G7. For each gate/requirement give: - PASS / GAP - exact evidence (file/test/command) - if GAP, the smallest required fix. Also check: - Module A/B/C mandatory requirements - auto-fail conditions - provenance - 100+ FDC decomposition - 10 seeded prescriptions - 11-question Module B eval - Module C single JSON trace - DESIGN.md decisions - SCALE.md - README fresh-machine setup - prompt library / CLAUDE.md - no claimed accuracy beyond measured tests. Do not fix anything yet. Do not commit.

### Reviewing and applying three documentation fixes

> The generated artifacts reviewed, and they are fine. We should now fix the documentation. There are three issues that need to be addressed:
> - The README still states that we have a "Scaffold only" state and that the .env.example generation process was broken.
> - G2 should indicate the distinction between our estimated FDC coverage and the required ≥95% accuracy gate because we were not provided with any held-out ground truth.
> - prompts/ is empty, and I see no need to generate some prompts just for the sake of creating a file.
>
> Review these three points and let me know what changes you would make while being honest and minimalistic.
>
> Don't touch anything and do not commit.

> Agreed. Apply exactly those three documentation fixes.
>
> Keep the wording honest and don't reconstruct or invent any prompts.
>
> Do not modify code and do not commit anything.
>
> Once finished, give me the diff for this documentation modification alone.

### Part 1 submission checklist audit

> Do not modify anything and do not commit anything.
>
> Give me the final Part 1 submission checklist only.
>
> Verify:
> - G1–G7
> - all Module A/B/C mandatory requirements
> - auto-fail conditions
> - required evaluation artifacts
> - README/setup
> - DESIGN.md
> - SCALE.md
> - SUBMISSION.md
> - gaps_register.md
>
> For each, give PASS or GAP and one short reason.
>
> Then stop.

### Final submission audit

> Final submission audit only. Check the repo against the assessment brief and identify anything that is genuinely missing or broken. Run the full test suite and verify required artifacts, README, DESIGN.md, SCALE.md, SUBMISSION.md, gaps_register.md, and Part 2. Don't redesign or add unnecessary features. Fix only clear submission blockers. Report blockers and final test count.
> Do not commit anything. I will handle Git commits.
