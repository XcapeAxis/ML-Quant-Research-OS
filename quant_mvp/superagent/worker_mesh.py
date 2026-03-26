from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..agent.subagent_controller import block_subagent, register_worker_subagent, retire_subagent
from ..experiment_graph import Experiment, SubagentTask, update_experiment, write_experiment_record
from ..project import resolve_project_paths
from .models import ResearchBranch, WorkerTask


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _write_markdown(path: Path, lines: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path


def _artifact_report_path(artifact_dir: Path, role: str) -> Path:
    return artifact_dir / f"{role.upper()}_REPORT.md"


def _write_scout_report(
    *,
    report_path: Path,
    branch: ResearchBranch,
    branch_snapshot_path: Path,
    branch_pool_size: int,
) -> Path:
    return _write_markdown(
        report_path,
        [
            "# Scout Report",
            "",
            f"- branch_id: {branch.branch_id}",
            f"- mission_id: {branch.mission_id}",
            f"- candidate_id: {branch.strategy_candidate.candidate_id if branch.strategy_candidate else 'unknown'}",
            f"- branch_pool_snapshot_id: {branch.branch_pool_snapshot_id or 'unknown'}",
            f"- branch_pool_snapshot_path: {branch_snapshot_path}",
            f"- branch_pool_size: {branch_pool_size}",
            "- stop_condition: Candidate pool and evidence map were written; verification stays deferred.",
        ],
    )


def _write_implementer_report(
    *,
    report_path: Path,
    branch: ResearchBranch,
    experiment_id: str,
    experiment_path: Path,
) -> Path:
    return _write_markdown(
        report_path,
        [
            "# Implementer Report",
            "",
            f"- branch_id: {branch.branch_id}",
            f"- mission_id: {branch.mission_id}",
            f"- candidate_id: {branch.strategy_candidate.candidate_id if branch.strategy_candidate else 'unknown'}",
            f"- experiment_id: {experiment_id}",
            f"- experiment_record_path: {experiment_path}",
            "- stop_condition: Experiment record was refreshed with branch lineage and worker-mesh execution state.",
        ],
    )


def _task_to_subagent_task(task: WorkerTask) -> SubagentTask:
    return SubagentTask(
        subagent_id=task.subagent_id or "",
        role=task.role,
        status=task.state,
        summary=task.result_summary or task.summary,
    )


def execute_worker_mesh(
    *,
    project: str,
    branch: ResearchBranch,
    worker_tasks: list[WorkerTask],
    branch_snapshot_path: Path,
    branch_pool_size: int,
    experiment: Experiment,
    experiment_path: Path,
    dry_run: bool,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    paths = resolve_project_paths(project, root=repo_root)
    executed_tasks: list[WorkerTask] = []
    experiment_artifacts: list[str] = [str(branch_snapshot_path), str(experiment_path)]
    executed_roles: list[str] = []
    queued_roles: list[str] = []

    for task in worker_tasks:
        if task.role == "verifier":
            queued_roles.append(task.role)
            executed_tasks.append(
                replace(
                    task,
                    result_summary="Verifier is intentionally still queued until one branch is chosen for a bounded strategy check.",
                ),
            )
            continue

        subagent = register_worker_subagent(
            project=project,
            role=task.role,
            summary=task.summary,
            mission_id=task.mission_id,
            branch_id=task.branch_id,
            candidate_id=task.candidate_id,
            worker_task_id=task.task_id,
            expected_artifacts=list(task.expected_artifacts),
            allowed_paths=[
                str(paths.branch_pools_dir),
                str(paths.experiments_dir),
                str(paths.subagent_artifacts_dir),
            ],
            repo_root=repo_root,
        )
        artifact_dir = Path(str(subagent["artifact_dir"]))
        report_path = _artifact_report_path(artifact_dir, task.role)
        started_at = _utc_now()
        try:
            if task.role == "scout":
                report_path = _write_scout_report(
                    report_path=report_path,
                    branch=branch,
                    branch_snapshot_path=branch_snapshot_path,
                    branch_pool_size=branch_pool_size,
                )
                result_summary = (
                    f"Scout wrote a branch-pool evidence report for {branch.branch_id} with {branch_pool_size} candidate codes."
                )
                artifact_refs = [str(branch_snapshot_path), str(report_path)]
            elif task.role == "implementer":
                report_path = _write_implementer_report(
                    report_path=report_path,
                    branch=branch,
                    experiment_id=experiment.experiment_id,
                    experiment_path=experiment_path,
                )
                result_summary = (
                    f"Implementer refreshed the experiment record for {branch.branch_id} and linked it to the worker mesh."
                )
                artifact_refs = [str(experiment_path), str(report_path)]
            else:
                artifact_refs = [str(report_path)]
                result_summary = f"Unsupported worker role: {task.role}"
            retire_subagent(
                project,
                subagent_id=str(subagent["subagent_id"]),
                summary=result_summary,
                repo_root=repo_root,
            )
        except Exception as exc:
            block_subagent(
                project,
                subagent_id=str(subagent["subagent_id"]),
                summary=f"Worker mesh failed while running {task.role}: {exc}",
                repo_root=repo_root,
            )
            raise

        finished_at = _utc_now()
        executed_roles.append(task.role)
        experiment_artifacts.extend(artifact_refs)
        executed_tasks.append(
            replace(
                task,
                state="verified",
                subagent_id=str(subagent["subagent_id"]),
                artifact_refs=list(dict.fromkeys(artifact_refs)),
                result_summary=result_summary,
                started_at=started_at,
                finished_at=finished_at,
            ),
        )

    execution = {
        "mode": "worker_mesh_dry_run" if dry_run else "worker_mesh",
        "executed_steps": ["core_pool_snapshot", "branch_pool_snapshot"],
        "outputs": {
            "core_pool_snapshot": {
                "snapshot_id": branch.core_universe_snapshot_id or "",
            },
            "branch_pool_snapshot": {
                "snapshot_id": branch.branch_pool_snapshot_id or "",
                "snapshot_path": str(branch_snapshot_path),
                "branch_pool_size": branch_pool_size,
            },
            "compatibility_eval": {
                "planned": True,
                "reason": "Verifier task stays queued until one bounded branch is selected.",
            },
            "worker_mesh": {
                "executed_roles": executed_roles,
                "queued_roles": queued_roles,
                "subagent_registry_path": str(paths.subagent_registry_path),
                "subagent_ledger_path": str(paths.subagent_ledger_path),
                "artifact_refs": sorted(dict.fromkeys(experiment_artifacts)),
            },
        },
    }
    updated_experiment = update_experiment(
        experiment,
        status="evidence_pending",
        execution=execution,
        subagent_tasks=[_task_to_subagent_task(task) for task in executed_tasks],
        artifact_refs=experiment_artifacts,
    )
    updated_path = write_experiment_record(updated_experiment, repo_root=repo_root)
    return {
        "worker_tasks": executed_tasks,
        "experiment": updated_experiment,
        "experiment_path": str(updated_path),
        "executed_roles": executed_roles,
        "queued_roles": queued_roles,
    }
