# Subagent Operating Model

## Purpose
- Subagents are controlled work units, not free-form personas.
- The main agent remains the only integrator and final decision maker.
- Default mode is `AUTO`; the system should stay effectively `OFF` when a task is too small or too coupled.

## Gate Modes
- `OFF`: do not split the task.
- `AUTO`: evaluate whether decomposition is worth the coordination cost.
- `FORCE`: override the suppressors when the user explicitly requests heavier decomposition or when risk isolation clearly dominates.

## Decision Factors
- task breadth
- subtask independence
- file overlap
- validation load
- coordination cost
- risk-isolation value

## Lifecycle
- `proposed`
- `active`
- `blocked`
- `merged`
- `retired`
- `canceled`
- `archived`

Every lifecycle event appends one compact line to `memory/projects/<project>/SUBAGENT_LEDGER.jsonl`.

## Memory Split
- Tracked summaries live in `memory/projects/<project>/SUBAGENT_REGISTRY.md` and `memory/projects/<project>/SUBAGENT_LEDGER.jsonl`.
- High-noise runtime outputs live under `artifacts/projects/<project>/subagents/<subagent_id>/`.
- Handoff, migration prompt, verify snapshot, and session state must all carry a short subagent status summary.

## Current Boundary
- The default project is still blocked by missing validated bars.
- Because of that blocker, the honest default recommendation is usually `gate=AUTO` with no active subagents until data restoration creates truly independent work packages.
