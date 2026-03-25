# Postmortems

No recorded failures yet in this bootstrap state. Append new failures with date, experiment id, root cause, and corrective action.

## promotion-gate | promote_candidate
- summary: Candidate failed the current promotion gate.
- root_cause: missing_research_inputs: No bars found for requested codes.
- corrective_action: Resolve the failed gate reasons before the next promotion attempt.

## 2026-03-24T16:22:54 | 2026Q1_limit_up-20260324T162254
- summary: Dry-run blocked by missing research inputs: No bars found for requested codes.
- root_cause: missing_research_inputs: No bars found for requested codes.
- corrective_action: Restore a usable frozen universe plus local bars before rerunning the dry-run cycle.

## promotion-gate | promote_candidate
- summary: Candidate failed the current promotion gate.
- root_cause: Max drawdown 83.38% exceeds 30.00%.
- corrective_action: Resolve the failed gate reasons before the next promotion attempt.
- resolution_status: not_fixed
