from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..config import load_config
from ..data.validation import validate_project_data
from ..experiment_graph import (
    build_dataset_snapshot,
    build_opportunity_spec,
    build_universe_snapshot,
    new_experiment,
    write_experiment_record,
)
from ..memory.writeback import bootstrap_memory_files, load_machine_state, record_strategy_action, save_machine_state, update_hypothesis_queue
from ..pools import build_branch_pool_snapshot, build_core_universe_snapshot, load_latest_core_pool_snapshot
from ..project import resolve_project_paths
from ..project_identity import canonical_project_id
from .models import BranchBudget, BranchPriority, ResearchBranch, StrategyCandidate, WorkerTask
from .storage import (
    append_branch_states,
    append_worker_evidence,
    latest_branch_states,
    load_or_create_mission_state,
    save_mission_state,
    write_portfolio_status,
)
from .worker_mesh import execute_worker_mesh


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _tick_token() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _branch_templates(max_branches: int, *, legacy_single_branch: bool) -> list[dict[str, Any]]:
    if legacy_single_branch:
        return [
            {
                "branch_id": "legacy_single_branch",
                "title": "Legacy Single Branch",
                "objective": "Keep the old agent_cycle alive while routing it through the new mission control plane.",
                "hypothesis": "Route one controlled branch through mission orchestration before adding a real worker mesh.",
                "notes": ["legacy_compatibility_mode"],
                "params": {"variant": "legacy_single_branch"},
            },
        ]
    templates = [
        {
            "branch_id": "baseline_limit_up",
            "title": "Baseline Limit-Up",
            "objective": "Keep the current idea as the baseline branch on the new control plane.",
            "hypothesis": "Maintain a baseline branch so later challengers have a stable comparison point.",
            "notes": ["baseline_branch"],
            "params": {"variant": "baseline"},
        },
        {
            "branch_id": "risk_constrained_limit_up",
            "title": "Risk-Constrained Limit-Up",
            "objective": "Challenge the current strategy with tighter risk constraints before broad tuning.",
            "hypothesis": "A risk-constrained branch can cut drawdown without destroying the core opportunity definition.",
            "notes": ["risk_branch"],
            "params": {"variant": "risk_constrained"},
        },
        {
            "branch_id": "tighter_entry_limit_up",
            "title": "Tighter Entry Limit-Up",
            "objective": "Test whether narrowing the entry pool improves candidate quality.",
            "hypothesis": "A tighter entry branch can keep the same idea while avoiding weak candidates entering too early.",
            "notes": ["entry_branch"],
            "params": {"variant": "tighter_entry"},
        },
    ]
    return templates[: max(1, int(max_branches))]


