# Postmortems

No recorded failures yet in this bootstrap state. Append new failures with date, experiment id, root cause, and corrective action.

## promotion-gate | promote_candidate
- summary: Candidate failed the current promotion gate.
- root_cause: missing_research_inputs: No bars found for requested codes.
- corrective_action: Resolve the failed gate reasons before the next promotion attempt.

## 2026-03-24T16:22:54 | as_share_research_v1-20260324T162254
- summary: Dry-run blocked by missing research inputs: No bars found for requested codes.
- root_cause: missing_research_inputs: No bars found for requested codes.
- corrective_action: Restore a usable frozen universe plus local bars before rerunning the dry-run cycle.

## promotion-gate | promote_candidate
- summary: Candidate failed the current promotion gate.
- root_cause: Max drawdown 83.38% exceeds 30.00%.
- corrective_action: Resolve the failed gate reasons before the next promotion attempt.
- resolution_status: not_fixed

## 2026-03-25T08:18:01+00:00 | as_share_research_v1-20260325T081801+0000
- summary: Promotion gate blocked: Max drawdown 56.50% exceeds 30.00%.
- root_cause: Max drawdown 56.50% exceeds 30.00%.
- corrective_action: Use the strategy failure report to design the next risk-focused experiment.
- resolution_status: not_fixed

## promotion-gate | promote_candidate
- summary: Candidate failed the current promotion gate.
- root_cause: Max drawdown 56.50% exceeds 30.00%.
- corrective_action: Use STRATEGY_FAILURE_REPORT to design the next risk-focused experiment.
- resolution_status: not_fixed

## 2026-03-25T08:23:26+00:00 | as_share_research_v1-20260325T082326+0000
- summary: Promotion gate blocked: Max drawdown 56.50% exceeds 30.00%.
- root_cause: Max drawdown 56.50% exceeds 30.00%.
- corrective_action: Use the strategy failure report to design the next risk-focused experiment.
- resolution_status: not_fixed

## promotion-gate | promote_candidate
- summary: Candidate failed the current promotion gate.
- root_cause: Max drawdown 56.50% exceeds 30.00%.
- corrective_action: Use STRATEGY_FAILURE_REPORT to design the next risk-focused experiment.
- resolution_status: not_fixed

## 2026-03-25T14:35:07+00:00 | as_share_research_v1__legacy_single_branch__20260325T143507Z
- summary: Promotion gate blocked: Max drawdown 50.44% exceeds 30.00%.; Benchmark or equal-weight baselines are incomplete.
- root_cause: Max drawdown 50.44% exceeds 30.00%.; Benchmark or equal-weight baselines are incomplete.
- corrective_action: Use the strategy failure report and the branch ledger to choose the next bounded branch experiment.
- resolution_status: not_fixed

## 2026-03-25T15:02:31+00:00 | as_share_research_v1__legacy_single_branch__20260325T150231Z
- summary: Promotion gate blocked: Max drawdown 50.44% exceeds 30.00%.; Benchmark or equal-weight baselines are incomplete.
- root_cause: Max drawdown 50.44% exceeds 30.00%.; Benchmark or equal-weight baselines are incomplete.
- corrective_action: Use the strategy failure report and the branch ledger to choose the next bounded branch experiment.
- resolution_status: not_fixed

## 2026-03-25T15:09:15+00:00 | as_share_research_v1__legacy_single_branch__20260325T150915Z
- summary: Promotion gate blocked: Max drawdown 50.44% exceeds 30.00%.; Benchmark or equal-weight baselines are incomplete.
- root_cause: Max drawdown 50.44% exceeds 30.00%.; Benchmark or equal-weight baselines are incomplete.
- corrective_action: Use the strategy failure report and the branch ledger to choose the next bounded branch experiment.
- resolution_status: not_fixed

## 2026-03-25T15:15:28+00:00 | as_share_research_v1__legacy_single_branch__20260325T151529Z
- summary: Promotion gate blocked: Max drawdown 50.44% exceeds 30.00%.; Benchmark or equal-weight baselines are incomplete.
- root_cause: Max drawdown 50.44% exceeds 30.00%.; Benchmark or equal-weight baselines are incomplete.
- corrective_action: Use the strategy failure report and the branch ledger to choose the next bounded branch experiment.
- resolution_status: not_fixed

## 2026-03-25T15:22:12+00:00 | as_share_research_v1__legacy_single_branch__20260325T152213Z
- summary: Promotion gate blocked: Max drawdown 50.44% exceeds 30.00%.; Benchmark or equal-weight baselines are incomplete.
- root_cause: Max drawdown 50.44% exceeds 30.00%.; Benchmark or equal-weight baselines are incomplete.
- corrective_action: Use the strategy failure report and the branch ledger to choose the next bounded branch experiment.
- resolution_status: not_fixed

## promotion-gate | promote_candidate
- summary: Candidate failed the current promotion gate.
- root_cause: Max drawdown 56.50% exceeds 30.00%.
- corrective_action: Resolve the failed gate reasons before the next promotion attempt.
- resolution_status: not_fixed

