# Prompt library — actual prompts used

This is the collection of **actual prompts used to drive development** of this
repository. It is **not a full conversation transcript**: trivial questions,
routine clarifications, and pure debugging back-and-forth (e.g. a stale
`.git/index.lock` cleanup request) are excluded. Every prompt kept below is
reproduced **exactly as written** by the candidate, including any typos or
informal phrasing — nothing here has been rewritten, cleaned up, or
reconstructed after the fact.

**Honesty note on coverage:** development was AI-assisted throughout an
interactive session with Claude (Cowork), across two consecutive sessions.
The second session began from an automatic context-compaction event, which
replaces the full prior message history with a condensed summary and does
not retain the original message text. As a result, the *earliest* prompts —
those that drove the initial Module A (drug master, ingestion, normalization)
build and the first three Safety Rail checks (duplicate ingredient,
prohibited/restricted FDC, severe interaction) — are **not recoverable
verbatim** from anything available in this environment. Rather than
reconstruct or paraphrase them as if they were the original text (which
`gaps_register.md` and this deliverable's own instructions both treat as a
worse outcome than an honest gap), `01_module_a.md` and `02_safety_rail.md`
say so plainly and contain only what could genuinely be recovered.

Every prompt below **is** the candidate's real, verbatim instruction text.
Files are grouped by development phase:

- `01_module_a.md` — Module A: drug master, ingestion, normalization
- `02_safety_rail.md` — Module A.6: the deterministic Safety Rail checks
- `03_module_b.md` — Module B: grounded clinical Q&A / mini-RAG
- `04_module_c.md` — Module C: end-to-end trace
- `05_part2.md` — Part 2: production plan (`docs/PART2_PLAN.md`)
- `06_final_audit.md` — Repo-wide submission audits and documentation fixes