def _mission_checkpoints(existing: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    by_label: dict[str, dict[str, Any]] = {}
    for item in existing or []:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label", "")).strip()
        if label:
            by_label[label] = dict(item)
    by_label["slice1"] = {
        "label": "slice1",
        "status": "complete",
        "note": "Mission orchestrator, branch graph, and dual-pool market plane",
    }
    by_label["slice2"] = {
        "label": "slice2",
        "status": "active",
        "note": "Scout and implementer worker tasks now run with auditable artifacts; verifier remains gated.",
    }
    ordered = [by_label.pop("slice1"), by_label.pop("slice2")]
    ordered.extend(by_label.values())
    return ordered


def _strategy_candidate(branch_id: str, cfg: dict[str, Any], params: dict[str, Any]) -> StrategyCandidate:
    return StrategyCandidate(
        candidate_id=f"candidate::{branch_id}",
        branch_id=branch_id,
        name=f"{branch_id}-candidate",
        strategy_mode=str(cfg.get("strategy_mode", "limit_up_screening")),
        params=dict(params),
    )


def _worker_tasks(mission_id: str, branch_id: str, candidate_id: str, experiment_id: str) -> list[WorkerTask]:
    roles = [
        ("scout", ["branch_pool_snapshot", "candidate_notes"], "Stop after the candidate pool and evidence map are written."),
        ("implementer", [experiment_id], "Stop after the planned experiment record is refreshed."),
        ("verifier", ["strategy_failure_report", "promotion_gate"], "Stop after the branch is ready for one controlled verification."),
    ]
    tasks: list[WorkerTask] = []
    for index, (role, artifacts, stop_condition) in enumerate(roles, start=1):
        tasks.append(
            WorkerTask(
                task_id=f"{branch_id}-{role}-{index}-{_tick_token()}",
                mission_id=mission_id,
                branch_id=branch_id,
                candidate_id=candidate_id,
                role=role,
                state="queued",
                expected_artifacts=list(artifacts),
                stop_condition=stop_condition,
                summary=f"{role} task for {branch_id}",
            ),
        )
    return tasks


def mission_tick(
    *,
    project: str,
    dry_run: bool = False,
    max_branches: int = 3,
    repo_root: Path | None = None,
    config_path: Path | None = None,
    legacy_single_branch: bool = False,
    seed_hypothesis: str | None = None,
) -> dict[str, Any]:
    project = canonical_project_id(project)
    bootstrap_memory_files(project, repo_root=repo_root)
    cfg, paths = load_config(project, config_path=config_path)
    paths.ensure_dirs()
    _, mission_state = load_or_create_mission_state(project, max_branches=max_branches, repo_root=repo_root)
    mission_id = str(mission_state.get("mission_id", "")).strip() or f"mission-{project}"
    if mission_id == "unknown":
        mission_id = f"mission-{project}"
    tick_token = _tick_token()

    core_snapshot = load_latest_core_pool_snapshot(project, repo_root=repo_root, build_if_missing=False, config_path=config_path)
    if core_snapshot is None:
        core_result = build_core_universe_snapshot(
            project=project,
            config_path=config_path,
            repo_root=repo_root,
            as_of_date=cfg.get("end_date"),
        )
        core_snapshot = core_result.snapshot
        core_snapshot_path = core_result.path
    else:
        core_snapshot_path = paths.pools_dir / "latest_core_pool.json"

    validation_report = validate_project_data(
        project=project,
        db_path=Path(str(cfg["db_path"])),
        freq=str(cfg["freq"]),
        universe_codes=list(core_snapshot.codes),
        provider_name=str(cfg.get("data_provider", {}).get("provider", "akshare")),
        data_quality_cfg=cfg.get("data_quality"),
        limit_threshold=float(cfg.get("limit_up_threshold", 0.095)),
    )
    universe_snapshot = build_universe_snapshot(codes=core_snapshot.codes, source_path=core_snapshot_path)
    dataset_snapshot = build_dataset_snapshot(report=validation_report.to_dict(), cfg=cfg, universe_snapshot=universe_snapshot)

    branch_templates = _branch_templates(max_branches, legacy_single_branch=legacy_single_branch)
    branches: list[ResearchBranch] = []
    proposals: list[dict[str, Any]] = []
    experiment_paths: list[str] = []
    worker_task_count = 0
    evidence_records: list[dict[str, Any]] = []

    for rank, template in enumerate(branch_templates, start=1):
        branch_result = build_branch_pool_snapshot(
            project=project,
            branch_id=template["branch_id"],
            hypothesis=seed_hypothesis or template["hypothesis"],
            config_path=config_path,
            repo_root=repo_root,
            core_snapshot=core_snapshot,
            as_of_date=cfg.get("end_date"),
        )
        branch_snapshot = branch_result.snapshot
        branch_snapshot_path = branch_result.path
        candidate = _strategy_candidate(template["branch_id"], cfg, template["params"])
        experiment_id = f"{project}__{template['branch_id']}__{tick_token}"
        worker_tasks = _worker_tasks(mission_id, template["branch_id"], candidate.candidate_id, experiment_id)
        branch = ResearchBranch(
            branch_id=template["branch_id"],
            mission_id=mission_id,
            state="selected" if dry_run else "active",
            title=template["title"],
            objective=template["objective"],
            hypothesis=seed_hypothesis or template["hypothesis"],
            created_at=_utc_now(),
            updated_at=_utc_now(),
            budget=BranchBudget(experiment_slots=1),
            priority=BranchPriority(rank=rank, score=float(max(len(branch_templates) - rank + 1, 1))),
            core_universe_snapshot_id=core_snapshot.snapshot_id,
            branch_pool_snapshot_id=branch_snapshot.snapshot_id,
            opportunity_generator_id=branch_snapshot.spec.generator_id,
            strategy_candidate=candidate,
            experiment_id=experiment_id,
            stop_rules=["Do not widen the board scope.", "Do not skip readiness or promotion guards."],
            notes=list(template["notes"]),
        )
        experiment = new_experiment(
            project=project,
            experiment_id=experiment_id,
            hypothesis=branch.hypothesis,
            mode="mission_tick_dry_run" if dry_run else "mission_tick",
            plan_steps=["core_pool_snapshot", "branch_pool_snapshot", "compatibility_eval"],
            success_criteria=[
                "A core research pool and a branch-specific pool must both be recorded.",
                "The branch must emit one structured experiment proposal with lineage fields.",
            ],
            universe_snapshot=universe_snapshot,
            dataset_snapshot=dataset_snapshot,
            opportunity_spec=build_opportunity_spec(cfg=cfg, hypothesis=branch.hypothesis),
            subagent_tasks=[],
            mission_id=mission_id,
            branch_id=branch.branch_id,
            core_universe_snapshot_id=core_snapshot.snapshot_id,
            branch_pool_snapshot_id=branch_snapshot.snapshot_id,
            opportunity_generator_id=branch_snapshot.spec.generator_id,
            strategy_candidate_id=candidate.candidate_id,
        )
        experiment_path = write_experiment_record(experiment, repo_root=repo_root)
        worker_result = execute_worker_mesh(
            project=project,
            branch=branch,
            worker_tasks=worker_tasks,
            branch_snapshot_path=branch_snapshot_path,
            branch_pool_size=len(branch_snapshot.codes),
            experiment=experiment,
            experiment_path=experiment_path,
            dry_run=dry_run,
            repo_root=repo_root,
        )
        worker_tasks = list(worker_result["worker_tasks"])
        experiment_path = Path(str(worker_result["experiment_path"]))

        worker_task_count += len(worker_tasks)
        branches.append(branch)
        experiment_paths.append(str(experiment_path))
        proposals.append(
            {
                "branch_id": branch.branch_id,
                "experiment_id": experiment_id,
                "experiment_record_path": str(experiment_path),
                "core_pool_snapshot_id": core_snapshot.snapshot_id,
                "branch_pool_snapshot_id": branch_snapshot.snapshot_id,
                "strategy_candidate_id": candidate.candidate_id,
            },
        )
        append_worker_evidence(
            project,
            mission_id=mission_id,
            branch_id=branch.branch_id,
            experiment_id=experiment_id,
            core_snapshot_id=core_snapshot.snapshot_id,
            branch_pool_snapshot_id=branch_snapshot.snapshot_id,
            branch_pool_size=len(branch_snapshot.codes),
            worker_tasks=worker_tasks,
            experiment_record_path=str(experiment_path),
            repo_root=repo_root,
        )
        evidence_records.append(
            {
                "branch_id": branch.branch_id,
                "latest_experiment_id": experiment_id,
                "branch_pool_snapshot_path": str(branch_snapshot_path),
                "experiment_record_path": str(experiment_path),
                "worker_tasks": [task.to_dict() for task in worker_tasks],
                "executed_roles": list(worker_result["executed_roles"]),
                "queued_roles": list(worker_result["queued_roles"]),
            },
        )
        for task in worker_tasks:
            if task.state != "verified":
                continue
            record_strategy_action(
                project,
                {
                    "run_id": experiment_id,
                    "project_id": project,
                    "strategy_id": branch.branch_id,
                    "actor_type": "subagent",
                    "actor_id": task.subagent_id or task.role,
                    "action_type": task.role,
                    "action_summary": task.summary,
                    "result": task.result_summary or "未记录",
                    "decision_delta": "更新该策略分支的候选证据，但尚未形成 verifier 级结论。",
                    "artifact_refs": list(task.artifact_refs),
                    "timestamp": task.finished_at or task.started_at or _utc_now(),
                },
                repo_root=repo_root,
            )

    mission_payload = {
        "mission_id": mission_id,
        "project": project,
        "state": "active",
        "objective": "Run multi-branch research from a frozen core universe plus branch pools instead of a linear single-cycle control plane.",
        "created_at": mission_state.get("created_at", _utc_now()),
        "updated_at": _utc_now(),
        "budget": mission_state.get("budget") or {"max_branches": max_branches, "experiments_per_tick": 1},
        "constraints": mission_state.get("constraints")
        or {
            "research_scope": "A-share daily/weekly research only",
            "no_live_trading": True,
            "board_scope": "mainboard_a_share_only",
        },
        "checkpoints": _mission_checkpoints(mission_state.get("checkpoints")),
        "active_branch_ids": [branch.branch_id for branch in branches],
        "core_universe_snapshot_id": core_snapshot.snapshot_id,
        "core_universe_snapshot_path": str(core_snapshot_path),
        "core_pool_snapshot_id": core_snapshot.snapshot_id,
        "core_pool_snapshot_path": str(core_snapshot_path),
    }
    save_mission_state(project, mission_payload, repo_root=repo_root)
    append_branch_states(project, branches, repo_root=repo_root)
    write_portfolio_status(project, mission=mission_payload, branches=branches, repo_root=repo_root)

    _, machine_state = load_machine_state(project, repo_root=repo_root)
    machine_state.update(
        {
            "current_task": "Use mission_tick as the system center, run branch-bound scout and implementer workers with auditable artifacts, and keep verifier work gated until one bounded branch is selected.",
            "current_phase": "Architecture Slice 2 - worker mesh partial execution",
            "current_blocker": "Verifier work is still gated, benchmark or equal-weight baselines are still degraded, and the current strategy still fails on drawdown.",
            "current_capability_boundary": "The repo can now build a core research pool, branch-specific opportunity pools, formal experiment records, and real scout or implementer worker runs with auditable subagent artifacts; verifier execution, tool autonomy, and passing strategy selection are still missing.",
            "next_priority_action": "Repair degraded baselines, then choose one branch and run the first bounded verifier-backed experiment instead of broad parameter search.",
            "last_verified_capability": "mission_tick executed scout and implementer worker tasks, wrote auditable subagent artifacts, and kept verifier queued on purpose.",
            "last_failed_capability": machine_state.get("last_failed_capability", "none"),
            "current_mission_id": mission_id,
            "active_branch_ids": [branch.branch_id for branch in branches],
            "core_universe_snapshot_id": core_snapshot.snapshot_id,
            "core_universe_snapshot_path": str(core_snapshot_path),
            "superagent_state": {
                "mission_id": mission_id,
                "mission_state": "active",
                "active_branch_ids": [branch.branch_id for branch in branches],
                "core_universe_snapshot_id": core_snapshot.snapshot_id,
            },
        },
    )
    save_machine_state(project, machine_state, repo_root=repo_root)
    update_hypothesis_queue(
        project,
        [{"status": "active", "hypothesis": branch.hypothesis} for branch in branches],
        repo_root=repo_root,
    )

    return {
        "project": project,
        "mission_id": mission_id,
        "mission_state_path": str(paths.mission_state_path),
        "branch_ledger_path": str(paths.branch_ledger_path),
        "evidence_ledger_path": str(paths.evidence_ledger_path),
        "portfolio_status_path": str(paths.portfolio_status_path),
        "core_universe_snapshot_id": core_snapshot.snapshot_id,
        "core_universe_snapshot_path": str(core_snapshot_path),
        "core_pool_snapshot_id": core_snapshot.snapshot_id,
        "core_pool_snapshot_path": str(core_snapshot_path),
        "core_universe_size": len(core_snapshot.codes),
        "core_pool_size": len(core_snapshot.codes),
        "core_universe_codes": list(core_snapshot.codes),
        "core_codes": list(core_snapshot.codes),
        "branch_ids": [branch.branch_id for branch in branches],
        "branch_states": [branch.to_dict() for branch in branches],
        "branches": [{**branch.to_dict(), "latest_experiment_id": branch.experiment_id} for branch in branches],
        "proposals": proposals,
        "experiment_record_paths": experiment_paths,
        "worker_task_count": worker_task_count,
        "legacy_single_branch": legacy_single_branch,
        "evidence_records": evidence_records,
        "primary_branch_id": branches[0].branch_id if branches else "",
        "primary_experiment_id": branches[0].experiment_id if branches else "",
        "primary_experiment_record_path": experiment_paths[0] if experiment_paths else "",
        "validation_report": validation_report.to_dict(),
    }


def mission_status(
    *,
    project: str,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    paths, mission_state = load_or_create_mission_state(project, max_branches=3, repo_root=repo_root)
    return {
        "mission_state_path": str(paths.mission_state_path),
        "portfolio_status_path": str(paths.portfolio_status_path),
        "mission": mission_state,
        "mission_state": mission_state,
        "branches": list(latest_branch_states(project, repo_root=repo_root).values()),
    }


def branch_review(
    *,
    project: str,
    branch_id: str,
    action: str,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    action_map = {
        "keep": "active",
        "hold": "evidence_pending",
        "retire": "archived",
        "promote": "promoted_to_challenger",
    }
    if action not in action_map:
        raise ValueError(f"Unsupported branch review action: {action}")

    branches = latest_branch_states(project, repo_root=repo_root)
    if branch_id not in branches:
        raise ValueError(f"Unknown branch id: {branch_id}")
    payload = dict(branches[branch_id])
    payload["state"] = action_map[action]
    payload["updated_at"] = _utc_now()
    from ..memory.ledger import append_jsonl

    paths = resolve_project_paths(project, root=repo_root)
    append_jsonl(paths.branch_ledger_path, payload)
    return {
        "branch_id": branch_id,
        "action": action,
        "state": payload["state"],
        "branch_ledger_path": str(paths.branch_ledger_path),
    }