## promotion-gate | promote_candidate
- summary: Candidate failed the current promotion gate.
- root_cause: Max drawdown 56.50% exceeds 30.00%.; Benchmark or equal-weight baselines are incomplete.
- corrective_action: Resolve the failed gate reasons before the next promotion attempt.
- resolution_status: not_fixed

## 2026-03-26T02:03:48Z | promote_candidate
- summary: Promotion gate stayed blocked on the ready 492-name core snapshot.
- root_cause: Max drawdown 56.50% exceeds 30.00%.; Benchmark or equal-weight baselines are incomplete (`benchmark_missing:000001`).
- corrective_action: Trace why benchmark code `000001` is absent from the promotion close panel, then rerun promotion before opening drawdown-focused branch work.
- resolution_status: not_fixed

## promotion-gate | promote_candidate
- summary: Candidate failed the current promotion gate.
- root_cause: Max drawdown 56.50% exceeds 30.00%.; Benchmark or equal-weight baselines are incomplete.
- corrective_action: Resolve the failed gate reasons before the next promotion attempt.
- resolution_status: not_fixed

## promotion-gate | promote_candidate
- summary: Candidate failed the current promotion gate.
- root_cause: Max drawdown 56.50% exceeds 30.00%.
- corrective_action: Resolve the failed gate reasons before the next promotion attempt.
- resolution_status: not_fixed

## 2026-03-26T02:40:36 | as_share_research_v1-20260326T024036
- summary: Promotion gate blocked: Max drawdown 56.50% exceeds 30.00%.
- root_cause: Max drawdown 56.50% exceeds 30.00%.
- corrective_action: Restore a usable frozen universe plus local bars before rerunning the dry-run cycle.
- resolution_status: not_fixed

## promotion-gate | promote_candidate
- summary: Candidate failed the current promotion gate.
- root_cause: Max drawdown 56.50% exceeds 30.00%.
- corrective_action: Resolve the failed gate reasons before the next promotion attempt.
- resolution_status: not_fixed

## 2026-03-26T02:44:04 | as_share_research_v1-20260326T024404
- summary: Promotion gate blocked: Max drawdown 56.50% exceeds 30.00%.; Benchmark or equal-weight baselines are incomplete.
- root_cause: Max drawdown 56.50% exceeds 30.00%.; Benchmark or equal-weight baselines are incomplete.
- corrective_action: Restore a usable frozen universe plus local bars before rerunning the dry-run cycle.
- resolution_status: not_fixed

## promotion-gate | promote_candidate
- summary: Candidate failed the current promotion gate.
- root_cause: Max drawdown 56.50% exceeds 30.00%.
- corrective_action: Resolve the failed gate reasons before the next promotion attempt.
- resolution_status: not_fixed

## 2026-03-26T02:45:47 | as_share_research_v1-20260326T024547
- summary: Promotion gate blocked: Max drawdown 56.50% exceeds 30.00%.
- root_cause: Max drawdown 56.50% exceeds 30.00%.
- corrective_action: Restore a usable frozen universe plus local bars before rerunning the dry-run cycle.
- resolution_status: not_fixed

## 2026-03-26T02:45:47Z | benchmark-baseline-diagnosis
- summary: Benchmark baseline completeness was restored without changing equal-weight baseline semantics.
- root_cause: `run_limit_up_backtest_artifacts` only loaded ranked codes into the strategy close panel, so benchmark code `000001` disappeared whenever it was not ranked.
- corrective_action: Keep the strategy close panel unchanged, but load a dedicated benchmark series and pass it into baseline evaluation for both `promote_candidate` and `agent_cycle`.
- resolution_status: fixed

## 2026-03-26T03:29:38 | as_share_research_v1-20260326T032938
- summary: Promotion gate blocked: Max drawdown 56.50% exceeds 30.00%.
- root_cause: Max drawdown 56.50% exceeds 30.00%.
- corrective_action: Restore a usable frozen universe plus local bars before rerunning the dry-run cycle.
- resolution_status: not_fixed

## promotion-gate | promote_candidate
- summary: Promotion gate blocked the current candidate.
- root_cause: Max drawdown 50.44% exceeds 30.00%.; Benchmark or equal-weight baselines are incomplete.
- corrective_action: Break down whether drawdown comes from time-window concentration, name concentration, or long holding tails.
- resolution_status: not_fixed

## promotion-gate | promote_candidate
- summary: Promotion gate blocked the current candidate.
- root_cause: Max drawdown 50.44% exceeds 30.00%.; Benchmark or equal-weight baselines are incomplete.
- corrective_action: Break down whether drawdown comes from time-window concentration, name concentration, or long holding tails.
- resolution_status: not_fixed

## 2026-03-26T03:30:31+00:00 | as_share_research_v1-iterative-20260326T032946Z
- summary: Max drawdown 50.44% exceeds 30.00%.; Benchmark or equal-weight baselines are incomplete.
- root_cause: Max drawdown 50.44% exceeds 30.00%.; Benchmark or equal-weight baselines are incomplete.
- corrective_action: Break down whether drawdown comes from time-window concentration, name concentration, or long holding tails.
- resolution_status: not_fixed
