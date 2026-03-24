# Research OS Instructions

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
