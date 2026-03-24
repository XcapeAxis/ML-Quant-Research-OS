# System Audit

- Date: 2026-03-25
- Project: 2026Q1_limit_up
- Scope: Phase 1 A-share daily/weekly research operating system audit

## Findings

| Area | Status | Detail |
| --- | --- | --- |
| standalone_vs_pipeline | pass | Standalone strategy entrypoint uses the same audited research core as the modular steps. |
| weekday_contract | pass | Tuesday rebalance helper returns only weekday=1 dates. |
| strategy_defaults | pass | Limit-up window defaults are centralized in the schema and set to 250 trading days. |
| manifest_paths | pass | Manifest path block should point to the current repository root rather than a stale machine-specific location. |
| reproducible_project_artifacts | warn | The default project needs both a frozen universe and usable local bars before any historical claim is treated as reproducible. |

## Key Observations

- The repo now routes both the standalone script and the step pipeline through the same audited limit-up core.
- The historical repo state had Wednesday/Tuesday drift and mismatched 250 vs 750 day defaults; those are now locked by schema and tests.
- Tracked long-term memory now belongs under `memory/projects/<project>/`, while runtime data and artifacts stay under `data/` and `artifacts/`.
- The default project still needs fresh universe/data artifacts to reproduce any real historical showcase, so documentation must remain conservative.
