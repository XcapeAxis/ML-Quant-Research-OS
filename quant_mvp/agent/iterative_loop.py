from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from subprocess import DEVNULL, check_output
from typing import Any, Protocol

from ..config import load_config
from ..data.validate_flow import run_data_validate_flow
from ..memory.writeback import load_machine_state, record_iterative_run, save_machine_state
from ..project import resolve_project_paths
from ..promotion import promote_candidate
from ..research_audit import run_research_audit
from .runner import run_agent_cycle
from .subagent_policy import evaluate_subagent_plan, load_subagent_policy, load_subagent_roles
from .subagent_registry import summarize_subagent_state
from .subagent_models import SubagentTaskProfile


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _normalize_blocker_key(text: str) -> str:
    lowered = str(text or "").strip().lower()
    if not lowered or lowered == "none":
        return "none"
    if any(token in lowered for token in ["validated bars", "coverage", "readiness", "missing_research_inputs", "bars"]):
        return "data_inputs"
    if "drawdown" in lowered:
        return "max_drawdown"
    if "leakage" in lowered:
        return "leakage"
    if "walk" in lowered:
        return "walk_forward"
    if "benchmark" in lowered or "baseline" in lowered:
        return "baseline_integrity"
    return lowered.replace(" ", "_")[:80]


def _direction_for_blocker(blocker_key: str) -> str:
    if blocker_key == "data_inputs":
        return "input_recovery"
    if blocker_key in {"max_drawdown", "leakage", "walk_forward", "baseline_integrity"}:
        return "strategy_diagnostics"
    if blocker_key == "none":
        return "verification"
    return "control_plane_verification"


def _worktree_safe(root: Path) -> bool:
    try:
        conflicts = check_output(
            ["git", "diff", "--name-only", "--diff-filter=U"],
            cwd=root,
            text=True,
            stderr=DEVNULL,
        ).strip()
    except Exception:
        return True
    return not bool(conflicts)


@dataclass(frozen=True)
class LoopConfig:
    target_iterations: int = 3
    max_iterations: int = 5

    def __post_init__(self) -> None:
        if self.target_iterations <= 0:
            raise ValueError("target_iterations must be positive")
        if self.max_iterations < self.target_iterations:
            raise ValueError("max_iterations must be >= target_iterations")


@dataclass(frozen=True)
class RepoTruth:
    current_task: str
    current_phase: str
    current_blocker: str
    blocker_key: str
    direction: str
    context_clear: bool
    worktree_safe: bool
    risk_level: str
    data_ready: bool | None
    next_priority_action: str
    current_capability_boundary: str
    last_verified_capability: str
    last_failed_capability: str
    failure_scope_score: int
    sources: list[str] = field(default_factory=list)
    state_snapshot: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LoopAction:
    name: str
    rationale: str
    expected_outcome: str
    risk_level: str = "low"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VerificationResult:
    classification: str
    summary: str
    verified_progress: bool
    new_information: bool
    direction_changed: bool = False
    failure_scope_expanded: bool = False
    allow_extra_iteration: bool = False
    stop_reason: str | None = None
    next_recommendation: str = ""
    artifact_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class IterativeLoopDriver(Protocol):
    def rescan(self, *, project: str, repo_root: Path | None = None, config_path: Path | None = None) -> RepoTruth:
        ...

    def choose_action(self, *, truth: RepoTruth, history: list[dict[str, Any]], config: LoopConfig) -> LoopAction | None:
        ...

    def execute(
        self,
        *,
        project: str,
        action: LoopAction,
        repo_root: Path | None = None,
        config_path: Path | None = None,
    ) -> dict[str, Any]:
        ...

    def verify(
        self,
        *,
        action: LoopAction,
        before: RepoTruth,
        after: RepoTruth,
        execution: dict[str, Any],
        history: list[dict[str, Any]],
        config: LoopConfig,
    ) -> VerificationResult:
        ...


