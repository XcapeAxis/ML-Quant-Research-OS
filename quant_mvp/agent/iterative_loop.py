from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from subprocess import DEVNULL, check_output
from typing import Any, Protocol

from ..config import load_config
from ..data.validate_flow import run_data_validate_flow
from ..memory.localization import humanize_text, zh_bool
from ..memory.writeback import load_machine_state, record_iterative_run, save_machine_state
from ..promotion import promote_candidate
from ..research_audit import run_research_audit
from .runner import run_agent_cycle
from .subagent_controller import reconcile_loop_subagents
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


def _historical_blocker_count(truth: RepoTruth, blocker_key: str | None = None) -> int:
    loop = (truth.state_snapshot.get("iterative_loop", {}) or {}) if truth.state_snapshot else {}
    history = dict(loop.get("blocker_history", {}) or {})
    key = str(blocker_key or truth.blocker_key or "").strip()
    if not key:
        return 0
    payload = dict(history.get(key, {}) or {})
    return int(payload.get("count", 0) or 0)


def _effective_next_recommendation(
    *,
    blocker_key: str,
    blocker_repeat_count: int,
    direction_changed: bool,
    default_next_recommendation: str,
    fallback_next_action: str,
) -> str:
    recommendation = str(default_next_recommendation or fallback_next_action or "").strip()
    if blocker_key in {"", "none"} or direction_changed:
        return recommendation
    if blocker_repeat_count >= 3:
        return (
            f"Escalated blocker `{blocker_key}`: stop automatic retries, narrow the path, and write back the root-cause "
            "diagnosis before the next run."
        )
    if blocker_repeat_count == 2:
        return f"Run a finer root-cause diagnosis for `{blocker_key}` before another automation iteration."
    return recommendation


