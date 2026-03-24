from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ..config import load_config
from ..memory.ledger import stable_hash
from ..memory.writeback import bootstrap_memory_files, record_agent_cycle, record_failure, update_hypothesis_queue
from ..project import resolve_project_paths
from ..research_core import build_limit_up_rank_artifacts, run_limit_up_backtest_artifacts
from ..universe import load_universe_codes
from ..llm.dry_run import DryRunLLM
from ..llm.openai_compatible import OpenAICompatibleLLM
from .evaluator import evaluate_execution
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
        rank_artifacts = build_limit_up_rank_artifacts(cfg=cfg, paths=paths, universe_codes=universe)
        backtest_artifacts = run_limit_up_backtest_artifacts(
            cfg=cfg,
            paths=paths,
            rank_df=rank_artifacts.selection.rank_df,
            save="none" if dry_run else "auto",
            no_show=True,
        )
        evaluation = evaluate_execution(
            project=project,
            cfg=cfg,
            universe_codes=universe,
            rank_df=rank_artifacts.selection.rank_df,
            close_panel=backtest_artifacts.close_panel,
            volume_panel=backtest_artifacts.volume_panel,
            metrics_df=backtest_artifacts.metrics_df,
            hypothesis=plan.primary_hypothesis,
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
        },
    )
    record_paths = record_agent_cycle(project, cycle.to_dict(), repo_root=repo_root)
    if not evaluation.passed:
        record_failure(
            project,
            {
                "timestamp": timestamp,
                "experiment_id": cycle.cycle_id,
                "summary": evaluation.summary,
                "root_cause": "; ".join(cycle.evaluation.get("promotion_decision", {}).get("reasons", [])),
                "corrective_action": "Restore a usable frozen universe plus local bars before rerunning the dry-run cycle.",
            },
            repo_root=repo_root,
        )
    payload = cycle.to_dict()
    payload["record_paths"] = {key: str(value) for key, value in record_paths.items()}
    return payload
