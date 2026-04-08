from __future__ import annotations

import re


_EXACT_TEXT = {
    "unknown": "unknown",
    "none": "none",
    "none recorded": "none recorded",
    "none recorded yet": "none recorded yet",
    "n/a": "n/a",
    "not_run": "not run",
    "not_fixed": "not fixed",
    "fixed": "fixed",
    "No iterative loop run has been recorded yet.": "No iterative loop run has been recorded yet.",
    "No recorded failures yet in this bootstrap state. Append new failures with root cause, corrective action, and current resolution status.": (
        "No recorded failures yet in this bootstrap state. Append new failures with root cause, corrective action, and current resolution status."
    ),
    "Subtasks are too coupled to split cleanly.": "Subtasks are too coupled to split cleanly.",
    "High coupling would turn subagents into coordination overhead.": "High coupling would turn subagents into coordination overhead.",
    "File overlap is too high for efficient parallel work.": "File overlap is too high for efficient parallel work.",
    "The same hot files would need frequent merges, so splitting is suppressed.": "The same hot files would need frequent merges, so splitting is suppressed.",
    "The coordination-adjusted score is too low.": "The coordination-adjusted score is too low.",
    "Validation and isolation benefits do not yet offset decomposition cost.": "Validation and isolation benefits do not yet offset decomposition cost.",
    "Subagent policy files are unavailable.": "Subagent policy files are unavailable.",
    "No subagents were activated.": "No subagents were activated.",
    "The default-project data blocker should be cleared before expanding into multiple subagents.": (
        "The default-project data blocker should be cleared before expanding into multiple subagents."
    ),
    "The current default-project blocker does not justify extra coordination yet.": (
        "The current default-project blocker does not justify extra coordination yet."
    ),
    "Stay effectively OFF until validated bars restore independent work packages.": (
        "Stay effectively OFF until validated bars restore independent work packages."
    ),
    "Gate is explicitly OFF.": "Gate is explicitly OFF.",
    "Subagent decomposition is disabled for this task.": "Subagent decomposition is disabled for this task.",
    "Independent work packages exist and the coordination-adjusted score justifies controlled decomposition.": (
        "Independent work packages exist and the coordination-adjusted score justifies controlled decomposition."
    ),
    "Promotion gate diagnostics were generated and written to runtime artifacts.": (
        "Promotion gate diagnostics were generated and written to runtime artifacts."
    ),
    "data_validate refreshed cleaned bars, coverage-gap artifacts, and research readiness.": (
        "data_validate refreshed cleaned bars, coverage-gap artifacts, and research readiness."
    ),
    "data_validate refreshed readiness artifacts and tracked memory.": (
        "data_validate refreshed readiness artifacts and tracked memory."
    ),
    "Validated data recovery, coverage-gap analysis, and readiness writeback all executed.": (
        "Validated data recovery, coverage-gap analysis, and readiness writeback all executed."
    ),
    "Promotion-grade research can proceed on the current validated snapshot.": (
        "Promotion-grade research can proceed on the current validated snapshot."
    ),
    "Coverage improved, but the readiness gate is still blocking broad research claims.": (
        "Coverage improved, but the readiness gate is still blocking broad research claims."
    ),
    "The repo truth still points to a data/readiness blocker, so the lowest-risk next action is to refresh validated inputs and readiness.": (
        "The repo truth still points to a data or readiness blocker, so the lowest-risk next action is to refresh validated inputs and readiness."
    ),
    "Refresh coverage-gap and readiness artifacts, then rescan the blocker.": (
        "Refresh coverage-gap and readiness artifacts, then rescan the blocker."
    ),
    "The current blocker is strategy- or gate-specific, so promotion diagnostics give the highest-signal next truth without widening the change set.": (
        "The current blocker is strategy- or gate-specific, so promotion diagnostics give the highest-signal next truth without widening the change set."
    ),
    "Refresh the promotion gate and strategy failure report for the current research universe.": (
        "Refresh the promotion gate and strategy failure report for the current research universe."
    ),
    "A control-plane rescan should start by refreshing the repo audit before another dry-run cycle.": (
        "A control-plane rescan should start by refreshing the repo audit before another dry-run cycle."
    ),
    "Refresh audit docs and confirm the current repo boundary.": "Refresh audit docs and confirm the current repo boundary.",
    "After the current truth is refreshed, the next low-risk step is one dry-run control-plane cycle.": (
        "After the current truth is refreshed, the next low-risk step is one dry-run control-plane cycle."
    ),
    "Regenerate one bounded cycle record plus updated hypothesis and evaluation state.": (
        "Regenerate one bounded cycle record plus updated hypothesis and evaluation state."
    ),
    "Validated inputs and readiness improved enough to justify one more bounded iteration.": (
        "Validated inputs and readiness improved enough to justify one more bounded iteration."
    ),
    "No additional unconfirmed questions have been recorded yet.": "No additional unconfirmed questions have been recorded yet.",
    "iterative_relevance_review": "iterative relevance review",
    "Do not move durable memory back into ignored runtime directories.": (
        "Do not move durable memory back into ignored runtime directories."
    ),
    "Do not trust default-project research claims until validated bars exist for the frozen universe.": (
        "Do not trust default-project research claims until validated bars exist for the frozen universe."
    ),
    "Run the tracked-memory and contract test suite first.": "Run the tracked-memory and contract test suite first.",
    "verified_progress": "verified progress",
    "blocker_clarified": "blocker clarified",
    "no_meaningful_progress": "no meaningful progress",
    "direction_corrected": "direction corrected",
}

