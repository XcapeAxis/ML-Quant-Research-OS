from __future__ import annotations

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
    max_seq = 0
    for record in records:
        raw = str(record.get("subagent_id", ""))
        if raw.startswith("sa-"):
            try:
                max_seq = max(max_seq, int(raw.split("-", 1)[1]))
            except Exception:
                continue
    return f"sa-{max_seq + 1:03d}"


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
            related_ids=created_ids,
        ),
    )
    return {
        "plan": plan.to_dict(),
        "created_ids": created_ids,
        "registry_path": str(paths.subagent_registry_path),
        "ledger_path": str(paths.subagent_ledger_path),
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
            related_ids=[into_subagent_id],
        ),
    )
    return {
        "subagent_id": subagent_id,
        "merged_into": into_subagent_id,
        "registry_path": str(paths.subagent_registry_path),
    }
