# Working conventions for AI-assisted development on this repo

## Ground rules
- No hardcoded thresholds, list locations, or config values in `src/` — everything loads from `config/`.
- Safety rail code (`src/module_a/rail/`) never calls an LLM. If a change to that package imports an LLM client, that's a bug, not a feature.
- Every data row and every check result must be traceable to source + version (see `config/thresholds.yaml` and migration comments for the versioning columns).
- Ambiguous resolutions are queued (`src/module_a/review_queue/`), never silently auto-resolved.
- Regulatory status is always derived from `src/module_a/regulatory/` event sourcing — never a boolean flag.
- Module B answers cite at the claim level; abstain rather than guess; never compute a patient-specific dose.

## Prompt library
Prompts actually used for AI-assisted development live in `prompts/`, one file per task, named `NN_task-name.md`, with the exact prompt text and which model/tool it was run against.

## Style
- Python 3.10+, type hints throughout, `ruff` for lint/format.
- Tests alongside each module in `tests/`, named to mirror `src/` layout.
