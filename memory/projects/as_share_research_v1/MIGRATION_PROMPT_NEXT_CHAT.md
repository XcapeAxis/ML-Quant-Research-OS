# Migration Prompt Next Chat

## Current Total Task
Keep promotion honest by separating data-readiness blockers from strategy-quality blockers.

## Current Phase
Phase 1 Research OS - promotion evaluation

## Current Repo / Branch / HEAD
- repo_root: C:\Users\asus\Documents\Projects\BackTest
- branch: main
- head: d19962e89e811dbdf20fd53f8becd66f470ec318

## Confirmed Facts
- tracked_memory_dir: C:\Users\asus\Documents\Projects\BackTest\memory\projects\as_share_research_v1
- runtime_meta_dir: C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta
- runtime_artifacts_dir: C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1
- current_blocker: Max drawdown 50.44% exceeds 30.00%.; Benchmark or equal-weight baselines are incomplete.

## Unconfirmed Questions
- No additional unconfirmed questions have been recorded yet.

## Recent Critical Failure
Max drawdown 50.44% exceeds 30.00%.; Benchmark or equal-weight baselines are incomplete.

## Current Blocker
Max drawdown 50.44% exceeds 30.00%.; Benchmark or equal-weight baselines are incomplete.

## Subagent Status
- gate_mode: AUTO
- active: none
- blocked: none
- recent_transition: iterative_assess
- continue_using_subagents: no

## Last Iterative Run
- iteration_count: 2
- target_iterations: 3
- max_iterations: 5
- stop_reason: no_verified_progress
- direction_change: False
- blocker_escalation: False
- last_classification: no_meaningful_progress
- max_active_subagents: 0
- subagents_used: none
- subagent_reason: Task breadth is below the minimum threshold for safe decomposition.
- completed: `promote_candidate` did not produce a new verified state change.
- not_done: Max drawdown 50.44% exceeds 30.00%.; Benchmark or equal-weight baselines are incomplete.
- next_recommendation: Break down whether drawdown comes from time-window concentration, name concentration, or long holding tails.

## Next Highest-Priority Action
Break down whether drawdown comes from time-window concentration, name concentration, or long holding tails.

## Avoid Repeating Work
- Do not move durable memory back into ignored runtime directories.
- Do not trust default-project research claims until validated bars exist for the frozen universe.

## Required Verification First
- python -m quant_mvp data_validate --project as_share_research_v1

## Read These Files First If Context Is Thin
- C:\Users\asus\Documents\Projects\BackTest\memory\projects\as_share_research_v1\PROJECT_STATE.md
- C:\Users\asus\Documents\Projects\BackTest\memory\projects\as_share_research_v1\VERIFY_LAST.md
- C:\Users\asus\Documents\Projects\BackTest\memory\projects\as_share_research_v1\HANDOFF_NEXT_CHAT.md
- C:\Users\asus\Documents\Projects\BackTest\memory\projects\as_share_research_v1\RESEARCH_MEMORY.md
- C:\Users\asus\Documents\Projects\BackTest\memory\projects\as_share_research_v1\POSTMORTEMS.md

## Tracked Memory Location
C:\Users\asus\Documents\Projects\BackTest\memory\projects\as_share_research_v1

## Subagent Tracked Files
- C:\Users\asus\Documents\Projects\BackTest\memory\projects\as_share_research_v1\SUBAGENT_REGISTRY.md
- C:\Users\asus\Documents\Projects\BackTest\memory\projects\as_share_research_v1\SUBAGENT_LEDGER.jsonl

## Runtime Artifacts Location
- C:\Users\asus\Documents\Projects\BackTest\data\projects\as_share_research_v1\meta
- C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1
- C:\Users\asus\Documents\Projects\BackTest\artifacts\projects\as_share_research_v1\subagents

## Current Real Capability Boundary
Research inputs are ready, but the candidate still fails strategy-quality checks.
