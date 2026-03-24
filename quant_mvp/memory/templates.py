from __future__ import annotations


ROOT_AGENTS_TEMPLATE = """# Research OS Instructions

## Goal
- This repository is Phase 1 of a China A-share research operating system.
- Scope is A-share daily/weekly research only.
- It is not a live trading system and does not promise profitability.

## Response Contract
- Follow `docs/RESPONSE_CONTRACT.md`.
- Default to `CHECKPOINT` replies unless the user explicitly asks for targeted evidence or full forensics.

## Memory Layers
- Git-tracked long-term memory lives under `memory/projects/<project>/`.
- Runtime/high-noise artifacts live under `data/projects/<project>/meta/` and `artifacts/projects/<project>/`.
- Do not write durable memory only into ignored runtime directories.

## Non-Negotiables
- Never fabricate backtest, validation, or agent results.
- Never delete failed experiments to make the ledger look cleaner.
- Never bypass leakage, tradability, or promotion checks for convenience.
- Never install or invoke new tools silently; log the reason first.

## Required Verification
- Run contract tests for strategy specs, weekday rebalance, tracked memory writeback, and leakage guards.
- Run `python -m quant_mvp research_audit --project <project>`.
- Run `python -m quant_mvp data_validate --project <project>` when data changes.
- Run `python -m quant_mvp agent_cycle --project <project> --dry-run` before trusting the control plane.

## Memory Writeback Contract
- Major repo-level decisions update `docs/DECISION_LOG.md`.
- Durable project summaries update `memory/projects/<project>/PROJECT_STATE.md`.
- Every failed or blocked experiment appends `memory/projects/<project>/POSTMORTEMS.md`.
- Every compact experiment record appends `memory/projects/<project>/EXPERIMENT_LEDGER.jsonl`.
- Every hypothesis refresh updates `memory/projects/<project>/HYPOTHESIS_QUEUE.md`.
- Session handoff artifacts live beside tracked project memory.

## Uncertainty Handling
- Prefer the most conservative, most auditable assumption.
- Write assumptions and unknowns into tracked project memory instead of leaving them only in context.
- If a tool or dependency is missing, stop at the interface boundary, record it, and keep the system reproducible.
"""


QUANT_AGENTS_TEMPLATE = """# quant_mvp Scope

- Core modules must stay deterministic, testable, and auditable.
- Strategy logic belongs in library modules, not scripts.
- Default values must come from schema modules, not ad-hoc literals.
- Memory APIs must preserve the tracked-memory / runtime-artifact split.
"""


SCRIPTS_AGENTS_TEMPLATE = """# scripts Scope

- Scripts orchestrate library code only.
- Do not embed strategy defaults or duplicate selection logic here.
- Durable memory writes must go through the memory writeback layer, not ad-hoc file writes.
"""


TESTS_AGENTS_TEMPLATE = """# tests Scope

- Prefer contract tests over broad smoke tests.
- Cover strategy spec consistency, leakage guards, reproducibility, tracked-memory writeback, and append-only behaviour.
- Tests must clean up tracked-memory side effects for temporary projects.
"""


DOCS_AGENTS_TEMPLATE = """# docs Scope

- Documentation must match the current code, config schema, and audit outputs.
- When behaviour changes, update response contract, strategy specs, decision logs, failure modes, and blueprint docs together.
- Do not retain historical performance claims that cannot be reproduced from the current repo state.
"""


PROJECT_STATE_TEMPLATE = """# Project State

- current_total_task: Keep the Phase 1 Research OS reproducible, auditable, and memory-stable.
- current_phase: Phase 1 Research OS
- current_blocker: Default project still lacks usable validated bars for the frozen universe.
- current_real_capability_boundary: Engineering guardrails work; real default-project research remains blocked on data coverage.
- next_priority_action: Restore a usable validated bar snapshot for the frozen default universe.
- last_verified_capability: Contract and dry-run orchestration tests passed in the repository virtual environment.
- last_failed_capability: Promotion on the default project is blocked by missing research inputs.
"""


HYPOTHESIS_QUEUE_TEMPLATE = """# Hypothesis Queue

1. [blocked] Restore validated daily bars for the frozen default universe, then rerun promotion.
2. [pending] Revalidate the audited limit-up screening spec on validated data only.
3. [pending] Compare the audited strategy against baselines and cost stress before any promotion claim.
"""


POSTMORTEMS_TEMPLATE = """# Postmortems

No critical failures recorded yet. Append only high-signal failures with root cause, corrective action, and current resolution status.
"""


RESEARCH_MEMORY_TEMPLATE = """# Research Memory

## Durable Facts
- The limit-up screening path now shares one audited research core between the standalone script and the modular steps.
- Tracked long-term memory lives under `memory/projects/<project>/`; runtime artifacts stay under `data/` and `artifacts/`.

## Negative Memory
- Default-project promotion is not trustworthy until validated bars exist for the frozen universe.
- Ignored runtime directories are not sufficient as the sole store for durable project memory.

## Next-Step Memory
- Restore validated default-project bars before trusting any research conclusion.
- Keep compact tracked ledgers and handoff files in sync with runtime experiment payloads.
"""


VERIFY_LAST_TEMPLATE = """# Verify Last

- head: unknown
- branch: unknown
- passed_commands:
  - none recorded yet
- failed_commands:
  - none recorded yet
- default_project_data_status: unknown
- conclusion_boundary_engineering: unknown
- conclusion_boundary_research: unknown
"""
