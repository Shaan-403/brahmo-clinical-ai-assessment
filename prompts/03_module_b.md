# Module B prompts — grounded clinical Q&A (mini-RAG)

See `00_README.md` for what this file is and is not.

---

### Initial Module B implementation

> Implement Module B according to the design you have just designed. Don't commit anything. I'll do the Git commits myself. Try to keep the scope narrow and assessment-oriented. - structural decision-unit chunks with complete metadata - SQL FT5 + fastembed retrieval hybrid - version and source type filtering - grounded responses with claim citations - abstentions where evidence is lacking - conflict resolution without synthesis - explicit distinction of local vs national - no patient specific dosing calculations - numeric clinical claims must have citations - working 11 question evaluation harness. Use the supplied STW PDFs and local protocol only. No external clinical knowledge should be used. Don't change anything in Module A/Safety Rail unless necessary for integrating Module B. Add tests for the critical edge cases and then run the full test suite and the 11 question evaluation. Provide the results and any gaps found. Do not make any additional designs or commits.

### Producing the checked-in mini-eval artifact

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

_(This same pair of prompts also drove Module A's seeded-rail-output artifact in the same request — see `01_module_a.md`.)_