class DefaultIterativeLoopDriver:
    def rescan(self, *, project: str, repo_root: Path | None = None, config_path: Path | None = None) -> RepoTruth:
        _, state = load_machine_state(project, repo_root=repo_root)
        cfg, paths = load_config(project, config_path=config_path)
        blocker = str(state.get("current_blocker") or state.get("last_failure", {}).get("root_cause") or "unknown")
        readiness = (state.get("verify_last", {}) or {}).get("default_project_data_status", "")
        blocker_key = _normalize_blocker_key(blocker)
        data_ready = None
        readiness_lower = str(readiness).lower()
        if blocker_key == "data_inputs":
            data_ready = False
        elif any(token in readiness_lower for token in ["ready", "promotion-grade", "data-ready"]):
            data_ready = True
        elif any(token in readiness_lower for token in ["pilot", "partial", "missing", "blocked"]):
            data_ready = False
        risk_level = "high" if blocker_key in {"leakage", "baseline_integrity"} else "medium" if blocker_key == "max_drawdown" else "low"
        context_clear = bool(blocker and state.get("next_priority_action") and state.get("current_phase"))
        failure_scope_score = max(1 if blocker_key != "none" else 0, len([item for item in blocker.split(";") if item.strip()]))
        return RepoTruth(
            current_task=str(state.get("current_task", "unknown")),
            current_phase=str(state.get("current_phase", "unknown")),
            current_blocker=blocker,
            blocker_key=blocker_key,
            direction=_direction_for_blocker(blocker_key),
            context_clear=context_clear,
            worktree_safe=_worktree_safe(paths.root),
            risk_level=risk_level,
            data_ready=data_ready,
            next_priority_action=str(state.get("next_priority_action", "unknown")),
            current_capability_boundary=str(state.get("current_capability_boundary", "unknown")),
            last_verified_capability=str(state.get("last_verified_capability", "unknown")),
            last_failed_capability=str(state.get("last_failed_capability", "unknown")),
            failure_scope_score=failure_scope_score,
            sources=[str(paths.session_state_path), str(paths.project_state_path), str(paths.verify_last_path)],
            state_snapshot=state,
        )

    def choose_action(self, *, truth: RepoTruth, history: list[dict[str, Any]], config: LoopConfig) -> LoopAction | None:
        if not truth.context_clear or not truth.worktree_safe:
            return None
        if truth.blocker_key == "data_inputs" or truth.data_ready is False:
            return LoopAction(
                name="data_validate",
                rationale="The repo truth still points to a data/readiness blocker, so the lowest-risk next action is to refresh validated inputs and readiness.",
                expected_outcome="Refresh coverage-gap and readiness artifacts, then rescan the blocker.",
            )
        if truth.blocker_key in {"max_drawdown", "leakage", "walk_forward", "baseline_integrity"}:
            return LoopAction(
                name="promote_candidate",
                rationale="The current blocker is strategy- or gate-specific, so promotion diagnostics give the highest-signal next truth without widening the change set.",
                expected_outcome="Refresh the promotion gate and strategy failure report for the current research universe.",
            )
        if not history:
            return LoopAction(
                name="research_audit",
                rationale="A control-plane rescan should start by refreshing the repo audit before another dry-run cycle.",
                expected_outcome="Refresh audit docs and confirm the current repo boundary.",
            )
        return LoopAction(
            name="agent_cycle_dry_run",
            rationale="After the current truth is refreshed, the next low-risk step is one dry-run control-plane cycle.",
            expected_outcome="Regenerate one bounded cycle record plus updated hypothesis and evaluation state.",
        )

    def execute(
        self,
        *,
        project: str,
        action: LoopAction,
        repo_root: Path | None = None,
        config_path: Path | None = None,
    ) -> dict[str, Any]:
        if action.name == "data_validate":
            return run_data_validate_flow(project=project, config_path=config_path, full_refresh=True)
        if action.name == "research_audit":
            return run_research_audit(project, repo_root=repo_root, config_path=config_path)
        if action.name == "promote_candidate":
            return promote_candidate(project, config_path=config_path)
        if action.name == "agent_cycle_dry_run":
            return run_agent_cycle(project=project, dry_run=True, repo_root=repo_root, config_path=config_path)
        raise ValueError(f"Unsupported loop action: {action.name}")

    def verify(
        self,
        *,
        action: LoopAction,
        before: RepoTruth,
        after: RepoTruth,
        execution: dict[str, Any],
        history: list[dict[str, Any]],
        config: LoopConfig,
    ) -> VerificationResult:
        artifact_refs: list[str] = []
        for key, value in execution.items():
            if isinstance(value, str) and (":" in value or "\\" in value or "/" in value):
                artifact_refs.append(value)
        direction_changed = before.direction != after.direction or before.blocker_key != after.blocker_key
        failure_scope_expanded = after.failure_scope_score > before.failure_scope_score and after.blocker_key != before.blocker_key
        if action.name == "data_validate" and before.data_ready is False and after.data_ready is True:
            return VerificationResult(
                classification="verified_progress",
                summary="Validated inputs and readiness improved enough to justify one more bounded iteration.",
                verified_progress=True,
                new_information=True,
                direction_changed=direction_changed,
                allow_extra_iteration=True,
                next_recommendation=after.next_priority_action,
                artifact_refs=artifact_refs,
            )
        if direction_changed:
            return VerificationResult(
                classification="direction_corrected",
                summary=f"Repo truth changed from `{before.blocker_key}` to `{after.blocker_key}` after `{action.name}`.",
                verified_progress=True,
                new_information=True,
                direction_changed=True,
                allow_extra_iteration=action.name == "data_validate",
                next_recommendation=after.next_priority_action,
                artifact_refs=artifact_refs,
            )
        if before.current_blocker != after.current_blocker:
            return VerificationResult(
                classification="blocker_clarified",
                summary=f"`{action.name}` clarified the current blocker without clearing it.",
                verified_progress=False,
                new_information=True,
                failure_scope_expanded=failure_scope_expanded,
                allow_extra_iteration=False,
                next_recommendation=after.next_priority_action,
                artifact_refs=artifact_refs,
            )
        return VerificationResult(
            classification="no_meaningful_progress",
            summary=f"`{action.name}` did not produce a new verified state change.",
            verified_progress=False,
            new_information=False,
            failure_scope_expanded=failure_scope_expanded,
            allow_extra_iteration=False,
            next_recommendation=after.next_priority_action,
            artifact_refs=artifact_refs,
        )


