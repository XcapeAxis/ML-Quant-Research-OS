from __future__ import annotations

from pathlib import Path
from typing import Any

from ..memory.writeback import load_machine_state, sync_project_state
from ..project import resolve_project_paths
from ..research_audit import run_research_audit
from .schemas import ExecutionRecord, ExperimentPlan
from .tool_registry import ToolRegistry


def execute_plan(
    *,
    project: str,
    plan: ExperimentPlan,
    registry: ToolRegistry,
    repo_root: Path | None = None,
    config_path: Path | None = None,
) -> ExecutionRecord:
    outputs: dict[str, Any] = {}
    executed_steps: list[str] = []
    for step in plan.steps:
        if not registry.is_allowed(step):
            outputs[step] = {"skipped": True, "reason": "not on allowlist"}
            continue
        if step == "research_audit":
            audit = run_research_audit(project=project, repo_root=repo_root, config_path=config_path)
            outputs[step] = audit
            executed_steps.append(step)
        elif step == "agent_memory_sync":
            project_paths = resolve_project_paths(project, root=repo_root)
            _, machine_state = load_machine_state(project, repo_root=repo_root)
            state_path = sync_project_state(
                project,
                {
                    "current_phase": "Phase 1 Research OS",
                    "current_task": "Keep the Phase 1 Research OS reproducible with tracked memory and honest runtime artifacts.",
                    "current_blocker": machine_state.get("current_blocker") or "none",
                    "current_capability_boundary": machine_state.get("current_capability_boundary")
                    or "Tracked memory sync refreshed the current state only; it did not change the canonical blocker.",
                    "next_priority_action": machine_state.get("next_priority_action")
                    or "Keep the current blocker diagnosis aligned across session_state and verifier artifacts.",
                    "last_verified_capability": f"Tracked memory sync refreshed for plan: {plan.primary_hypothesis}",
                },
                repo_root=repo_root,
            )
            outputs[step] = {
                "project_state_path": str(state_path),
                "memory_dir": str(project_paths.memory_dir),
            }
            executed_steps.append(step)
        elif step == "promote_candidate":
            outputs[step] = {
                "skipped": True,
                "reason": "Promotion gate runs in evaluator so agent execution cannot bypass it.",
            }
        else:
            outputs[step] = {"skipped": True, "reason": "unknown tool"}
    return ExecutionRecord(mode=plan.mode, executed_steps=executed_steps, outputs=outputs)
