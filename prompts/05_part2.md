# Part 2 prompts — production plan (`docs/PART2_PLAN.md`)

See `00_README.md` for what this file is and is not.

---

### Requirements review before drafting

> Let's move to Part 2. I want to make the production plan specific to what we actually built, not a generic AI healthcare architecture. Before writing docs/PART2_PLAN.md, review the Part 2 requirements and give me thesame

### Section 1 — Completion architecture

> Now let's turn to Section 1 — Completion Architecture.
>
> Using the real implementation of Part 1, come up with production architecture and distinguish between:
> - What do we have now?
> - What should be changed in order to go into production?
> - Why?
>
> Be practical and specific for Brahmo. You are not required to finalize the PART2_PLAN.md file yet, nor to change any files or commit anything.

> The overall architecture makes sense to me.
>
> Keep the 8 production modifications, and modify language in two places:
> - Patient context is required for patient-aware safety but must explicitly not be used for any patient-specific dose calculations.
> - Service layer must have a scalable concurrency boundary, and don't assume queue is required for each request unless latency/SLO demands it.
>
> Explicitly state that the fastembed semantic path was intended but not used in this system; TF-IDF was the testable fallback.
>
> Now implement just Section 1 into PART2_PLAN.md using this architecture.
>
> Do not commit.

### Section 2 — Week-by-week plan

> Now let's turn to Section 2 – the weekly plan for production.
>
> Develop a practical 3–6 week plan based on the architecture we have discussed above:
> - with specific weekly deliverables
> - with binary pass/fail gates
> - with dependencies
> - with team ownership
> - with delineation between AI and human tasks
>
> It should be practical and realistic taking into account the issues of Part 1 without presuming a big team.
>
> Do not write this into the file at this moment and do not commit any changes.

> I agree with the 6-week plan.
>
> Make these adjustments before writing it:
> - Week 1: gate on all functional tests passing against Postgres, with any DB-specific test adaptations documented, rather than requiring every existing test to remain literally unchanged.
> - Week 5: clinical SMEs own the specification and approval of contraindication rules; don't imply engineering can define those clinical rules.
> - Week 6: don't invent an arbitrary pilot-doctor number. Tie the target to the assessment's 100 doctors / 1,000 real questions each requirement where appropriate.
>
> Now write only Section 2 into PART2_PLAN.md. Keep the binary gates concrete and measurable.
>
> Do not commit anything.

### Sections 3 and 4 — Sources/data strategy and gap analysis

> Let's cover Sections 3 and 4 together.
>
> For Sources/Data Strategy, propose the specific Indian sources we should consider, separating:
> - free/public
> - licensed
> - build/derived
>
> Include rough cost/rights assumptions only where we can defend them.
>
> For Gap Analysis, use our actual Part 1 gaps and select the 3–5 most consequential ones, with what we'd do about each.
>
> Don't write to the file yet, don't invent facts, and don't commit. Keep it concise.

> Go ahead and write Sections 3 and 4 into `docs/PART2_PLAN.md` using this draft. Keep the claims and numbers grounded in our actual Part 1 results. Make the licensed-source/vendor language cautious and don't invent prices or rights. In Gap #2, frame broader reference-data licensing as a production dependency rather than saying a specific vendor is mandatory.
> After writing, quickly verify the section numbering and formatting.
> Do not commit anything. I will handle Git commits.

### Sections 5–9 — remainder of the plan

> Finish Sections 5–9 in `docs/PART2_PLAN.md`. Keep it concise and ownership-driven: decision → why → rejected alternative → implication where relevant. Cover doctor workflow, quality/evaluation, fair BRAHMO vs ChatGPT vs Claude comparison, 100k QA, dependencies/fences, and exactly 10 production risks with mitigations/owners. Use only our actual Part 1 facts; don't invent measurements, costs, or clinical claims. Verify Sections 1–9 cover every Part 2 requirement.
> Do not commit anything. I will handle Git commits.
