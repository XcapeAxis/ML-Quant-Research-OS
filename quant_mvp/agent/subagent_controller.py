from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..memory.ledger import append_jsonl
from ..memory.writeback import load_machine_state, save_machine_state
from ..project import resolve_project_paths
from .subagent_merge import apply_merge_transition
from .subagent_models import GateMode, SubagentEvent, SubagentPlan, SubagentRecord, SubagentTaskProfile
from .subagent_policy import evaluate_subagent_plan, load_subagent_policy, load_subagent_roles
from .subagent_registry import ensure_subagent_runtime_dir


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _policy_path(root: Path) -> Path:
    return root / "configs" / "subagent_policy.yaml"


def _roles_path(root: Path) -> Path:
    return root / "configs" / "subagent_roles.yaml"


def _next_subagent_id(records: list[dict[str, Any]]) -> str:
    salt = uuid.uuid4().hex[:4]
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")
    candidate = f"sa-{stamp}-{salt}"
    existing = {str(record.get("subagent_id", "")) for record in records}
    if candidate not in existing:
        return candidate
    for seq in range(1, 1000):
        retry = f"{candidate}-{seq:03d}"
        if retry not in existing:
            return retry
    raise RuntimeError("Unable to allocate a unique subagent id.")


def _active_subagent_count(records: list[dict[str, Any]]) -> int:
    return sum(1 for item in records if item.get("status") == "active")


def _hard_limit(policy: dict[str, Any]) -> int:
    return int(policy.get("hard_limit", 6))


def _append_event(paths, event: SubagentEvent) -> None:
    append_jsonl(paths.subagent_ledger_path, event.to_dict())


def _summary_for_state(state: dict[str, Any]) -> dict[str, Any]:
    records = list(state.get("subagents", []))
    active = [item["subagent_id"] for item in records if item.get("status") == "active"]
    blocked = [item["subagent_id"] for item in records if item.get("status") == "blocked"]
    retired = [item["subagent_id"] for item in records if item.get("status") in {"retired", "merged", "archived", "canceled"}]
    return {
        "active_ids": active,
        "blocked_ids": blocked,
        "retired_ids": retired,
    }


