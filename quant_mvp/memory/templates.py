from __future__ import annotations


ROOT_AGENTS_TEMPLATE = """# Research Kernel Instructions

## Goal
- This repository is a market-agnostic research kernel.
- The current mainline is `crypto_okx_research_v1`.
- The current market focus is crypto.
- The current exchange focus is OKX.
- The current phase is `Backtest First`.
- Live scope stays `none` until governance and risk review both approve a wider phase.

## Response Contract
- Follow `docs/RESPONSE_CONTRACT.md`.
- Default to clear checkpoint-style replies.
- Do not pretend an experiment or a promotion is stronger than its evidence.

## Memory Layers
- Git-tracked long-term memory lives under `memory/projects/<project>/`.
- Runtime and high-noise outputs live under `data/projects/<project>/meta/` and `artifacts/projects/<project>/`.
- Durable decisions must not live only in ignored runtime directories.

## Non-Negotiables
- Never fabricate backtest, validation, or agent results.
- Never bypass risk review because a result looks promising.
- Never widen to demo or live during phase 0.
- Never silently treat a legacy A-share result as crypto evidence.

## Required Verification
- Run `python -m quant_mvp memory_bootstrap --project <project>`.
- Run `python -m quant_mvp doctor --project <project>`.
- Run `python -m quant_mvp memory_sync --project <project>`.
- Run `python -m quant_mvp research_audit --project <project>`.
- Use `python -m quant_mvp agent_cycle --project <project> --dry-run` only when the project contract is already stable enough to make that cycle useful.

## Memory Writeback Contract
- Major repo-level decisions update `docs/DECISION_LOG.md`.
- Durable project summaries update `memory/projects/<project>/PROJECT_STATE.md`.
- Failed or blocked experiments append `memory/projects/<project>/POSTMORTEMS.md`.
- Compact experiment records append `memory/projects/<project>/EXPERIMENT_LEDGER.jsonl`.
- Session handoff artifacts live beside tracked project memory.

## Uncertainty Handling
- Prefer the most conservative, most auditable assumption.
- Write assumptions and unknowns into tracked project memory instead of leaving them only in chat.
- If a required data contract is missing, stop at that boundary and record it.
"""


QUANT_AGENTS_TEMPLATE = """# quant_mvp Scope

- Core modules must stay deterministic, testable, and auditable.
- Strategy logic belongs in library modules, not ad-hoc scripts.
- Defaults must come from config or schema modules, not scattered literals.
- Memory APIs must preserve the tracked-memory / runtime-artifact split.
"""


SCRIPTS_AGENTS_TEMPLATE = """# scripts Scope

- Scripts orchestrate library code only.
- Do not hide strategy defaults in scripts.
- Durable memory writes must go through the memory writeback layer.
"""


TESTS_AGENTS_TEMPLATE = """# tests Scope

- Prefer contract tests over large noisy smoke tests.
- Cover identity, tracked-memory writeback, readiness boundaries, and reproducibility.
- Temporary test projects must clean up tracked side effects.
"""


DOCS_AGENTS_TEMPLATE = """# docs Scope

- Docs must match current code, config, audit outputs, and promotion boundaries.
- When behavior changes, update the decision log, audit docs, and current mainline docs together.
- Do not keep historical claims that cannot be reproduced from current repo state.
"""


PROJECT_STATE_TEMPLATE = """# Project State

- Current canonical project: `crypto_okx_research_v1`
- Current phase: `Phase 0 Backtest First`
- Current task: establish the crypto + OKX research kernel without widening into execution.
- Current blocker: no verified blocker has been recorded yet; write one only after doctor, audit, or a bounded experiment produces fresh evidence.
- Current capability boundary: tracked memory bootstrap alone does not prove research readiness.
- Next priority action: run doctor, memory sync, and research audit before changing the blocker story.
- Latest verified capability: none recorded yet for the crypto mainline.
- Latest failed capability: none recorded yet for the crypto mainline.
"""


HYPOTHESIS_QUEUE_TEMPLATE = """# Hypothesis Queue

1. [blocked] Prove the phase-0 data contract on OKX public market data before trusting any strategy claim.
2. [pending] Check whether one small explicit OKX universe is enough to support a useful Backtest First loop.
3. [pending] Refuse promotion unless costs, fees, funding, and walk-forward behavior are all visible in the evaluation bundle.
"""


EXECUTION_QUEUE_TEMPLATE = """# Execution Queue

| task_id | title | impact | risk | prerequisite | current_status | owner | success_condition | stop_condition |
|---|---|---|---|---|---|---|---|---|
| materialize_phase0_universe | Materialize the OKX phase-0 universe file | high | low | universe contract exists | queued | main | `universe_codes.txt` exists and matches the contract | universe contract is missing or invalid |
| refresh_project_doctor | Refresh project doctor and readiness boundary | high | low | config exists | queued | main | doctor output clarifies the real blocker | doctor still only reports missing configuration noise |
| refresh_research_audit | Refresh repo audit and current truth | medium | low | tracked memory exists | queued | main | audit clarifies the next bounded research step | audit adds no new boundary information |
| bounded_agent_cycle | Run one dry-run research cycle | medium | medium | doctor and audit no longer block on missing contracts | blocked | main | dry-run adds new bounded evidence | dry-run only repeats the same blocker |
"""


POSTMORTEMS_TEMPLATE = """# Postmortems

No high-value failure has been recorded yet for the crypto mainline.
Append only when the failure changes direction, risk, or the next bounded step.
"""


RESEARCH_MEMORY_TEMPLATE = """# Research Memory

## Durable Facts
- This repo is now the research kernel for `crypto_okx_research_v1`.
- The current market focus is crypto and the current exchange focus is OKX.
- A-share work remains in the repo only as a legacy reference.

## Negative Memory
- Do not claim crypto readiness from A-share artifacts.
- Do not widen to demo or live during phase 0.
- Do not trust a strategy story until doctor, audit, and evaluation all line up.

## Next Step Memory
- Materialize the OKX phase-0 universe file.
- Refresh doctor and audit before promoting any research claim.
- Keep tracked memory and runtime artifacts aligned after every bounded step.
"""


VERIFY_LAST_TEMPLATE = """# Latest Verify Snapshot

- head: unknown
- branch: unknown
- passed commands:
  - none recorded
- failed commands:
  - none recorded
- current canonical project ID: crypto_okx_research_v1
- historical aliases:
  - as_share_research_v1
  - 2026Q1_limit_up
- default project data status: unknown
- engineering boundary: unknown
- research boundary: unknown
"""
