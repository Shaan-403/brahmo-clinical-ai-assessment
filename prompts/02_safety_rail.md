# Safety Rail prompts — Module A.6 deterministic checks

See `00_README.md` for what this file is and is not.

**Honesty note:** the prompts that originally specified the first three
Safety Rail checks (duplicate active ingredient, prohibited/restricted FDC,
severe interaction) predate an automatic context-compaction event in this
session and are not recoverable verbatim (see `01_module_a.md` for the same
disclosure). The one prompt below, for the fourth check (cumulative daily
exposure), happened after compaction and is fully recoverable.

---

### Adding check (d): cumulative daily exposure, as its own never-HIT check

> Do not touch any code and do not make any commits. Rapidly assess Module C based on the precise A.6 contract: - Does the resulting JSON reveal all of the 4 checks needed, inclusive of the cumulative daily exposure? - Is the cumulative exposure properly represented as check 4/evidence despite D-011 rendering it non-HIT-producing? - Does the trace have all of the required 8-state fields, evidence, severity, rule version, and data versions? - Is the CLI capable of taking draft prescription + clinical question as specified? If there is any aspect that fails to meet the requirements for assessment, let me know precisely what is missing.

> Do not modify code and do not commit anything. Make sure that your Module C trace contains all four A.6 checks that are necessary: 1. duplicate_active_ingredient 2. prohibited_restricted_fdc 3. severe_interaction 4. cumulative_daily_exposure. In Check 4, do not define any dose limit or any other clinical criteria. Just calculate your 8-state return based solely on having partial or complete cumulative exposure coverage, with your results in evidence. Keep D-011 untouched: cumulative exposure should not trigger a clinical HIT. Test both complete and unparseable (SOS) exposures. Do not commit.