_STOP_REASONS = {
    "no_verified_progress": "No verified progress was recorded in this run.",
    "no_new_information_twice": "No new information was produced in two consecutive runs.",
    "no_effective_progress_twice": "No effective progress was produced in two consecutive runs.",
    "low_roi_repeated_blocker": "The same blocker repeated and the expected ROI is now too low.",
    "verification_failed_scope_expanded": "Verification failed and the blast radius expanded.",
    "max_iterations_reached": "The maximum iteration count was reached.",
    "target_iterations_reached": "The target iteration count was reached.",
    "sufficient_campaign_progress": "This campaign produced enough bounded progress for now.",
    "clarify_only_limit_reached": "The clarify-only limit was reached.",
    "stage_stop_condition_met": "The current stage stop condition was met.",
    "insufficient_context": "The current context is not strong enough to keep pushing safely.",
    "worktree_not_suitable": "The current worktree is not suitable for more automatic progress.",
}

_STATUS_TEXT = {
    "pending": "pending",
    "blocked": "blocked",
    "active": "active",
    "merged": "merged",
    "retired": "retired",
    "canceled": "canceled",
    "archived": "archived",
    "refactored": "refactored",
    "proposed": "proposed",
}

_FRAGMENT_REPLACEMENTS = {
    "Max drawdown": "Max drawdown",
    "exceeds": "exceeds",
    "Validated rows": "Validated rows",
    "are below the minimum readiness floor": "are below the minimum readiness floor",
    "Benchmark or equal-weight baselines are incomplete": "Benchmark or equal-weight baselines are incomplete",
    "Promotion gate blocked the current candidate.": "Promotion gate blocked the current candidate.",
    "Promotion gate blocked on strategy-quality checks.": "Promotion gate blocked on strategy-quality checks.",
    "Promotion gate blocked on data readiness.": "Promotion gate blocked on data readiness.",
    "Promotion gate blocked:": "Promotion gate blocked:",
    "Resolve the failed gate reasons before the next promotion attempt.": (
        "Resolve the failed gate reasons before the next promotion attempt."
    ),
    "Use the strategy failure report to design the next risk-focused experiment.": (
        "Use the strategy failure report to design the next risk-focused experiment."
    ),
    "Use STRATEGY_FAILURE_REPORT to design the next risk-focused experiment.": (
        "Use STRATEGY_FAILURE_REPORT to design the next risk-focused experiment."
    ),
    "Use the strategy failure report and the branch ledger to choose the next bounded branch experiment.": (
        "Use the strategy failure report and the branch ledger to choose the next bounded branch experiment."
    ),
    "Break down whether drawdown comes from time-window concentration, name concentration, or long holding tails.": (
        "Break down whether drawdown comes from time-window concentration, name concentration, or long holding tails."
    ),
    "Run a finer root-cause diagnosis for": "Run a finer root-cause diagnosis for",
    "before another automation iteration.": "before another automation iteration.",
    "Escalated blocker": "Escalated blocker",
    "Escalated repeated blocker": "Escalated repeated blocker",
    "stop automatic retries, narrow the path, and write back the root-cause diagnosis before the next run.": (
        "stop automatic retries, narrow the path, and write back the root-cause diagnosis before the next run."
    ),
    "and stopped automatic retries.": "and stopped automatic retries.",
    "Tracked memory bootstrap does not establish the current business blocker; refresh verified research artifacts before changing the narrative.": (
        "Tracked memory bootstrap does not establish the current business blocker; refresh verified research artifacts before changing the narrative."
    ),
    "Refresh the latest verified research artifacts before changing the blocker narrative.": (
        "Refresh the latest verified research artifacts before changing the blocker narrative."
    ),
    "Tracked memory sync refreshed the current state only; it did not change the canonical blocker.": (
        "Tracked memory sync refreshed the current state only; it did not change the canonical blocker."
    ),
    "Keep the current blocker diagnosis aligned across session_state and verifier artifacts.": (
        "Keep the current blocker diagnosis aligned across session_state and verifier artifacts."
    ),
    "Break down the current max-drawdown driver and compare one bounded challenger before rerunning the dry-run cycle.": (
        "Break down the current max-drawdown driver and compare one bounded challenger before rerunning the dry-run cycle."
    ),
    "Restore the validated snapshot and rerun the dry-run cycle only after the data boundary is healthy again.": (
        "Restore the validated snapshot and rerun the dry-run cycle only after the data boundary is healthy again."
    ),
    "Refresh the blocker diagnosis and narrow one bounded next step before rerunning the dry-run cycle.": (
        "Refresh the blocker diagnosis and narrow one bounded next step before rerunning the dry-run cycle."
    ),
    "Tracked memory synced from config": "Tracked memory synced from config",
    "Tracked memory sync refreshed for plan:": "Tracked memory sync refreshed for plan:",
    "Keep the Phase 1 Research OS reproducible with tracked memory and honest runtime artifacts.": (
        "Keep the Phase 1 Research OS reproducible with tracked memory and honest runtime artifacts."
    ),
    "Keep the Phase 1 Research OS reproducible with tracked long-term memory and honest runtime artifacts.": (
        "Keep the Phase 1 Research OS reproducible with tracked long-term memory and honest runtime artifacts."
    ),
    "Contract and dry-run orchestration tests passed in the repository virtual environment.": (
        "Contract and dry-run orchestration tests passed in the repository virtual environment."
    ),
    "Restore a usable frozen universe plus local bars before rerunning the dry-run cycle.": (
        "Restore a usable frozen universe plus local bars before rerunning the dry-run cycle."
    ),
    "Restore a usable validated bar snapshot for the frozen default universe.": (
        "Restore a usable validated bar snapshot for the frozen default universe."
    ),
    "Use STRATEGY_FAILURE_REPORT and the branch ledger to choose the first bounded drawdown-focused experiment now that baseline completeness passes.": (
        "Use STRATEGY_FAILURE_REPORT and the branch ledger to choose the first bounded drawdown-focused experiment now that baseline completeness passes."
    ),
    "ready coverage:": "ready coverage:",
}


def zh_bool(value: bool) -> str:
    return "yes" if bool(value) else "no"


def zh_status(value: str) -> str:
    key = str(value or "").strip().lower()
    return _STATUS_TEXT.get(key, value)


def zh_stop_reason(value: str) -> str:
    key = str(value or "").strip()
    return _STOP_REASONS.get(key, humanize_text(key))


def humanize_text(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return "none recorded"
    if text in _EXACT_TEXT:
        return _EXACT_TEXT[text]
    if text in _STOP_REASONS:
        return _STOP_REASONS[text]

    lowered = text.lower()
    if lowered in {"true", "false"}:
        return zh_bool(lowered == "true")

    for source, target in _FRAGMENT_REPLACEMENTS.items():
        text = text.replace(source, target)

    text = re.sub(r"\s+", " ", text).strip()
    return text