def _subagent_status_snapshot(*, state: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    records = list(state.get("subagents", []))
    active_ids = [str(item.get("subagent_id", "")) for item in records if item.get("status") == "active" and item.get("subagent_id")]
    blocked_ids = [str(item.get("subagent_id", "")) for item in records if item.get("status") == "blocked" and item.get("subagent_id")]
    active_count = sum(1 for item in records if item.get("status") == "active")
    blocked_count = sum(1 for item in records if item.get("status") == "blocked")
    retired_count = sum(1 for item in records if item.get("status") == "retired")
    merged_count = sum(1 for item in records if item.get("status") == "merged")
    archived_count = sum(1 for item in records if item.get("status") == "archived")
    canceled_count = sum(1 for item in records if item.get("status") == "canceled")
    refactored_count = sum(1 for item in records if item.get("status") == "refactored")
    return {
        "gate_mode": str(plan.get("effective_gate_mode") or state.get("subagent_gate_mode", "AUTO")),
        "recommended_count": int(plan.get("recommended_count", 0) or 0),
        "should_expand": bool(plan.get("should_expand", False)),
        "active_ids": active_ids,
        "blocked_ids": blocked_ids,
        "active_count": active_count,
        "blocked_count": blocked_count,
        "retired_count": retired_count,
        "merged_count": merged_count,
        "archived_count": archived_count,
        "canceled_count": canceled_count,
        "refactored_count": refactored_count,
        "reason": str(plan.get("reason") or state.get("subagent_continue_reason") or "n/a"),
    }


@dataclass(frozen=True)
class LoopConfig:
    target_productive_minutes: int = 40
    max_runtime_mode: str = "bounded"
    target_iterations: int = 4
    max_iterations: int = 6
    min_substantive_actions: int = 2
    target_substantive_actions: int = 3
    clarify_only_limit: int = 1

    def __post_init__(self) -> None:
        if self.target_productive_minutes <= 0:
            raise ValueError("target_productive_minutes must be positive")
        if self.target_iterations <= 0:
            raise ValueError("target_iterations must be positive")
        if self.max_iterations < self.target_iterations:
            raise ValueError("max_iterations must be >= target_iterations")
        if self.min_substantive_actions < 0:
            raise ValueError("min_substantive_actions must be non-negative")
        if self.target_substantive_actions < self.min_substantive_actions:
            raise ValueError("target_substantive_actions must be >= min_substantive_actions")
        if self.clarify_only_limit < 0:
            raise ValueError("clarify_only_limit must be non-negative")


@dataclass
class CampaignRunContext:
    project: str
    paths: Any
    state: dict[str, Any]
    execution_queue: list[dict[str, Any]]
    core_cache: dict[str, str]
    core_paths: dict[str, Path]
    core_mtimes: dict[str, float | None]
    controlled_refreshes: list[str] = field(default_factory=list)


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


def _safe_mtime(path: Path) -> float | None:
    try:
        return path.stat().st_mtime
    except FileNotFoundError:
        return None


def _repo_truth_from_state(*, paths, state: dict[str, Any]) -> RepoTruth:
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


def _default_action_name_for_truth(*, truth: RepoTruth, history: list[dict[str, Any]]) -> str | None:
    if not truth.context_clear or not truth.worktree_safe:
        return None
    if truth.blocker_key == "data_inputs" or truth.data_ready is False:
        return "data_validate"
    if truth.blocker_key in {"max_drawdown", "leakage", "walk_forward", "baseline_integrity"}:
        return "promote_candidate"
    if not history:
        return "research_audit"
    return "agent_cycle_dry_run"


def _loop_action_for_name(name: str, *, truth: RepoTruth, history: list[dict[str, Any]]) -> LoopAction | None:
    if name == "data_validate":
        return LoopAction(
            name="data_validate",
            rationale="默认项目仍受数据/readiness blocker 约束，当前最高 ROI 的低风险动作仍是刷新 validated inputs 和 readiness。",
            expected_outcome="刷新 coverage-gap 与 readiness artifacts，并确认 blocker 是否缩小。",
        )
    if name == "promote_candidate":
        return LoopAction(
            name="promote_candidate",
            rationale="当前 blocker 落在策略或 gate 诊断面，promotion diagnostics 能提供更高信息量且不扩大改动面。",
            expected_outcome="刷新 promotion gate 与 strategy failure report，重新确认当前研究边界。",
        )
    if name == "research_audit":
        return LoopAction(
            name="research_audit",
            rationale="在继续推进前先刷新 repo truth 与 audit baseline，可减少后续错误方向。",
            expected_outcome="更新审计文档并确认当前 repo capability boundary。",
        )
    if name == "agent_cycle_dry_run":
        return LoopAction(
            name="agent_cycle_dry_run",
            rationale="当 repo truth 已刷新后，用一次 dry-run control plane cycle 获取下一条高信号 truth。",
            expected_outcome="生成一个受控 cycle record，并带回新的 hypothesis/evaluation 线索。",
        )
    return None


def _seed_execution_queue() -> list[dict[str, Any]]:
    return [
        {
            "task_id": "recover_daily_bars",
            "title": "恢复默认项目可用日频 bars",
            "impact": "high",
            "risk": "low",
            "prerequisite": "无",
            "current_status": "queued",
            "owner": "main",
            "success_condition": "`data_validate` 后 blocker 缩小或 `data_ready=True`。",
            "stop_condition": "full refresh 后仍无新证据且 blocker 未缩小。",
            "action_name": "data_validate",
            "requires_data_ready": False,
        },
        {
            "task_id": "refresh_research_audit",
            "title": "刷新 repo truth 与审计基线",
            "impact": "medium",
            "risk": "low",
            "prerequisite": "以当前 blocker 重新确认 repo truth。",
            "current_status": "queued",
            "owner": "main",
            "success_condition": "审计结果让下一轮选择更确定。",
            "stop_condition": "审计结果没有带来新的边界信息。",
            "action_name": "research_audit",
            "requires_data_ready": False,
        },
        {
            "task_id": "refresh_promotion_boundary",
            "title": "刷新晋级边界诊断",
            "impact": "high",
            "risk": "medium",
            "prerequisite": "默认项目具备可研究输入。",
            "current_status": "queued",
            "owner": "main",
            "success_condition": "promotion 失败边界被重新确认或收窄。",
            "stop_condition": "输入仍不足，继续执行 ROI 过低。",
            "action_name": "promote_candidate",
            "requires_data_ready": True,
        },
        {
            "task_id": "dry_run_agent_cycle",
            "title": "跑一次 dry-run control plane",
            "impact": "medium",
            "risk": "medium",
            "prerequisite": "默认项目具备可研究输入。",
            "current_status": "queued",
            "owner": "main",
            "success_condition": "dry-run 结果带来新的候选或 blocker 收敛。",
            "stop_condition": "dry-run 只重复旧 blocker 且没有新信息。",
            "action_name": "agent_cycle_dry_run",
            "requires_data_ready": True,
        },
    ]


def _merge_execution_queue(existing: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    merged = {item["task_id"]: dict(item) for item in _seed_execution_queue()}
    for item in existing or []:
        task_id = str(item.get("task_id", "")).strip()
        if not task_id:
            continue
        base = merged.get(task_id, {})
        base.update(item)
        merged[task_id] = base
    return list(merged.values())


def _sync_queue_with_truth(queue: list[dict[str, Any]], truth: RepoTruth) -> list[dict[str, Any]]:
    updated: list[dict[str, Any]] = []
    for raw in queue:
        item = dict(raw)
        status = str(item.get("current_status", "queued"))
        if item.get("action_name") == "data_validate":
            if truth.data_ready is True and truth.blocker_key != "data_inputs":
                status = "done" if item.get("selected_count", 0) else "advanced"
            elif truth.blocker_key == "data_inputs" or truth.data_ready is False:
                status = "ready" if status not in {"done", "advanced"} else status
            elif status == "blocked":
                status = "queued"
        elif item.get("requires_data_ready"):
            if truth.data_ready is True:
                if status == "blocked":
                    status = "ready"
            elif status not in {"done", "advanced"}:
                status = "blocked"
        elif status == "blocked":
            status = "queued"
        item["current_status"] = status
        updated.append(item)
    return updated


def _queue_task_score(*, task: dict[str, Any], truth: RepoTruth, history: list[dict[str, Any]]) -> int:
    status = str(task.get("current_status", "queued"))
    if status not in {"ready", "queued", "advanced"}:
        return -999
    if task.get("requires_data_ready") and truth.data_ready is not True:
        return -999
    score = {"high": 30, "medium": 20, "low": 10}.get(str(task.get("impact", "medium")), 20)
    score += {"low": 12, "medium": 6, "high": 0}.get(str(task.get("risk", "medium")), 6)
    score += {"ready": 12, "queued": 4, "advanced": 2}.get(status, 0)
    if task.get("action_name") == _default_action_name_for_truth(truth=truth, history=history):
        score += 8
    score -= int(task.get("selected_count", 0) or 0) * 10
    return score


def _pick_queue_task(*, queue: list[dict[str, Any]], truth: RepoTruth, history: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [dict(item) for item in queue if _queue_task_score(task=item, truth=truth, history=history) > -999]
    if not candidates:
        return None
    candidates.sort(key=lambda item: _queue_task_score(task=item, truth=truth, history=history), reverse=True)
    return candidates[0]


def _mark_queue_selected(queue: list[dict[str, Any]], task_id: str, *, iteration: int) -> list[dict[str, Any]]:
    updated: list[dict[str, Any]] = []
    for raw in queue:
        item = dict(raw)
        if item.get("task_id") == task_id:
            item["current_status"] = "in_progress"
            item["selected_count"] = int(item.get("selected_count", 0) or 0) + 1
            item["last_iteration"] = iteration
        updated.append(item)
    return updated


def _apply_queue_result(
    queue: list[dict[str, Any]],
    *,
    task_id: str | None,
    verification: VerificationResult,
    before: RepoTruth,
    after: RepoTruth,
    iteration: int,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    selected: dict[str, Any] | None = None
    updated: list[dict[str, Any]] = []
    for raw in queue:
        item = dict(raw)
        if task_id and item.get("task_id") == task_id:
            item["last_iteration"] = iteration
            item["last_summary"] = verification.summary
            item["last_classification"] = verification.classification
            if verification.verified_progress:
                item["current_status"] = "done"
            elif verification.classification in {"direction_corrected", "blocker_clarified"} or before.current_blocker != after.current_blocker:
                item["current_status"] = "advanced"
            elif verification.new_information:
                item["current_status"] = "advanced"
            else:
                item["current_status"] = "deferred" if int(item.get("selected_count", 0) or 0) >= 2 else "queued"
            if item.get("action_name") == "data_validate" and after.data_ready is True:
                item["current_status"] = "done"
            selected = item
        updated.append(item)
    return updated, selected


def _queue_frontier(queue: list[dict[str, Any]]) -> str:
    advanced = [str(item.get("title", "")) for item in queue if item.get("current_status") in {"advanced", "done"} and item.get("last_iteration")]
    if advanced:
        return "、".join(advanced[:3])
    return "未记录"


def _top_pending_task(queue: list[dict[str, Any]]) -> str:
    for status in ["ready", "queued", "blocked", "deferred"]:
        for item in queue:
            if item.get("current_status") == status:
                return str(item.get("title", "未记录"))
    return "未记录"


def _is_effective_progress(
    *,
    verification: VerificationResult,
    before: RepoTruth,
    after: RepoTruth,
    selected_task: dict[str, Any] | None,
) -> bool:
    if verification.verified_progress or verification.direction_changed:
        return True
    if before.current_blocker != after.current_blocker or before.blocker_key != after.blocker_key:
        return True
    if selected_task and selected_task.get("current_status") in {"advanced", "done"} and verification.classification != "no_meaningful_progress":
        return True
    return False


def _action_is_clarify_only(*, verification: VerificationResult, effective_progress: bool) -> bool:
    return effective_progress and verification.classification == "blocker_clarified" and not verification.verified_progress


def _build_campaign_context(*, project: str, repo_root: Path | None = None) -> CampaignRunContext:
    paths, state = load_machine_state(project, repo_root=repo_root)
    core_paths = {
        "agents": paths.root / "AGENTS.md",
        "response_contract": paths.root / "docs" / "RESPONSE_CONTRACT.md",
        "project_state": paths.project_state_path,
        "research_memory": paths.research_memory_path,
        "verify_last": paths.verify_last_path,
        "session_state": paths.session_state_path,
        "execution_queue": paths.execution_queue_path,
    }
    core_cache = {name: path.read_text(encoding="utf-8") if path.exists() else "" for name, path in core_paths.items()}
    core_mtimes = {name: _safe_mtime(path) for name, path in core_paths.items()}
    execution_queue = _merge_execution_queue(list(state.get("execution_queue", []) or []))
    truth = _repo_truth_from_state(paths=paths, state=state)
    execution_queue = _sync_queue_with_truth(execution_queue, truth)
    state = dict(state)
    state["execution_queue"] = execution_queue
    return CampaignRunContext(
        project=project,
        paths=paths,
        state=state,
        execution_queue=execution_queue,
        core_cache=core_cache,
        core_paths=core_paths,
        core_mtimes=core_mtimes,
    )


def _refresh_campaign_context(context: CampaignRunContext, *, reason: str) -> CampaignRunContext:
    _, refreshed_state = load_machine_state(context.project, repo_root=context.paths.root)
    refreshed_state = dict(refreshed_state)
    refreshed_state["execution_queue"] = list(context.execution_queue)
    context.state = refreshed_state
    for name in ["project_state", "research_memory", "verify_last", "session_state"]:
        path = context.core_paths[name]
        context.core_cache[name] = path.read_text(encoding="utf-8") if path.exists() else ""
        context.core_mtimes[name] = _safe_mtime(path)
    context.controlled_refreshes.append(reason)
    return context


def _refresh_if_external_change(context: CampaignRunContext) -> CampaignRunContext:
    changed = False
    for name in ["project_state", "research_memory", "verify_last", "session_state"]:
        mtime = _safe_mtime(context.core_paths[name])
        if mtime != context.core_mtimes.get(name):
            changed = True
            break
    if changed:
        return _refresh_campaign_context(context, reason="external_truth_change")
    return context


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
        _, paths = load_config(project, config_path=config_path)
        return _repo_truth_from_state(paths=paths, state=state)

    def choose_action(self, *, truth: RepoTruth, history: list[dict[str, Any]], config: LoopConfig) -> LoopAction | None:
        del config
        name = _default_action_name_for_truth(truth=truth, history=history)
        if not name:
            return None
        return _loop_action_for_name(name, truth=truth, history=history)

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


def _assess_subagents(*, state: dict[str, Any], root: Path, truth: RepoTruth, action: LoopAction) -> dict[str, Any]:
    try:
        policy = load_subagent_policy(_policy_path(root))
        roles = load_subagent_roles(_roles_path(root))
    except Exception:
        return {
            "effective_gate_mode": "OFF",
            "recommended_count": 0,
            "recommended_roles": [],
            "should_expand": False,
            "reason": "Subagent policy files are unavailable.",
        }

    if truth.blocker_key == "data_inputs" or truth.data_ready is False:
        reason = "默认项目仍是单点数据输入 blocker，本轮保持 subagent 有效 OFF，优先把预算花在数据恢复与边界确认上。"
        state["subagent_plan"] = {
            "recommended_count": 0,
            "recommended_roles": [],
            "should_expand": False,
            "effective_gate_mode": "OFF",
        }
        state["subagent_continue_recommended"] = False
        state["subagent_continue_reason"] = reason
        state["subagent_last_event"] = {
            "timestamp": _utc_now(),
            "action": "iterative_assess",
            "summary": reason,
            "related_ids": [],
        }
        return {
            "effective_gate_mode": "OFF",
            "recommended_count": 0,
            "recommended_roles": [],
            "should_expand": False,
            "reason": reason,
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
    return {
        "effective_gate_mode": state.get("subagent_gate_mode", "AUTO"),
        "recommended_count": plan.recommended_count,
        "recommended_roles": plan.recommended_roles,
        "should_expand": plan.should_expand,
        "reason": state["subagent_continue_reason"],
    }


def _ready_queue_count(queue: list[dict[str, Any]]) -> int:
    return sum(1 for item in queue if item.get("current_status") in {"ready", "queued", "advanced"})


def _decision_to_stop_reason(
    *,
    iteration: int,
    config: LoopConfig,
    truth: RepoTruth,
    verification: VerificationResult,
    blocker_repeat_count: int,
    no_effective_progress_streak: int,
    ready_queue_count: int,
    effective_progress: bool,
    substantive_action_count: int,
    clarify_only_iterations: int,
) -> str | None:
    if verification.stop_reason:
        return verification.stop_reason
    if verification.failure_scope_expanded:
        return "verification_failed_scope_expanded"
    if not truth.worktree_safe:
        return "worktree_not_suitable"
    if not truth.context_clear:
        return "insufficient_context"
    if blocker_repeat_count >= 3:
        return "low_roi_repeated_blocker"
    if not effective_progress and ready_queue_count <= 0:
        return "no_verified_progress"
    if no_effective_progress_streak >= 2:
        return "no_effective_progress_twice"
    if clarify_only_iterations > config.clarify_only_limit and substantive_action_count < config.min_substantive_actions:
        return "clarify_only_limit_reached"
    if iteration >= config.max_iterations:
        return "max_iterations_reached"
    if iteration >= config.target_iterations and substantive_action_count >= config.target_substantive_actions:
        return "sufficient_campaign_progress"
    if iteration >= config.target_iterations and substantive_action_count >= config.min_substantive_actions and ready_queue_count <= 0:
        return "target_iterations_reached"
    if iteration >= config.target_iterations and substantive_action_count >= config.min_substantive_actions and not verification.allow_extra_iteration:
        return "target_iterations_reached"
    return None


def run_iterative_loop(
    *,
    project: str,
    target_productive_minutes: int = 40,
    target_iterations: int = 4,
    max_iterations: int = 6,
    min_substantive_actions: int = 2,
    target_substantive_actions: int = 3,
    clarify_only_limit: int = 1,
    driver: IterativeLoopDriver | None = None,
    repo_root: Path | None = None,
    config_path: Path | None = None,
) -> dict[str, Any]:
    driver = driver or DefaultIterativeLoopDriver()
    config = LoopConfig(
        target_productive_minutes=target_productive_minutes,
        target_iterations=target_iterations,
        max_iterations=max_iterations,
        min_substantive_actions=min_substantive_actions,
        target_substantive_actions=target_substantive_actions,
        clarify_only_limit=clarify_only_limit,
    )
    context = _build_campaign_context(project=project, repo_root=repo_root)
    run_id = f"{project}-iterative-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
    history: list[dict[str, Any]] = []
    stop_reason = "target_iterations_reached"
    blocker_count = 0
    last_blocker_key = ""
    no_effective_progress_streak = 0
    direction_change = False
    blocker_escalation = False
    max_active_subagents = 0
    blocker_repeat_count = 0
    historical_blocker_count = 0
    effective_progress_count = 0
    substantive_action_count = 0
    clarify_only_iterations = 0
    final_truth: RepoTruth | None = None
    final_verification: VerificationResult | None = None
    subagent_reason = "No subagents were activated."
    subagents_used: list[str] = []
    classification = "no_meaningful_progress"
    subagent_status = {
        "gate_mode": "AUTO",
        "recommended_count": 0,
        "should_expand": False,
        "active_count": 0,
        "blocked_count": 0,
        "retired_count": 0,
        "merged_count": 0,
        "archived_count": 0,
        "canceled_count": 0,
        "refactored_count": 0,
        "reason": subagent_reason,
    }
    effective_next_recommendation = ""
    auto_closed_subagents: list[dict[str, str]] = []
    alternative_subagents: list[dict[str, str]] = []

    for iteration in range(1, config.max_iterations + 1):
        context = _refresh_if_external_change(context)
        if isinstance(driver, DefaultIterativeLoopDriver):
            before = _repo_truth_from_state(paths=context.paths, state=context.state)
        else:
            before = driver.rescan(project=project, repo_root=repo_root, config_path=config_path)
        context.execution_queue = _sync_queue_with_truth(context.execution_queue, before)
        context.state["execution_queue"] = context.execution_queue
        if not before.context_clear:
            stop_reason = "insufficient_context"
            final_truth = before
            break
        if not before.worktree_safe:
            stop_reason = "worktree_not_suitable"
            final_truth = before
            break

        selected_task = _pick_queue_task(queue=context.execution_queue, truth=before, history=history)
        selected_task_id = ""
        action: LoopAction | None = None
        if isinstance(driver, DefaultIterativeLoopDriver) and selected_task:
            action = _loop_action_for_name(str(selected_task.get("action_name", "")), truth=before, history=history)
            if action is not None:
                selected_task_id = str(selected_task.get("task_id", ""))
        if action is None:
            action = driver.choose_action(truth=before, history=history, config=config)
            if action is not None:
                matching = next(
                    (
                        item
                        for item in context.execution_queue
                        if item.get("action_name") == action.name and item.get("current_status") in {"ready", "queued", "advanced"}
                    ),
                    None,
                )
                if matching is not None:
                    selected_task_id = str(matching.get("task_id", ""))
        if action is None:
            stop_reason = "stage_stop_condition_met"
            final_truth = before
            break
        if selected_task_id:
            context.execution_queue = _mark_queue_selected(context.execution_queue, selected_task_id, iteration=iteration)
            context.state["execution_queue"] = context.execution_queue

        subagent_plan = _assess_subagents(state=context.state, root=context.paths.root, truth=before, action=action)
        subagent_reason = str(subagent_plan.get("reason", subagent_reason))
        reconcile = reconcile_loop_subagents(
            project=project,
            desired_roles=list(subagent_plan.get("recommended_roles", [])),
            should_expand=bool(subagent_plan.get("should_expand")),
            summary=subagent_reason,
            repo_root=context.paths.root,
            state_override=context.state,
            paths_override=context.paths,
            persist=False,
        )
        auto_closed_subagents.extend(reconcile.get("auto_closed", []))
        alternative_subagents.extend(
            [
                {
                    "subagent_id": subagent_id,
                    "role": role,
                }
                for subagent_id, role in zip(reconcile.get("replacement_ids", []), reconcile.get("created_roles", []))
            ],
        )
        summarized = summarize_subagent_state(context.state)
        max_active_subagents = max(max_active_subagents, len(summarized.get("active_ids", [])))
        subagent_status = _subagent_status_snapshot(state=context.state, plan=subagent_plan)
        subagents_used = [record.get("role", "") for record in context.state.get("subagents", []) if record.get("status") == "active"]

        execution = driver.execute(project=project, action=action, repo_root=context.paths.root, config_path=config_path)
        if isinstance(driver, DefaultIterativeLoopDriver):
            context = _refresh_campaign_context(context, reason=f"{action.name}_writeback")
            after = _repo_truth_from_state(paths=context.paths, state=context.state)
        else:
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

        context.execution_queue, selected_queue_task = _apply_queue_result(
            context.execution_queue,
            task_id=selected_task_id or None,
            verification=verification,
            before=before,
            after=after,
            iteration=iteration,
        )
        context.execution_queue = _sync_queue_with_truth(context.execution_queue, after)
        context.state["execution_queue"] = context.execution_queue
        effective_progress = _is_effective_progress(
            verification=verification,
            before=before,
            after=after,
            selected_task=selected_queue_task,
        )
        if effective_progress:
            effective_progress_count += 1
            no_effective_progress_streak = 0
            if _action_is_clarify_only(verification=verification, effective_progress=effective_progress):
                clarify_only_iterations += 1
            else:
                substantive_action_count += 1
        else:
            no_effective_progress_streak += 1

        blocker_key = after.blocker_key
        historical_blocker_count = _historical_blocker_count(before, blocker_key)
        if blocker_key == last_blocker_key and blocker_key not in {"", "none"}:
            blocker_count += 1
        else:
            blocker_count = 1 if blocker_key not in {"", "none"} else 0
            last_blocker_key = blocker_key
        blocker_repeat_count = historical_blocker_count + blocker_count
        blocker_escalation = blocker_escalation or blocker_repeat_count >= 3
        effective_next_recommendation = _effective_next_recommendation(
            blocker_key=blocker_key,
            blocker_repeat_count=blocker_repeat_count,
            direction_changed=verification.direction_changed,
            default_next_recommendation=verification.next_recommendation,
            fallback_next_action=after.next_priority_action,
        )

        history.append(
            {
                "iteration": iteration,
                "before": before.to_dict(),
                "action": action.to_dict(),
                "execution": execution,
                "after": after.to_dict(),
                "verification": verification.to_dict(),
                "subagent_plan": subagent_plan,
                "subagent_reconcile": reconcile,
                "blocker_count": blocker_count,
                "historical_blocker_count": historical_blocker_count,
                "blocker_repeat_count": blocker_repeat_count,
                "effective_progress": effective_progress,
                "selected_task_id": selected_task_id,
                "effective_next_recommendation": effective_next_recommendation,
                "subagent_status": dict(subagent_status),
            },
        )
        final_truth = after
        final_verification = verification

        stop = _decision_to_stop_reason(
            iteration=iteration,
            config=config,
            truth=after,
            verification=verification,
            blocker_repeat_count=blocker_repeat_count,
            no_effective_progress_streak=no_effective_progress_streak,
            ready_queue_count=_ready_queue_count(context.execution_queue),
            effective_progress=effective_progress,
            substantive_action_count=substantive_action_count,
            clarify_only_iterations=clarify_only_iterations,
        )
        if stop:
            stop_reason = stop
            close_status = "archived" if stop in {"low_roi_repeated_blocker", "verification_failed_scope_expanded", "insufficient_context", "worktree_not_suitable"} else "retired"
            final_reconcile = reconcile_loop_subagents(
                project=project,
                desired_roles=[],
                should_expand=False,
                summary=subagent_reason,
                repo_root=context.paths.root,
                close_status_if_unused=close_status,
                state_override=context.state,
                paths_override=context.paths,
                persist=False,
            )
            auto_closed_subagents.extend(final_reconcile.get("auto_closed", []))
            subagent_status = _subagent_status_snapshot(
                state=context.state,
                plan={
                    "recommended_count": context.state.get("subagent_plan", {}).get("recommended_count", 0),
                    "should_expand": context.state.get("subagent_continue_recommended", False),
                    "reason": context.state.get("subagent_continue_reason", subagent_reason),
                    "effective_gate_mode": subagent_status.get("gate_mode", "AUTO"),
                },
            )
            break

    if final_truth is None:
        if isinstance(driver, DefaultIterativeLoopDriver):
            final_truth = _repo_truth_from_state(paths=context.paths, state=context.state)
        else:
            final_truth = driver.rescan(project=project, repo_root=repo_root, config_path=config_path)
    completed = final_verification.summary if final_verification else "初始安全门直接停止，本轮没有进入可执行 iteration。"
    if stop_reason == "low_roi_repeated_blocker":
        completed = f"已对重复 blocker `{final_truth.blocker_key}` 做诚实升级，并停止自动重试。"
    frontier = _queue_frontier(context.execution_queue)
    if frontier != "未记录":
        completed = f"推进执行队列：{frontier}"
    not_done = _top_pending_task(context.execution_queue)
    next_recommendation = (
        effective_next_recommendation
        or (final_verification.next_recommendation if final_verification and final_verification.next_recommendation else final_truth.next_priority_action)
    )
    if not history:
        historical_blocker_count = _historical_blocker_count(final_truth)
        blocker_repeat_count = historical_blocker_count
        subagent_status = _subagent_status_snapshot(
            state=context.state,
            plan={
                "recommended_count": context.state.get("subagent_plan", {}).get("recommended_count", 0),
                "should_expand": context.state.get("subagent_continue_recommended", False),
                "reason": context.state.get("subagent_continue_reason", subagent_reason),
                "effective_gate_mode": subagent_status.get("gate_mode", "AUTO"),
            },
        )
        subagent_reason = str(subagent_status.get("reason", subagent_reason))
    result = {
        "run_id": run_id,
        "timestamp": _utc_now(),
        "project": project,
        "workflow_mode": "campaign",
        "target_productive_minutes": config.target_productive_minutes,
        "max_runtime_mode": config.max_runtime_mode,
        "target_iterations": config.target_iterations,
        "max_iterations": config.max_iterations,
        "min_substantive_actions": config.min_substantive_actions,
        "target_substantive_actions": config.target_substantive_actions,
        "substantive_action_count": substantive_action_count,
        "effective_progress_count": effective_progress_count,
        "clarify_only_iterations": clarify_only_iterations,
        "clarify_only_limit": config.clarify_only_limit,
        "controlled_refresh_count": len(context.controlled_refreshes),
        "run_start_read_count": len(context.core_cache),
        "iteration_count": len(history),
        "stop_reason": stop_reason,
        "direction_change": direction_change,
        "blocker_escalation": blocker_escalation,
        "blocker_key": final_truth.blocker_key,
        "historical_blocker_count": historical_blocker_count,
        "blocker_repeat_count": blocker_repeat_count,
        "classification": classification,
        "verified_progress": bool(final_verification and final_verification.verified_progress),
        "new_information": bool(final_verification and final_verification.new_information),
        "completed": completed,
        "not_done": not_done,
        "next_recommendation": next_recommendation,
        "current_task": final_truth.current_task,
        "current_phase": final_truth.current_phase,
        "current_blocker": final_truth.current_blocker,
        "data_ready": final_truth.data_ready,
        "current_capability_boundary": final_truth.current_capability_boundary,
        "last_verified_capability": final_truth.last_verified_capability,
        "last_failed_capability": final_truth.last_failed_capability,
        "max_active_subagents": max_active_subagents,
        "subagents_used": subagents_used,
        "subagent_reason": subagent_reason,
        "subagent_gate_mode": subagent_status.get("gate_mode", "AUTO"),
        "subagent_status": subagent_status,
        "auto_closed_subagents": auto_closed_subagents,
        "alternative_subagents": alternative_subagents,
        "execution_queue": context.execution_queue,
        "iterations": history,
        "postmortem_required": stop_reason in {"no_verified_progress", "no_effective_progress_twice", "low_roi_repeated_blocker", "verification_failed_scope_expanded"},
        "postmortem_summary": not_done,
    }
    context.state["execution_queue"] = context.execution_queue
    record_paths = record_iterative_run(project, result, repo_root=repo_root, state_override=context.state)
    result["record_paths"] = {key: str(value) for key, value in record_paths.items()}
    _, refreshed_state = load_machine_state(project, repo_root=repo_root)
    if not refreshed_state.get("execution_queue") and result.get("execution_queue"):
        refreshed_state = dict(refreshed_state)
        refreshed_state["execution_queue"] = list(result.get("execution_queue", []))
        save_machine_state(project, refreshed_state, repo_root=repo_root, rebuild_progress=False)
        _, refreshed_state = load_machine_state(project, repo_root=repo_root)
    result["research_progress"] = dict(refreshed_state.get("research_progress", {}) or {})
    result["checkpoint"] = render_iterative_checkpoint(result)
    return result


def render_iterative_checkpoint(result: dict[str, Any]) -> str:
    status = dict(result.get("subagent_status", {}) or {})
    auto_closed = list(result.get("auto_closed_subagents", []) or [])
    alternatives = list(result.get("alternative_subagents", []) or [])
    progress = dict(result.get("research_progress", {}) or {})
    dimension_rows = {
        str(item.get("dimension", "")): item
        for item in progress.get("dimensions", [])
        if isinstance(item, dict)
    }
    active_ids = list(status.get("active_ids", []) or [])
    active_summary = ", ".join(active_ids) if active_ids else f"无（current={status.get('active_count', 0)}）"
    retired_this_run = sum(1 for item in auto_closed if isinstance(item, dict) and item.get("status") == "retired")
    merged_this_run = sum(1 for item in auto_closed if isinstance(item, dict) and item.get("status") == "merged")
    archived_this_run = sum(1 for item in auto_closed if isinstance(item, dict) and item.get("status") == "archived")
    if not result.get("subagents_used") and not auto_closed and not alternatives:
        subagent_explanation = f"未额外启用 subagents：{humanize_text(result.get('subagent_reason', status.get('reason', 'none recorded')))}"
    else:
        subagent_explanation = (
            f"本轮 subagent 结论：{humanize_text(result.get('subagent_reason', status.get('reason', 'none recorded')))}；"
            f"替代分支={', '.join(item.get('subagent_id', '') for item in alternatives) if alternatives else '无'}"
        )
    lines = [
        "Done",
        f"- 本轮真正完成：{humanize_text(result.get('completed', 'none recorded'))}",
        f"- 本轮是否发生方向修正：{zh_bool(result.get('direction_change', False))}",
        "Not done",
        f"- 本轮没有完成：{humanize_text(result.get('not_done', 'none recorded'))}",
        f"- 当前 blocker：{humanize_text(result.get('current_blocker', 'unknown'))}",
        "Research progress",
        "| Dimension | Status | Score | Evidence |",
        "|---|---|---:|---|",
    ]
    for dimension in [
        "Data inputs",
        "Strategy integrity",
        "Validation stack",
        "Promotion readiness",
        "Subagent effectiveness",
    ]:
        item = dimension_rows.get(dimension, {})
        evidence = str(item.get("evidence", "未记录")).replace("|", "/")
        lines.append(
            f"| {dimension} | {item.get('status', 'blocked')} | {int(item.get('score', 0))}/4 | {evidence} |"
        )
    lines.extend(
        [
            f"- Overall trajectory: {progress.get('overall_trajectory', 'blocked')}",
            f"- This-run delta: {progress.get('this_run_delta', 'unchanged')}",
            f"- Current blocker: {humanize_text(progress.get('current_blocker', result.get('current_blocker', 'unknown')))}",
            f"- Next milestone: {humanize_text(progress.get('next_milestone', result.get('next_recommendation', 'none recorded')))}",
            f"- Confidence: {progress.get('confidence', 'low')}",
            "Next recommendation",
            f"- {humanize_text(result.get('next_recommendation', 'none recorded'))}",
            "Subagent status",
            f"- gate mode: {result.get('subagent_gate_mode', status.get('gate_mode', 'AUTO'))}",
            f"- max active this run: {result.get('max_active_subagents', 0)}",
            f"- active: {active_summary}",
            f"- retired/merged/archived this run: {retired_this_run}/{merged_this_run}/{archived_this_run}",
            f"- {subagent_explanation}",
        ],
    )
    return "\n".join(lines)
