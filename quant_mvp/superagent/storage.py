from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..memory.ledger import append_jsonl, to_jsonable
from ..project import resolve_project_paths
from .models import ResearchBranch, WorkerTask


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _read_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return dict(default or {})
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return dict(default or {})
    return json.loads(text)


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_jsonable(payload), ensure_ascii=False, indent=2).rstrip() + "\n", encoding="utf-8")
    return path


def default_mission_state(project: str, *, max_branches: int) -> dict[str, Any]:
    return {
        "mission_id": f"mission-{project}",
        "project": project,
        "state": "active",
        "objective": "Replace the linear control plane with a multi-branch research portfolio manager.",
        "created_at": _utc_now(),
        "updated_at": _utc_now(),
        "budget": {"max_branches": max_branches, "experiments_per_tick": 1},
        "constraints": {
            "research_scope": "A-share daily/weekly research only",
            "no_live_trading": True,
            "board_scope": "mainboard_a_share_only",
        },
        "checkpoints": [
            {"label": "slice1", "status": "active", "note": "Mission orchestrator, branch graph, and dual-pool market plane"},
        ],
        "active_branch_ids": [],
    }


def load_or_create_mission_state(project: str, *, max_branches: int, repo_root: Path | None = None) -> tuple[Any, dict[str, Any]]:
    paths = resolve_project_paths(project, root=repo_root)
    paths.ensure_dirs()
    default = default_mission_state(project, max_branches=max_branches)
    state = _read_json(paths.mission_state_path, default=default)
    mission_id = str(state.get("mission_id", "")).strip()
    if mission_id in {"", "unknown"}:
        state = {**default, **{key: value for key, value in state.items() if key != "mission_id"}}
        state["mission_id"] = default["mission_id"]
    if not paths.mission_state_path.exists():
        _write_json(paths.mission_state_path, state)
    return paths, state


def save_mission_state(project: str, state: dict[str, Any], *, repo_root: Path | None = None) -> Path:
    paths = resolve_project_paths(project, root=repo_root)
    payload = dict(state)
    payload["updated_at"] = _utc_now()
    return _write_json(paths.mission_state_path, payload)


def append_branch_states(project: str, branches: list[ResearchBranch], *, repo_root: Path | None = None) -> Path:
    paths = resolve_project_paths(project, root=repo_root)
    for branch in branches:
        append_jsonl(paths.branch_ledger_path, branch.to_dict())
    return paths.branch_ledger_path


def append_worker_evidence(
    project: str,
    *,
    mission_id: str,
    branch_id: str,
    experiment_id: str,
    core_snapshot_id: str,
    branch_pool_snapshot_id: str,
    branch_pool_size: int,
    worker_tasks: list[WorkerTask],
    experiment_record_path: str,
    repo_root: Path | None = None,
) -> Path:
    paths = resolve_project_paths(project, root=repo_root)
    payload = {
        "timestamp": _utc_now(),
        "mission_id": mission_id,
        "branch_id": branch_id,
        "experiment_id": experiment_id,
        "core_universe_snapshot_id": core_snapshot_id,
        "branch_pool_snapshot_id": branch_pool_snapshot_id,
        "branch_pool_size": branch_pool_size,
        "evidence_type": "worker_task_bundle",
        "worker_tasks": [task.to_dict() for task in worker_tasks],
        "experiment_record_path": experiment_record_path,
    }
    append_jsonl(paths.evidence_ledger_path, payload)
    return paths.evidence_ledger_path


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    items: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        try:
            items.append(json.loads(stripped))
        except json.JSONDecodeError:
            continue
    return items


def latest_branch_states(project: str, *, repo_root: Path | None = None) -> dict[str, dict[str, Any]]:
    paths = resolve_project_paths(project, root=repo_root)
    latest: dict[str, dict[str, Any]] = {}
    for payload in _load_jsonl(paths.branch_ledger_path):
        branch_id = str(payload.get("branch_id", "")).strip()
        if not branch_id:
            continue
        latest[branch_id] = payload
    return latest


def write_portfolio_status(
    project: str,
    *,
    mission: dict[str, Any],
    branches: list[ResearchBranch],
    repo_root: Path | None = None,
) -> Path:
    paths = resolve_project_paths(project, root=repo_root)
    lines = [
        "# Portfolio Status",
        "",
        f"- mission_id: {mission.get('mission_id', 'unknown')}",
        f"- mission_state: {mission.get('state', 'unknown')}",
        f"- active_branch_count: {len(branches)}",
        "",
        "## Active Branches",
    ]
    if not branches:
        lines.append("- none")
    else:
        for branch in branches:
            candidate = branch.strategy_candidate.candidate_id if branch.strategy_candidate else "none"
            lines.extend(
                [
                    f"- {branch.branch_id}: state={branch.state}, priority_rank={branch.priority.rank}, candidate={candidate}",
                    f"  objective: {branch.objective}",
                    f"  core_snapshot: {branch.core_universe_snapshot_id}",
                    f"  branch_pool: {branch.branch_pool_snapshot_id}",
                    f"  experiment_id: {branch.experiment_id}",
                ],
            )
    path = paths.portfolio_status_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path
