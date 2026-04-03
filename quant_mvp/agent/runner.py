from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ..config import load_config
from ..memory.ledger import stable_hash
from ..memory.writeback import bootstrap_memory_files, load_machine_state, record_agent_cycle, record_failure, update_hypothesis_queue
from ..project import resolve_project_paths
from ..strategy_diagnostics import run_strategy_diagnostics
from ..universe import load_universe_codes
from ..llm.dry_run import DryRunLLM
from ..llm.openai_compatible import OpenAICompatibleLLM
from .executor import execute_plan
from .memory import load_memory_context
from .planner import build_plan
from .reflector import build_reflection
from .schemas import AgentCycleRecord, EvaluationRecord
from .tool_registry import load_tool_registry


def _resolve_backend(name: str):
    if name == "openai_compatible":
        return OpenAICompatibleLLM()
    return DryRunLLM()


def _corrective_action_for_root_cause(root_cause: str) -> str:
    lowered = str(root_cause or "").strip().lower()
    if "drawdown" in lowered or "最大回撤" in root_cause:
        return "Break down the current max-drawdown driver and compare one bounded challenger before rerunning the dry-run cycle."
    if any(token in lowered for token in ["validated bars", "coverage", "readiness", "frozen universe", "local bars"]):
        return "Restore the validated snapshot and rerun the dry-run cycle only after the data boundary is healthy again."
    return "Refresh the blocker diagnosis and narrow one bounded next step before rerunning the dry-run cycle."


def run_agent_cycle(
    *,
    project: str,
    dry_run: bool = False,
    repo_root: Path | None = None,
    config_path: Path | None = None,
) -> dict:
    bootstrap_memory_files(project, repo_root=repo_root)
    cfg, paths = load_config(project, config_path=config_path)
    backend_name = "dry_run" if dry_run else str(cfg.get("agent", {}).get("default_backend", "dry_run"))
    backend = _resolve_backend(backend_name)
    context = load_memory_context(project, repo_root=repo_root)
    hypotheses = backend.generate_hypotheses(project=project, context=context)
    plan = build_plan(
        hypothesis=hypotheses[0],
        backend_plan=backend.plan_experiment(project=project, hypotheses=hypotheses, context=context),
    )
    registry = load_tool_registry(resolve_project_paths(project, root=repo_root).root / cfg.get("agent", {}).get("default_tool_allowlist_path", "configs/tool_allowlist.yaml"))
    execution = execute_plan(
        project=project,
        plan=plan,
        registry=registry,
        repo_root=repo_root,
        config_path=config_path,
    )

    try:
        universe = load_universe_codes(project)
        diagnostics = run_strategy_diagnostics(
            project=project,
            cfg=cfg,
            paths=paths,
            universe_codes=universe,
            hypothesis=plan.primary_hypothesis,
        )
        decision = diagnostics["decision"]
        summary = (
            "Promotion gate passed in dry-run mode."
            if decision.get("promotable")
            else f"Promotion gate blocked: {'; '.join(decision.get('reasons', []))}"
        )
        evaluation = EvaluationRecord(
            passed=bool(decision.get("promotable")),
            summary=summary,
            promotion_decision=decision,
        )
    except Exception as exc:
        evaluation = EvaluationRecord(
            passed=False,
            summary=f"Dry-run blocked by missing research inputs: {exc}",
            promotion_decision={
                "promotable": False,
                "reasons": [f"missing_research_inputs: {exc}"],
                "checks": {},
            },
        )
    reflection = build_reflection(
        backend.reflect(project=project, evaluation=evaluation.to_dict(), context=context),
    )
    update_hypothesis_queue(project, reflection.next_hypotheses, repo_root=repo_root)

    timestamp = datetime.utcnow().replace(microsecond=0).isoformat()
    _, machine_state = load_machine_state(project, repo_root=repo_root)
    active_subagents = [
        item["subagent_id"]
        for item in machine_state.get("subagents", [])
        if item.get("status") == "active"
    ]
    cycle = AgentCycleRecord(
        cycle_id=f"{project}-{timestamp.replace(':', '').replace('-', '')}",
        timestamp=timestamp,
        backend=backend.backend_name,
        hypotheses=hypotheses,
        plan=plan.to_dict(),
        execution=execution.to_dict(),
        evaluation=evaluation.to_dict(),
        reflection=reflection.to_dict(),
        metadata={
            "dry_run": dry_run,
            "project": project,
            "meta_dir": str(paths.meta_dir),
            "tracked_memory_dir": str(paths.memory_dir),
            "config_hash": stable_hash(cfg),
            "subagent_gate_mode": machine_state.get("subagent_gate_mode", "AUTO"),
            "active_subagents": active_subagents,
        },
    )
    record_paths = record_agent_cycle(project, cycle.to_dict(), repo_root=repo_root)
    if not evaluation.passed:
        root_cause = "; ".join(cycle.evaluation.get("promotion_decision", {}).get("reasons", []))
        record_failure(
            project,
            {
                "timestamp": timestamp,
                "experiment_id": cycle.cycle_id,
                "summary": evaluation.summary,
                "root_cause": root_cause,
                "corrective_action": _corrective_action_for_root_cause(root_cause),
            },
            repo_root=repo_root,
        )
    payload = cycle.to_dict()
    payload["record_paths"] = {key: str(value) for key, value in record_paths.items()}
    return payload
