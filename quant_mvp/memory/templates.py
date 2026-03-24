from __future__ import annotations


ROOT_AGENTS_TEMPLATE = """# Research OS Instructions

## Goal
- This repository is Phase 1 of a China A-share research operating system.
- Scope is A-share daily/weekly research only.
- It is not a live trading system and does not promise profitability.

## Non-Negotiables
- Never fabricate backtest, validation, or agent results.
- Never delete failed experiments to make the ledger look cleaner.
- Never bypass leakage, tradability, or promotion checks for convenience.
- Never install or invoke new tools silently; log the reason first.

## Required Verification
- Run contract tests for strategy specs, weekday rebalance, memory writeback, and leakage guards.
- Run `python -m quant_mvp research_audit --project <project>`.
- Run `python -m quant_mvp data_validate --project <project>` when data changes.
- Run `python -m quant_mvp agent_cycle --project <project> --dry-run` before trusting the control plane.

## Memory Writeback Contract
- Major repo-level decisions update `docs/DECISION_LOG.md`.
- Every experiment appends one line to `EXPERIMENT_LEDGER.jsonl`.
- Every failed experiment updates `POSTMORTEMS.md`.
- Every hypothesis refresh updates `HYPOTHESIS_QUEUE.md`.
- Every material state change updates `PROJECT_STATE.md`.

## Uncertainty Handling
- Prefer the most conservative, most auditable assumption.
- Write assumptions and unknowns into project memory files instead of leaving them only in context.
- If a tool or dependency is missing, stop at the interface boundary, record it, and keep the system reproducible.
"""


QUANT_AGENTS_TEMPLATE = """# quant_mvp Scope

- Core modules must stay deterministic, testable, and auditable.
- Strategy logic belongs in library modules, not scripts.
- Default values must come from schema modules, not ad-hoc literals.
- New code must keep leakage checks and memory writeback reachable from the CLI.
"""


SCRIPTS_AGENTS_TEMPLATE = """# scripts Scope

- Scripts orchestrate library code only.
- Do not embed strategy defaults or duplicate selection logic here.
- Scripts should write explicit artifacts and manifest entries for reproducibility.
"""


TESTS_AGENTS_TEMPLATE = """# tests Scope

- Prefer contract tests over broad smoke tests.
- Cover strategy spec consistency, leakage guards, reproducibility, and append-only memory behaviour.
- Synthetic fixtures must make the true main entrypoints executable in CI.
"""


DOCS_AGENTS_TEMPLATE = """# docs Scope

- Documentation must match the current code, config schema, and audit outputs.
- When behaviour changes, update strategy specs, decision logs, failure modes, and roadmap docs together.
- Do not retain historical performance claims that cannot be reproduced from the current repo state.
"""


PROJECT_STATE_TEMPLATE = """# Project State

- Project: {project}
- Phase: Phase 1 Research OS bootstrap
- Current mode: audited research only
- Highest priority: keep strategy spec, validation, and memory in sync
- Known assumptions:
  - A-share daily/weekly only
  - AKShare is the current raw provider
  - Tradability uses positive volume and limit-lock proxies until richer data arrives
- Open risks:
  - Provider quality still depends on upstream AKShare stability
  - Walk-forward and robustness are lightweight until richer data is present
"""


HYPOTHESIS_QUEUE_TEMPLATE = """# Hypothesis Queue

1. Revalidate the audited limit-up screening spec against newer cleaned data snapshots.
2. Compare the strategy to simple baselines before promoting any candidate.
3. Extend tradability constraints with richer exchange flags when a higher-quality provider is added.
"""


POSTMORTEMS_TEMPLATE = """# Postmortems

No recorded failures yet in this bootstrap state. Append new failures with date, experiment id, root cause, and corrective action.
"""


RESEARCH_MEMORY_TEMPLATE = """# Research Memory

- Keep only durable facts, rejected paths, and next-step-worthy observations here.
- Do not overwrite failed experiments; summarize and link them.
- Use this file to preserve high-value context across agent cycles.
"""
