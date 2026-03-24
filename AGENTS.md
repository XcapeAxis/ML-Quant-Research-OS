# Research OS Instructions

## Goal
- This repository is Phase 1 of a China A-share research operating system.
- Scope is A-share daily/weekly research only.
- It is not a live trading system and does not promise profitability.

## Response Contract
- Follow `docs/RESPONSE_CONTRACT.md`.
- Default to `CHECKPOINT` replies unless the user explicitly asks for targeted evidence or full forensics.
- When subagents are relevant, keep the reply to one short gate/status note instead of narrating every subagent.

## Memory Layers
- Git-tracked long-term memory lives under `memory/projects/<project>/`.
- Runtime/high-noise artifacts live under `data/projects/<project>/meta/` and `artifacts/projects/<project>/`.
- Subagent runtime payloads live under `artifacts/projects/<project>/subagents/<subagent_id>/`.
- Durable memory must not exist only inside ignored runtime directories.

## Non-Negotiables
- Never fabricate backtest, validation, or agent results.
- Never delete failed experiments to make the ledger look cleaner.
- Never bypass leakage, tradability, or promotion checks for convenience.
- Never install or invoke new tools silently; log the reason first.

## Required Verification
- Run contract tests for strategy specs, weekday rebalance, memory writeback, and leakage guards.
- Run subagent policy and lifecycle tests when touching the subagent governance layer.
- Run `python -m quant_mvp research_audit --project <project>`.
- Run `python -m quant_mvp data_validate --project <project>` when data changes.
- Run `python -m quant_mvp agent_cycle --project <project> --dry-run` before trusting the control plane.

## Memory Writeback Contract
- Major repo-level decisions update `docs/DECISION_LOG.md`.
- Every compact tracked experiment appends one line to `memory/projects/<project>/EXPERIMENT_LEDGER.jsonl`.
- Every failed experiment updates `memory/projects/<project>/POSTMORTEMS.md`.
- Every hypothesis refresh updates `memory/projects/<project>/HYPOTHESIS_QUEUE.md`.
- Every material state change updates `memory/projects/<project>/PROJECT_STATE.md`.
- Refresh `HANDOFF_NEXT_CHAT.md`, `MIGRATION_PROMPT_NEXT_CHAT.md`, `VERIFY_LAST.md`, and `SESSION_STATE.json` whenever the tracked state changes materially.

## Uncertainty Handling
- Prefer the most conservative, most auditable assumption.
- Write assumptions and unknowns into tracked project memory instead of leaving them only in context.
- If a tool or dependency is missing, stop at the interface boundary, record it, and keep the system reproducible.
