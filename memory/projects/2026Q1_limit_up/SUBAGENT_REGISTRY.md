# Subagent Registry

## Governance
- gate_mode: AUTO
- recommended_gate: OFF
- continue_using_subagents: no
- continue_reason: Task breadth is below the minimum threshold for safe decomposition.
- recent_event: plan

## Current Sets
- active: none
- blocked: none
- retired_or_merged: none
- temporary: none
- long_lived_templates: none

## Latest Plan
- recommended_count: 0
- recommended_roles: none
- no_split_reason: Task breadth is below the minimum threshold for safe decomposition.
- rationale: The work is still narrow enough for one integrating agent.

## Role Templates
- data_steward: Own provider, ingestion, cleaning, and data coverage diagnostics without changing strategy logic.
- strategy_auditor: Check strategy entrypoints, defaults, and documentation for drift.
- validation_guard: Own leakage, robustness, baseline, and promotion-gate verification work.
- memory_curator: Keep tracked memory, handoff, and migration prompts concise and accurate.
- tooling_scout: Investigate missing tools, policy files, and reproducibility boundaries before anything is added.
- integration_merger: Merge compatible workstreams, reduce overlap, and close out temporary subagents.

## Records
- no instantiated subagents
