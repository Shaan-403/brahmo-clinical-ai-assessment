# Module A prompts — drug master, ingestion, normalization

See `00_README.md` for what this file is and is not.

**Honesty note:** the prompts that originally drove Module A's build (drug
master schema, migrations, CDCI/NLEM/Jan Aushadhi/pharmacy-stock ingestion,
normalization, and the review-queue design) were given in an earlier part of
this development session that was later summarized by an automatic
context-compaction event. That event replaces raw message history with a
condensed narrative and does not preserve the original prompt text. Nothing
verbatim from that phase survived into this environment. No prompt is
reconstructed here to fill the gap — see `gaps_register.md` for the same
disclosure applied to this deliverable.

The one Module-A-scoped prompt below is verbatim and recoverable because it
happened after compaction, in the phase that closed out Part 1's
demonstration artifacts (seeded-prescription rail outputs).

---

### Producing the checked-in seeded-rail-output artifact

> I went through the final audit. The implementation looks good, but I noticed the seeded rail outputs and Module B eval are only represented through tests right now.
>
> Can you check what the assessment expects us to actually submit as demonstration artifacts? I want the 10 seeded prescriptions and 11-question eval to be reproducible and visible to a reviewer, not just hidden inside tests.
>
> Don't change anything yet, and don't commit. Tell me what you recommend.

> Makes sense. I concur that the reviewer should be able to examine the artifacts without having to run the test suite.
>
> Proceed with the two reproducible scripts and populate the 10 seeded prescription output with the actual rail results. Leave the existing logic intact.
>
> Also make sure that the generated artifacts clearly differentiate between our expected/candidate output and the system-generated output.
>
> Do not commit anything. Then run both the scripts and provide me with the generated output as well as the test suite status.

_(This same pair of prompts also drove Module B's mini-eval artifact in the same request — see `03_module_b.md`.)_