def plan_subagents(
    *,
    project: str,
    profile: SubagentTaskProfile,
    gate_mode: GateMode = "AUTO",
    activate: bool = False,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    paths, state = load_machine_state(project, repo_root=repo_root)
    policy = load_subagent_policy(_policy_path(paths.root))
    roles = load_subagent_roles(_roles_path(paths.root))
    plan = evaluate_subagent_plan(profile, gate_mode=gate_mode, policy=policy, role_templates=roles)

    records = list(state.get("subagents", []))
    if activate and _active_subagent_count(records) + len(plan.work_packages) > _hard_limit(policy):
        raise ValueError(f"Subagent hard limit exceeded: {_hard_limit(policy)}")
    created_ids: list[str] = []
    timestamp = _utc_now()
    for work_package in plan.work_packages:
        subagent_id = _next_subagent_id(records)
        artifact_dir = ensure_subagent_runtime_dir(paths, subagent_id) if activate else None
        record = SubagentRecord(
            subagent_id=subagent_id,
            role=work_package.role,
            summary=work_package.summary,
            status="active" if activate else "proposed",
            transient=work_package.transient,
            allowed_paths=work_package.allowed_paths,
            expected_artifacts=work_package.expected_artifacts,
            artifact_dir=str(artifact_dir) if artifact_dir else None,
            subagent_type="infrastructure",
            blocker_scope=profile.task_summary,
            research_focus=work_package.summary,
            decision_impact="为后续研究准备前提；不是直接推进某条策略。",
            created_at=timestamp,
            updated_at=timestamp,
            last_action="spawn" if activate else "propose",
            last_note=plan.rationale if plan.should_expand else plan.no_split_reason,
        )
        records.append(record.to_dict())
        created_ids.append(subagent_id)
        _append_event(
            paths,
            SubagentEvent(
                timestamp=timestamp,
                action="spawn" if activate else "propose",
                project=project,
                subagent_id=subagent_id,
                from_status="none",
                to_status=record.status,
                summary=record.last_note,
                subagent_type=record.subagent_type,
                blocker_scope=record.blocker_scope,
                decision_impact=record.decision_impact,
                artifact_refs=[str(artifact_dir)] if artifact_dir else [],
            ),
        )

    state["subagent_gate_mode"] = gate_mode
    state["subagent_plan"] = plan.to_dict()
    state["subagent_continue_recommended"] = plan.should_expand
    state["subagent_continue_reason"] = plan.rationale if plan.should_expand else plan.no_split_reason
    state["subagents"] = records
    state["subagent_last_event"] = {
        "timestamp": timestamp,
        "action": "spawn" if activate and created_ids else "plan",
        "summary": plan.rationale if plan.should_expand else plan.no_split_reason,
        "related_ids": created_ids,
    }
    save_machine_state(project, state, repo_root=repo_root)
    _append_event(
        paths,
        SubagentEvent(
            timestamp=timestamp,
            action="plan",
            project=project,
            subagent_id="plan",
            from_status=gate_mode,
            to_status=plan.recommended_gate,
            summary=plan.rationale if plan.should_expand else plan.no_split_reason,
            subagent_type="infrastructure",
            blocker_scope=profile.task_summary,
            decision_impact="决定是否需要为研究任务拆出基础设施型子代理。",
            related_ids=created_ids,
        ),
    )
    return {
        "plan": plan.to_dict(),
        "created_ids": created_ids,
        "registry_path": str(paths.subagent_registry_path),
        "ledger_path": str(paths.subagent_ledger_path),
    }


def register_worker_subagent(
    *,
    project: str,
    role: str,
    summary: str,
    mission_id: str,
    branch_id: str,
    candidate_id: str,
    worker_task_id: str,
    expected_artifacts: list[str],
    allowed_paths: list[str],
    requested_by_subagent_id: str | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    if requested_by_subagent_id:
        raise ValueError("Recursive subagent spawning is prohibited.")

    paths, state = load_machine_state(project, repo_root=repo_root)
    policy = load_subagent_policy(_policy_path(paths.root))
    records = list(state.get("subagents", []))
    if _active_subagent_count(records) >= _hard_limit(policy):
        raise ValueError(f"Subagent hard limit exceeded: {_hard_limit(policy)}")

    subagent_id = _next_subagent_id(records)
    artifact_dir = ensure_subagent_runtime_dir(paths, subagent_id)
    timestamp = _utc_now()
    lineage_root = hashlib.sha1(f"{mission_id}|{branch_id}|{candidate_id}".encode("utf-8")).hexdigest()[:12]
    record = SubagentRecord(
        subagent_id=subagent_id,
        role=role,
        summary=summary,
        status="active",
        transient=True,
        allowed_paths=list(allowed_paths),
        expected_artifacts=list(expected_artifacts),
        artifact_dir=str(artifact_dir),
        subagent_type="research",
        strategy_id=branch_id,
        research_focus=summary,
        decision_impact=f"服务策略 `{branch_id}` 的研究推进；最终是否继续由主代理统一决策。",
        mission_id=mission_id,
        branch_id=branch_id,
        candidate_id=candidate_id,
        worker_task_id=worker_task_id,
        lineage_root_id=f"lineage-{lineage_root}",
        spawn_depth=0,
        created_at=timestamp,
        updated_at=timestamp,
        last_action="spawn_worker",
        last_note=summary,
    )
    records.append(record.to_dict())
    state["subagents"] = records
    state["subagent_last_event"] = {
        "timestamp": timestamp,
        "action": "spawn_worker",
        "summary": summary,
        "related_ids": [subagent_id],
    }
    save_machine_state(project, state, repo_root=repo_root)
    _append_event(
        paths,
        SubagentEvent(
            timestamp=timestamp,
            action="spawn_worker",
            project=project,
            subagent_id=subagent_id,
            from_status="none",
            to_status="active",
            summary=summary,
            subagent_type=record.subagent_type,
            strategy_id=record.strategy_id,
            decision_impact=record.decision_impact,
            related_ids=[worker_task_id, branch_id],
            artifact_refs=[str(artifact_dir)],
        ),
    )
    return {
        "subagent_id": subagent_id,
        "artifact_dir": str(artifact_dir),
        "registry_path": str(paths.subagent_registry_path),
    }


def reconcile_loop_subagents(
    *,
    project: str,
    desired_roles: list[str],
    should_expand: bool,
    summary: str,
    repo_root: Path | None = None,
    close_status_if_unused: str = "retired",
    state_override: dict[str, Any] | None = None,
    paths_override: Any | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    if paths_override is not None and state_override is not None:
        paths = paths_override
        state = state_override
    else:
        paths, state = load_machine_state(project, repo_root=repo_root)
    policy = load_subagent_policy(_policy_path(paths.root))
    role_templates = load_subagent_roles(_roles_path(paths.root))
    records = [dict(item) for item in state.get("subagents", [])]
    timestamp = _utc_now()

    desired = list(desired_roles if should_expand else [])
    desired_counts: dict[str, int] = {}
    for role in desired:
        desired_counts[role] = desired_counts.get(role, 0) + 1

    created_ids: list[str] = []
    created_roles: list[str] = []
    auto_closed: list[dict[str, str]] = []
    replacement_ids: list[str] = []
    canceled_ids: list[str] = []

    def _close_record(item: dict[str, Any], *, to_status: str, note: str) -> dict[str, Any]:
        previous = str(item.get("status", "unknown"))
        item["status"] = to_status
        item["updated_at"] = timestamp
        item["last_action"] = "relevance_review"
        item["last_note"] = note
        auto_closed.append(
            {
                "subagent_id": str(item.get("subagent_id", "")),
                "role": str(item.get("role", "")),
                "status": to_status,
                "summary": note,
            },
        )
        if to_status == "canceled":
            canceled_ids.append(str(item.get("subagent_id", "")))
        _append_event(
            paths,
            SubagentEvent(
                timestamp=timestamp,
                action="relevance_review",
                project=project,
                subagent_id=str(item.get("subagent_id", "")),
                from_status=previous,
                to_status=to_status,
                summary=note,
                subagent_type=str(item.get("subagent_type", "infrastructure")),
                strategy_id=str(item.get("strategy_id", "")).strip() or None,
                blocker_scope=str(item.get("blocker_scope", "")).strip() or None,
                decision_impact=str(item.get("decision_impact", "")).strip() or None,
            ),
        )
        return item

    for index, record in enumerate(records):
        if record.get("status") != "active":
            continue
        role = str(record.get("role", ""))
        if not should_expand:
            note = "Auto-retired by iterative relevance review because the task no longer owns an independent work package."
            if close_status_if_unused == "archived":
                note = "Auto-archived by iterative relevance review because the run is stopping and the task should not remain active."
            records[index] = _close_record(record, to_status=close_status_if_unused, note=note)
            continue
        if desired_counts.get(role, 0) > 0:
            desired_counts[role] -= 1
            continue
        note = "Auto-canceled by iterative relevance review because the current direction superseded the old work package."
        records[index] = _close_record(record, to_status="canceled", note=note)

    remaining_slots = _hard_limit(policy) - _active_subagent_count(records)
    parent_ids = list(canceled_ids)
    new_ids_by_parent: list[str] = []
    for role in desired:
        if desired_counts.get(role, 0) <= 0:
            continue
        template = role_templates.get(role)
        if template is None or remaining_slots <= 0:
            continue
        subagent_id = _next_subagent_id(records)
        artifact_dir = ensure_subagent_runtime_dir(paths, subagent_id)
        record = SubagentRecord(
            subagent_id=subagent_id,
            role=role,
            summary=f"{role}: {summary}",
            status="active",
            transient=role != "memory_curator",
            allowed_paths=list(template.allowed_paths),
            expected_artifacts=list(template.expected_artifacts),
            artifact_dir=str(artifact_dir),
            subagent_type="infrastructure",
            blocker_scope=summary,
            research_focus=f"{role}: {summary}",
            decision_impact="为研究创造输入、验证或记忆前提；不是直接研究某条策略。",
            parent_ids=parent_ids,
            created_at=timestamp,
            updated_at=timestamp,
            last_action="loop_spawn",
            last_note="Loop spawned a replacement subagent for the current bounded work package." if parent_ids else summary,
        )
        records.append(record.to_dict())
        created_ids.append(subagent_id)
        created_roles.append(role)
        desired_counts[role] -= 1
        remaining_slots -= 1
        if parent_ids:
            replacement_ids.append(subagent_id)
        new_ids_by_parent.append(subagent_id)
        _append_event(
            paths,
            SubagentEvent(
                timestamp=timestamp,
                action="loop_spawn",
                project=project,
                subagent_id=subagent_id,
                from_status="none",
                to_status="active",
                summary=summary,
                subagent_type=record.subagent_type,
                blocker_scope=record.blocker_scope,
                decision_impact=record.decision_impact,
                related_ids=parent_ids,
                artifact_refs=[str(artifact_dir)],
            ),
        )

    if parent_ids and new_ids_by_parent:
        updated_records: list[dict[str, Any]] = []
        for record in records:
            item = dict(record)
            if item.get("subagent_id") in parent_ids:
                children = list(item.get("child_ids", []))
                for new_id in new_ids_by_parent:
                    if new_id not in children:
                        children.append(new_id)
                item["child_ids"] = children
            updated_records.append(item)
        records = updated_records

    state["subagents"] = records
    state["subagent_continue_recommended"] = bool(should_expand)
    state["subagent_continue_reason"] = summary
    state["subagent_last_event"] = {
        "timestamp": timestamp,
        "action": "iterative_relevance_review",
        "summary": summary,
        "related_ids": [*created_ids, *[item["subagent_id"] for item in auto_closed]],
    }
    if persist:
        save_machine_state(project, state, repo_root=repo_root)
    return {
        "created_ids": created_ids,
        "created_roles": created_roles,
        "auto_closed": auto_closed,
        "replacement_ids": replacement_ids,
        "registry_path": str(paths.subagent_registry_path),
    }


def sync_subagent_memory(project: str, *, repo_root: Path | None = None) -> dict[str, Any]:
    paths, state = load_machine_state(project, repo_root=repo_root)
    save_machine_state(project, state, repo_root=repo_root)
    summary = _summary_for_state(state)
    return {
        "registry_path": str(paths.subagent_registry_path),
        "ledger_path": str(paths.subagent_ledger_path),
        "gate_mode": state.get("subagent_gate_mode", "AUTO"),
        "active_ids": summary["active_ids"],
        "blocked_ids": summary["blocked_ids"],
    }


def _transition_subagent(
    *,
    project: str,
    subagent_id: str,
    to_status: str,
    action: str,
    summary: str,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    paths, state = load_machine_state(project, repo_root=repo_root)
    timestamp = _utc_now()
    records = list(state.get("subagents", []))
    updated: list[dict[str, Any]] = []
    found = None
    from_status = "unknown"
    for record in records:
        item = dict(record)
        if item.get("subagent_id") == subagent_id:
            from_status = str(item.get("status", "unknown"))
            item["status"] = to_status
            item["updated_at"] = timestamp
            item["last_action"] = action
            item["last_note"] = summary
            found = item
        updated.append(item)
    if found is None:
        raise ValueError(f"Unknown subagent id: {subagent_id}")
    state["subagents"] = updated
    state["subagent_last_event"] = {
        "timestamp": timestamp,
        "action": action,
        "summary": summary,
        "related_ids": [subagent_id],
    }
    save_machine_state(project, state, repo_root=repo_root)
    _append_event(
        paths,
        SubagentEvent(
            timestamp=timestamp,
            action=action,
            project=project,
            subagent_id=subagent_id,
            from_status=from_status,
            to_status=to_status,
            summary=summary,
            subagent_type=str(found.get("subagent_type", "infrastructure")),
            strategy_id=str(found.get("strategy_id", "")).strip() or None,
            blocker_scope=str(found.get("blocker_scope", "")).strip() or None,
            decision_impact=str(found.get("decision_impact", "")).strip() or None,
        ),
    )
    return {
        "subagent_id": subagent_id,
        "status": to_status,
        "registry_path": str(paths.subagent_registry_path),
    }


def retire_subagent(project: str, *, subagent_id: str, summary: str, repo_root: Path | None = None) -> dict[str, Any]:
    return _transition_subagent(
        project=project,
        subagent_id=subagent_id,
        to_status="retired",
        action="retire",
        summary=summary,
        repo_root=repo_root,
    )


def block_subagent(project: str, *, subagent_id: str, summary: str, repo_root: Path | None = None) -> dict[str, Any]:
    return _transition_subagent(
        project=project,
        subagent_id=subagent_id,
        to_status="blocked",
        action="block",
        summary=summary,
        repo_root=repo_root,
    )


def cancel_subagent(project: str, *, subagent_id: str, summary: str, repo_root: Path | None = None) -> dict[str, Any]:
    return _transition_subagent(
        project=project,
        subagent_id=subagent_id,
        to_status="canceled",
        action="cancel",
        summary=summary,
        repo_root=repo_root,
    )


def archive_subagent(project: str, *, subagent_id: str, summary: str, repo_root: Path | None = None) -> dict[str, Any]:
    return _transition_subagent(
        project=project,
        subagent_id=subagent_id,
        to_status="archived",
        action="archive",
        summary=summary,
        repo_root=repo_root,
    )


def refactor_subagent(project: str, *, subagent_id: str, summary: str, repo_root: Path | None = None) -> dict[str, Any]:
    return _transition_subagent(
        project=project,
        subagent_id=subagent_id,
        to_status="refactored",
        action="refactor",
        summary=summary,
        repo_root=repo_root,
    )


def merge_subagent(
    project: str,
    *,
    subagent_id: str,
    into_subagent_id: str,
    summary: str,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    paths, state = load_machine_state(project, repo_root=repo_root)
    timestamp = _utc_now()
    records = list(state.get("subagents", []))
    source = None
    target = None
    for record in records:
        if record.get("subagent_id") == subagent_id:
            source = record
        if record.get("subagent_id") == into_subagent_id:
            target = record
    if source is None or target is None:
        raise ValueError("merge requires both source and target subagents")

    merged_source, merged_target = apply_merge_transition(
        source=source,
        target=target,
        summary=summary,
        timestamp=timestamp,
    )
    updated: list[dict[str, Any]] = []
    for record in records:
        if record.get("subagent_id") == subagent_id:
            updated.append(merged_source)
        elif record.get("subagent_id") == into_subagent_id:
            updated.append(merged_target)
        else:
            updated.append(record)
    state["subagents"] = updated
    state["subagent_last_event"] = {
        "timestamp": timestamp,
        "action": "merge",
        "summary": summary,
        "related_ids": [subagent_id, into_subagent_id],
    }
    save_machine_state(project, state, repo_root=repo_root)
    _append_event(
        paths,
        SubagentEvent(
            timestamp=timestamp,
            action="merge",
            project=project,
            subagent_id=subagent_id,
            from_status=str(source.get("status", "unknown")),
            to_status="merged",
            summary=summary,
            subagent_type=str(source.get("subagent_type", "infrastructure")),
            strategy_id=str(source.get("strategy_id", "")).strip() or None,
            blocker_scope=str(source.get("blocker_scope", "")).strip() or None,
            decision_impact=str(source.get("decision_impact", "")).strip() or None,
            related_ids=[into_subagent_id],
        ),
    )
    return {
        "subagent_id": subagent_id,
        "merged_into": into_subagent_id,
        "registry_path": str(paths.subagent_registry_path),
    }
