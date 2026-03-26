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
- a research-readiness gate that classifies empty / pilot / ready data coverage before promotion
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

The default project `as_share_research_v1` should now be interpreted through two explicit gates:
- `data_validate` tells you what validated coverage exists for the frozen universe.
- `research_readiness` decides whether that snapshot is empty, only a pilot subset, or good enough for promotion-grade research.

Because of that:
- promotion is blocked whenever research readiness is not met
- partial coverage is treated as pilot recovery, not as full-universe evidence
- any README-level return claims remain removed unless they can be reproduced from the current local snapshot

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
python scripts/steps/10_symbols.py --project as_share_research_v1 --config configs/projects/as_share_research_v1.json
```

Validate and clean data:

```bash
python -m quant_mvp data_validate --project as_share_research_v1 --config configs/projects/as_share_research_v1.json --full-refresh
```

Evaluate whether the validated snapshot is promotion-ready:

```bash
python -m quant_mvp research_readiness --project as_share_research_v1 --config configs/projects/as_share_research_v1.json
```

Run the audited repo audit:

```bash
python -m quant_mvp research_audit --project as_share_research_v1 --config configs/projects/as_share_research_v1.json
```

Run one dry-run research cycle:

```bash
python -m quant_mvp agent_cycle --project as_share_research_v1 --config configs/projects/as_share_research_v1.json --dry-run
```

Run one bounded higher-order automation loop:

```bash
python -m quant_mvp iterative_run --project as_share_research_v1 --config configs/projects/as_share_research_v1.json --target-iterations 3 --max-iterations 5 --format checkpoint
```

Bootstrap tracked memory and handoff files:

```bash
python -m quant_mvp memory_bootstrap --project as_share_research_v1
python -m quant_mvp memory_sync --project as_share_research_v1
python -m quant_mvp generate_handoff --project as_share_research_v1
```

Evaluate whether subagents are worth enabling for a task:

```bash
python -m quant_mvp subagent_plan --project as_share_research_v1 --task-summary "Assess future data and validation split after bars are restored" --breadth 2 --independence 0.7 --file-overlap 0.2 --validation-load 0.8 --coordination-cost 0.3 --risk-isolation 0.5
```

Attempt promotion:

```bash
python -m quant_mvp promote_candidate --project as_share_research_v1 --config configs/projects/as_share_research_v1.json
```

Run the end-to-end strategy pipeline when data is available:

```bash
python scripts/run_limit_up_screening.py --project as_share_research_v1 --config configs/projects/as_share_research_v1.json --no-show --save auto
```

## Memory and Audit Files

System-level docs:
- [SYSTEM_BLUEPRINT.md](docs/SYSTEM_BLUEPRINT.md)
- [SYSTEM_AUDIT.md](docs/SYSTEM_AUDIT.md)
- [FAILURE_MODES.md](docs/FAILURE_MODES.md)
- [DECISION_LOG.md](docs/DECISION_LOG.md)
- [RESEARCH_PROMOTION_RULES.md](docs/RESEARCH_PROMOTION_RULES.md)

Tracked project memory for the default project:
- [PROJECT_STATE.md](memory/projects/as_share_research_v1/PROJECT_STATE.md)
- [HYPOTHESIS_QUEUE.md](memory/projects/as_share_research_v1/HYPOTHESIS_QUEUE.md)
- [POSTMORTEMS.md](memory/projects/as_share_research_v1/POSTMORTEMS.md)
- [EXPERIMENT_LEDGER.jsonl](memory/projects/as_share_research_v1/EXPERIMENT_LEDGER.jsonl)
- [RESEARCH_MEMORY.md](memory/projects/as_share_research_v1/RESEARCH_MEMORY.md)
- [HANDOFF_NEXT_CHAT.md](memory/projects/as_share_research_v1/HANDOFF_NEXT_CHAT.md)
- [MIGRATION_PROMPT_NEXT_CHAT.md](memory/projects/as_share_research_v1/MIGRATION_PROMPT_NEXT_CHAT.md)
- [VERIFY_LAST.md](memory/projects/as_share_research_v1/VERIFY_LAST.md)
- [SESSION_STATE.json](memory/projects/as_share_research_v1/SESSION_STATE.json)
- [SUBAGENT_REGISTRY.md](memory/projects/as_share_research_v1/SUBAGENT_REGISTRY.md)
- [SUBAGENT_LEDGER.jsonl](memory/projects/as_share_research_v1/SUBAGENT_LEDGER.jsonl)

`SESSION_STATE.json` is the canonical tracked state. The markdown handoff, migration, verify, and summary files are derived views.

Runtime/high-noise outputs:
- `data/projects/<project>/meta/`
- `artifacts/projects/<project>/`
- `artifacts/projects/<project>/automation_runs/`
- repo-local skill recipe: `skills/research_iteration_loop/SKILL.md`

## Verification

The contract and smoke suite runs with:

```bash
python -m pytest tests -q
```

Current expected result:
- the test suite passes
- dry-run agent flow passes
- promotion may still be blocked on the default project until research readiness passes on the current validated snapshot