def _policy_path(root: Path) -> Path:
    return root / "configs" / "subagent_policy.yaml"


def _roles_path(root: Path) -> Path:
    return root / "configs" / "subagent_roles.yaml"


def _assess_subagents(*, project: str, truth: RepoTruth, action: LoopAction, repo_root: Path | None = None) -> dict[str, Any]:
    _, state = load_machine_state(project, repo_root=repo_root)
    root = resolve_project_paths(project, root=repo_root).root
    try:
        policy = load_subagent_policy(_policy_path(root))
        roles = load_subagent_roles(_roles_path(root))
    except Exception:
        return {
            "gate_mode": "OFF",
            "recommended_count": 0,
            "recommended_roles": [],
            "should_expand": False,
            "reason": "Subagent policy files are unavailable.",
        }

    breadth = 1 if truth.blocker_key in {"data_inputs", "max_drawdown", "none"} else 2
    profile = SubagentTaskProfile(
        task_summary=f"{action.name}: {truth.current_blocker}",
        breadth=breadth,
        independence=0.2 if breadth == 1 else 0.7,
        file_overlap=0.8 if breadth == 1 else 0.25,
        validation_load=0.4 if action.name in {"data_validate", "promote_candidate"} else 0.7,
        coordination_cost=0.6 if breadth == 1 else 0.3,
        risk_isolation=0.2 if truth.blocker_key == "data_inputs" else 0.5,
        focus_tags=[truth.blocker_key, action.name],
    )
    plan = evaluate_subagent_plan(profile, gate_mode=state.get("subagent_gate_mode", "AUTO"), policy=policy, role_templates=roles)
    state["subagent_plan"] = plan.to_dict()
    state["subagent_continue_recommended"] = plan.should_expand
    state["subagent_continue_reason"] = plan.rationale if plan.should_expand else plan.no_split_reason
    state["subagent_last_event"] = {
        "timestamp": _utc_now(),
        "action": "iterative_assess",
        "summary": state["subagent_continue_reason"],
        "related_ids": [],
    }
    save_machine_state(project, state, repo_root=repo_root)
    return {
        "gate_mode": state.get("subagent_gate_mode", "AUTO"),
        "recommended_count": plan.recommended_count,
        "recommended_roles": plan.recommended_roles,
        "should_expand": plan.should_expand,
        "reason": state["subagent_continue_reason"],
    }


