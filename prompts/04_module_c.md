# Module C prompts — end-to-end trace

See `00_README.md` for what this file is and is not.

---

### Initial Module C implementation

> Do not commit anything. I will handle Git commits. Implement Module C now: one runnable endpoint/script that accepts: draft prescription one clinical question. Return a single JSON trace containing: prescription normalization + unresolved items all four Safety Rail check results with their required 8-state contract grounded Module B answer/citations/abstention dataset versions, rule versions, prompt/model versions used. Keep it minimal and assessment-focused. Reuse existing Module A/B code; don't duplicate logic. Add an end-to-end test covering: known-bad prescription + supported question unresolved input + unsupported question. Run the full test suite and report results. Do not make any unrelated changes. Do not commit.

### Read-only audit against the A.6 contract

> Do not touch any code and do not make any commits. Rapidly assess Module C based on the precise A.6 contract: - Does the resulting JSON reveal all of the 4 checks needed, inclusive of the cumulative daily exposure? - Is the cumulative exposure properly represented as check 4/evidence despite D-011 rendering it non-HIT-producing? - Does the trace have all of the required 8-state fields, evidence, severity, rule version, and data versions? - Is the CLI capable of taking draft prescription + clinical question as specified? If there is any aspect that fails to meet the requirements for assessment, let me know precisely what is missing.

_(This same prompt also drove the addition of Safety Rail check (d) — see `02_safety_rail.md`.)_

### Producing the checked-in sample end-to-end trace

> There are still two minor submission gaps for Part 1 remaining.
>
> Do not change any implementation code, and do not commit anything.
>
> 1. Produce one instance of Module C end-to-end JSON trace and store it in eval_results/ folder.
> The trace should cover normalization, all four Safety Rails checks, and a grounded Module B output by using a wrong prescription + valid clinical question.
>
> 2. Update SUBMISSION.md file to accurately reflect completed Part 1 submissions and update the checklist items accordingly.
>
> Do not change any assessment results or make any new design choices.
>
> Test the relevant tests after the documentation/artifact changes.
