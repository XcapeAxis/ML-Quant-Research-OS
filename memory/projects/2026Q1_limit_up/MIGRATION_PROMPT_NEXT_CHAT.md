# Migration Prompt Next Chat

## Current Total Task
Keep the default project on real daily inputs, expand beyond the pilot subset, and reassess promotion only after coverage and drawdown context improve.

## Current Phase
Phase 1 Research OS - pilot real-input recovery

## Current Repo / Branch / HEAD
- repo_root: C:\Users\asus\Documents\Projects\BackTest
- branch: main
- head: 6692256dc0363569b9ecfc39654a51878b888114

## Confirmed Facts
- tracked_memory_dir: C:\Users\asus\Documents\Projects\BackTest\memory\projects\2026Q1_limit_up
- runtime_meta_dir: C:\Users\asus\Documents\Projects\BackTest\data\projects\2026Q1_limit_up\meta
- runtime_artifacts_dir: C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\2026Q1_limit_up
- current_blocker: Pilot recovery covers 150/3063 frozen-universe names (coverage_ratio=0.0490), and promotion is blocked because max drawdown is 83.38% > 30.00%.

## Unconfirmed Questions
- No additional unconfirmed questions have been recorded yet.

## Recent Critical Failure
Candidate failed the current promotion gate.

## Current Blocker
Pilot recovery covers 150/3063 frozen-universe names (coverage_ratio=0.0490), and promotion is blocked because max drawdown is 83.38% > 30.00%.

## Subagent Status
- gate_mode: AUTO
- active: none
- blocked: none
- recent_transition: plan
- continue_using_subagents: no

## Next Highest-Priority Action
Expand validated daily bars beyond the 150-code pilot or explicitly test whether the 83.38% drawdown is pilot-sampling bias before trusting any strategy conclusion.

## Avoid Repeating Work
- Do not move durable memory back into ignored runtime directories.
- Do not trust default-project research claims until validated bars exist for the frozen universe.

## Required Verification First
- python scripts/steps/11_update_bars.py --project 2026Q1_limit_up --config configs/projects/2026Q1_limit_up.json --mode backfill --start-date 2016-01-01 --end-date 2025-07-01 --workers 4 --max-codes-scan 150
- python -m quant_mvp data_validate --project 2026Q1_limit_up --config configs/projects/2026Q1_limit_up.json --full-refresh
- python -m quant_mvp subagent_plan --project 2026Q1_limit_up --task-summary "After restoring a pilot subset of real bars, expand data coverage while independently auditing the pilot-bias and drawdown failure before the next promotion attempt." --gate AUTO --breadth 2 --independence 0.72 --file-overlap 0.30 --validation-load 0.80 --coordination-cost 0.45 --risk-isolation 0.55 --focus-tag data --focus-tag validation
- python -m quant_mvp promote_candidate --project 2026Q1_limit_up --config configs/projects/2026Q1_limit_up.json

## Read These Files First If Context Is Thin
- C:\Users\asus\Documents\Projects\BackTest\memory\projects\2026Q1_limit_up\PROJECT_STATE.md
- C:\Users\asus\Documents\Projects\BackTest\memory\projects\2026Q1_limit_up\VERIFY_LAST.md
- C:\Users\asus\Documents\Projects\BackTest\memory\projects\2026Q1_limit_up\HANDOFF_NEXT_CHAT.md
- C:\Users\asus\Documents\Projects\BackTest\memory\projects\2026Q1_limit_up\RESEARCH_MEMORY.md
- C:\Users\asus\Documents\Projects\BackTest\memory\projects\2026Q1_limit_up\POSTMORTEMS.md

## Tracked Memory Location
C:\Users\asus\Documents\Projects\BackTest\memory\projects\2026Q1_limit_up

## Subagent Tracked Files
- C:\Users\asus\Documents\Projects\BackTest\memory\projects\2026Q1_limit_up\SUBAGENT_REGISTRY.md
- C:\Users\asus\Documents\Projects\BackTest\memory\projects\2026Q1_limit_up\SUBAGENT_LEDGER.jsonl

## Runtime Artifacts Location
- C:\Users\asus\Documents\Projects\BackTest\data\projects\2026Q1_limit_up\meta
- C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\2026Q1_limit_up
- C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\2026Q1_limit_up\subagents

## Current Real Capability Boundary
The default project no longer sits at coverage=0: data_validate, promotion gate, verify snapshot, and subagent planning all run on real bars, but only on a pilot subset rather than the full frozen universe.