def _decision_to_stop_reason(
    *,
    iteration: int,
    config: LoopConfig,
    truth: RepoTruth,
    verification: VerificationResult,
    blocker_count: int,
    no_new_information_streak: int,
) -> str | None:
    if verification.stop_reason:
        return verification.stop_reason
    if verification.failure_scope_expanded:
        return "verification_failed_scope_expanded"
    if not truth.worktree_safe:
        return "worktree_not_suitable"
    if not truth.context_clear:
        return "insufficient_context"
    if blocker_count >= 3:
        return "low_roi_repeated_blocker"
    if not verification.verified_progress and not verification.new_information:
        if no_new_information_streak >= 2:
            return "no_new_information_twice"
        return "no_verified_progress"
    if iteration >= config.max_iterations:
        return "max_iterations_reached"
    if iteration >= config.target_iterations and not verification.allow_extra_iteration:
        return "target_iterations_reached"
    return None


def run_iterative_loop(
    *,
    project: str,
    target_iterations: int = 3,
    max_iterations: int = 5,
    driver: IterativeLoopDriver | None = None,
    repo_root: Path | None = None,
    config_path: Path | None = None,
) -> dict[str, Any]:
    driver = driver or DefaultIterativeLoopDriver()
    config = LoopConfig(target_iterations=target_iterations, max_iterations=max_iterations)
    run_id = f"{project}-iterative-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
    history: list[dict[str, Any]] = []
    stop_reason = "target_iterations_reached"
    blocker_count = 0
    last_blocker_key = ""
    no_new_information_streak = 0
    direction_change = False
    blocker_escalation = False
    max_active_subagents = 0
    final_truth: RepoTruth | None = None
    final_verification: VerificationResult | None = None
    subagent_reason = "No subagents were activated."
    subagents_used: list[str] = []
    classification = "no_meaningful_progress"

    for iteration in range(1, config.max_iterations + 1):
        before = driver.rescan(project=project, repo_root=repo_root, config_path=config_path)
        if not before.context_clear:
            stop_reason = "insufficient_context"
            final_truth = before
            break
        if not before.worktree_safe:
            stop_reason = "worktree_not_suitable"
            final_truth = before
            break
        action = driver.choose_action(truth=before, history=history, config=config)
        if action is None:
            stop_reason = "stage_stop_condition_met"
            final_truth = before
            break

        subagent_plan = _assess_subagents(project=project, truth=before, action=action, repo_root=repo_root)
        subagent_reason = str(subagent_plan.get("reason", subagent_reason))
        subagents_used = list(subagent_plan.get("recommended_roles", [])) if subagent_plan.get("should_expand") else []
        _, state = load_machine_state(project, repo_root=repo_root)
        max_active_subagents = max(max_active_subagents, len(summarize_subagent_state(state).get("active_ids", [])))

        execution = driver.execute(project=project, action=action, repo_root=repo_root, config_path=config_path)
        after = driver.rescan(project=project, repo_root=repo_root, config_path=config_path)
        verification = driver.verify(
            action=action,
            before=before,
            after=after,
            execution=execution,
            history=history,
            config=config,
        )
        classification = verification.classification
        direction_change = direction_change or verification.direction_changed

        blocker_key = after.blocker_key
        if blocker_key == last_blocker_key and blocker_key not in {"", "none"}:
            blocker_count += 1
        else:
            blocker_count = 1 if blocker_key not in {"", "none"} else 0
            last_blocker_key = blocker_key
        blocker_escalation = blocker_escalation or blocker_count >= 3
        no_new_information_streak = no_new_information_streak + 1 if not verification.new_information else 0

        history.append(
            {
                "iteration": iteration,
                "before": before.to_dict(),
                "action": action.to_dict(),
                "execution": execution,
                "after": after.to_dict(),
                "verification": verification.to_dict(),
                "subagent_plan": subagent_plan,
                "blocker_count": blocker_count,
            },
        )
        final_truth = after
        final_verification = verification

        stop = _decision_to_stop_reason(
            iteration=iteration,
            config=config,
            truth=after,
            verification=verification,
            blocker_count=blocker_count,
            no_new_information_streak=no_new_information_streak,
        )
        if stop:
            stop_reason = stop
            break

    final_truth = final_truth or driver.rescan(project=project, repo_root=repo_root, config_path=config_path)
    completed = final_verification.summary if final_verification else "No iteration ran because the loop stopped at the initial safety gate."
    not_done = final_truth.current_blocker if final_truth.current_blocker else stop_reason
    next_recommendation = (
        final_verification.next_recommendation
        if final_verification and final_verification.next_recommendation
        else final_truth.next_priority_action
    )
    result = {
        "run_id": run_id,
        "timestamp": _utc_now(),
        "project": project,
        "target_iterations": config.target_iterations,
        "max_iterations": config.max_iterations,
        "iteration_count": len(history),
        "stop_reason": stop_reason,
        "direction_change": direction_change,
        "blocker_escalation": blocker_escalation,
        "blocker_key": final_truth.blocker_key,
        "classification": classification,
        "verified_progress": bool(final_verification and final_verification.verified_progress),
        "new_information": bool(final_verification and final_verification.new_information),
        "completed": completed,
        "not_done": not_done,
        "next_recommendation": next_recommendation,
        "current_task": final_truth.current_task,
        "current_phase": final_truth.current_phase,
        "current_blocker": final_truth.current_blocker,
        "current_capability_boundary": final_truth.current_capability_boundary,
        "last_verified_capability": final_truth.last_verified_capability,
        "last_failed_capability": final_truth.last_failed_capability,
        "max_active_subagents": max_active_subagents,
        "subagents_used": subagents_used,
        "subagent_reason": subagent_reason,
        "iterations": history,
        "postmortem_required": stop_reason in {"no_verified_progress", "no_new_information_twice", "low_roi_repeated_blocker", "verification_failed_scope_expanded"},
        "postmortem_summary": not_done,
    }
    record_paths = record_iterative_run(project, result, repo_root=repo_root)
    result["record_paths"] = {key: str(value) for key, value in record_paths.items()}
    result["checkpoint"] = render_iterative_checkpoint(result)
    return result


def render_iterative_checkpoint(result: dict[str, Any]) -> str:
    lines = [
        "Done",
        f"- {result.get('completed', 'none recorded')}",
        f"- direction_change: {result.get('direction_change', False)}",
        "Evidence",
        f"- stop_reason={result.get('stop_reason', 'unknown')}",
        f"- iterations={result.get('iteration_count', 0)}/{result.get('target_iterations', 0)} target, max={result.get('max_iterations', 0)}",
        "Next action",
        f"- {result.get('next_recommendation', 'none recorded')}",
        "Subagent status",
        f"- gate mode: AUTO",
        f"- max active: {result.get('max_active_subagents', 0)}",
        f"- active/blocked/retired/merged: main agent only; {result.get('subagent_reason', 'no extra subagents')}",
    ]
    return "\n".join(lines)
