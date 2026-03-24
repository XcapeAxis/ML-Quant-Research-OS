# Research OS Phase 1

This repository is being refactored into a reproducible research operating system for China A-share daily/weekly strategy work.

Phase 1 is deliberately narrow:
- market: A-share
- frequency: daily / weekly
- goal: reliable research, reproducible experiments, durable memory, and guarded agent assistance
- non-goal: live trading, minute-level alpha production, profitability promises

## Current Status

Implemented in this refactor:
- a schema-driven limit-up screening strategy spec
- one audited limit-up research core shared by the step pipeline and the standalone strategy script
- provider abstraction over AKShare
- raw -> cleaned -> validated data flow with project-scoped quality reports
- leakage, walk-forward, cost-sensitivity, and promotion-gate modules
- AGENTS files plus tracked project memory under `memory/projects/<project>/` and runtime artifacts under `data/` / `artifacts/`
- a dry-run agent cycle that writes plan / execution / evaluation / reflection to disk
- a subagent governance layer with `OFF/AUTO/FORCE` gate, lifecycle tracking, and tracked/runtime separation
- contract tests for strategy consistency, Tuesday rebalance, leakage guards, and memory writeback

Not implemented yet:
- live trading or broker connectivity
- minute-level production research
- richer exchange-native tradability flags
- automatic profitable strategy discovery

## Important Reality Check

Historical performance claims that existed in earlier repo states are not trusted unless they can be reproduced from the current local data snapshot.

At the time of this refactor, the default project `2026Q1_limit_up` can freeze a universe and generate audit / memory artifacts, but `data_validate` reports that the local market database does not currently contain usable bar data for that project universe. Because of that:
- promotion is blocked
- the dry-run agent records a data-input failure instead of pretending success
- any README-level return claims have been removed

## Canonical Strategy

The Phase 1 canonical strategy is `limit_up_screening`.

Single source of truth:
- strategy spec: [limit_up_screening.md](docs/strategy_specs/limit_up_screening.md)
- schema defaults: [strategy_schema.py](quant_mvp/strategy_schema.py)
- project config schema: [config_schema.py](quant_mvp/config_schema.py)

The standalone entrypoint [run_limit_up_screening.py](scripts/run_limit_up_screening.py) and the modular steps both call the same audited library code in [research_core.py](quant_mvp/research_core.py).

## Core Commands

Install dependencies:

```bash
pip install -r requirements.txt
```

Freeze the project universe:

```bash
python scripts/steps/10_symbols.py --project 2026Q1_limit_up --config configs/projects/2026Q1_limit_up.json
```

Validate and clean data:

```bash
python -m quant_mvp data_validate --project 2026Q1_limit_up --config configs/projects/2026Q1_limit_up.json --full-refresh
```

Run the audited repo audit:

```bash
python -m quant_mvp research_audit --project 2026Q1_limit_up --config configs/projects/2026Q1_limit_up.json
```

Run one dry-run research cycle:

```bash
python -m quant_mvp agent_cycle --project 2026Q1_limit_up --config configs/projects/2026Q1_limit_up.json --dry-run
```

Bootstrap tracked memory and handoff files:

```bash
python -m quant_mvp memory_bootstrap --project 2026Q1_limit_up
python -m quant_mvp memory_sync --project 2026Q1_limit_up
python -m quant_mvp generate_handoff --project 2026Q1_limit_up
```

Evaluate whether subagents are worth enabling for a task:

```bash
python -m quant_mvp subagent_plan --project 2026Q1_limit_up --task-summary "Assess future data and validation split after bars are restored" --breadth 2 --independence 0.7 --file-overlap 0.2 --validation-load 0.8 --coordination-cost 0.3 --risk-isolation 0.5
```

Attempt promotion:

```bash
python -m quant_mvp promote_candidate --project 2026Q1_limit_up --config configs/projects/2026Q1_limit_up.json
```

Run the end-to-end strategy pipeline when data is available:

```bash
python scripts/run_limit_up_screening.py --project 2026Q1_limit_up --config configs/projects/2026Q1_limit_up.json --no-show --save auto
```

## Memory and Audit Files

System-level docs:
- [SYSTEM_BLUEPRINT.md](docs/SYSTEM_BLUEPRINT.md)
- [SYSTEM_AUDIT.md](docs/SYSTEM_AUDIT.md)
- [FAILURE_MODES.md](docs/FAILURE_MODES.md)
- [DECISION_LOG.md](docs/DECISION_LOG.md)
- [RESEARCH_PROMOTION_RULES.md](docs/RESEARCH_PROMOTION_RULES.md)

Tracked project memory for the default project:
- [PROJECT_STATE.md](memory/projects/2026Q1_limit_up/PROJECT_STATE.md)
- [HYPOTHESIS_QUEUE.md](memory/projects/2026Q1_limit_up/HYPOTHESIS_QUEUE.md)
- [POSTMORTEMS.md](memory/projects/2026Q1_limit_up/POSTMORTEMS.md)
- [EXPERIMENT_LEDGER.jsonl](memory/projects/2026Q1_limit_up/EXPERIMENT_LEDGER.jsonl)
- [RESEARCH_MEMORY.md](memory/projects/2026Q1_limit_up/RESEARCH_MEMORY.md)
- [HANDOFF_NEXT_CHAT.md](memory/projects/2026Q1_limit_up/HANDOFF_NEXT_CHAT.md)
- [MIGRATION_PROMPT_NEXT_CHAT.md](memory/projects/2026Q1_limit_up/MIGRATION_PROMPT_NEXT_CHAT.md)
- [VERIFY_LAST.md](memory/projects/2026Q1_limit_up/VERIFY_LAST.md)
- [SESSION_STATE.json](memory/projects/2026Q1_limit_up/SESSION_STATE.json)
- [SUBAGENT_REGISTRY.md](memory/projects/2026Q1_limit_up/SUBAGENT_REGISTRY.md)
- [SUBAGENT_LEDGER.jsonl](memory/projects/2026Q1_limit_up/SUBAGENT_LEDGER.jsonl)

Runtime/high-noise outputs:
- `data/projects/<project>/meta/`
- `artifacts/projects/<project>/`

## Verification

The contract and smoke suite runs with:

```bash
python -m pytest tests -q
```

Current expected result:
- the test suite passes
- dry-run agent flow passes
- promotion may still be blocked on the default project until real bar data is present
