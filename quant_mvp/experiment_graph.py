from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from .memory.ledger import stable_hash, to_jsonable
from .project import resolve_project_paths


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _normalize_codes(codes: Iterable[str]) -> list[str]:
    return sorted({str(code).zfill(6) for code in codes if str(code).strip()})


@dataclass
class UniverseSnapshot:
    size: int
    codes: list[str]
    hash: str
    source_path: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DatasetSnapshot:
    frequency: str
    provider: str
    start_date: str | None
    end_date: str | None
    universe_hash: str
    report: dict[str, Any]
    hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FactorSpec:
    name: str
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class OpportunitySpec:
    strategy_mode: str
    hypothesis: str
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ToolSpec:
    name: str
    status: str
    reason: str = ""
    output_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SubagentTask:
    subagent_id: str
    role: str
    status: str
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvaluationRecord:
    status: str
    summary: str
    classification: str
    primary_blockers: list[str] = field(default_factory=list)
    promotion_decision: dict[str, Any] = field(default_factory=dict)
    strategy_failure_report_json: str | None = None
    strategy_failure_report_md: str | None = None
    next_experiment_themes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Experiment:
    experiment_id: str
    project: str
    created_at: str
    updated_at: str
    status: str
    hypothesis: str
    mode: str
    plan_steps: list[str]
    success_criteria: list[str]
    universe_snapshot: UniverseSnapshot
    dataset_snapshot: DatasetSnapshot
    factor_specs: list[FactorSpec] = field(default_factory=list)
    opportunity_spec: OpportunitySpec | None = None
    tool_specs: list[ToolSpec] = field(default_factory=list)
    subagent_tasks: list[SubagentTask] = field(default_factory=list)
    execution: dict[str, Any] = field(default_factory=dict)
    evaluation: EvaluationRecord | None = None
    related_cycle_id: str | None = None
    mission_id: str | None = None
    branch_id: str | None = None
    core_universe_snapshot_id: str | None = None
    branch_pool_snapshot_id: str | None = None
    opportunity_generator_id: str | None = None
    strategy_candidate_id: str | None = None
    artifact_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["universe_snapshot"] = self.universe_snapshot.to_dict()
        payload["dataset_snapshot"] = self.dataset_snapshot.to_dict()
        payload["factor_specs"] = [item.to_dict() for item in self.factor_specs]
        payload["opportunity_spec"] = self.opportunity_spec.to_dict() if self.opportunity_spec else None
        payload["tool_specs"] = [item.to_dict() for item in self.tool_specs]
        payload["subagent_tasks"] = [item.to_dict() for item in self.subagent_tasks]
        payload["evaluation"] = self.evaluation.to_dict() if self.evaluation else None
        return payload


def build_universe_snapshot(*, codes: Iterable[str], source_path: Path) -> UniverseSnapshot:
    normalized = _normalize_codes(codes)
    return UniverseSnapshot(
        size=len(normalized),
        codes=normalized,
        hash=stable_hash(normalized),
        source_path=str(source_path),
    )


def build_dataset_snapshot(
    *,
    report: Mapping[str, Any],
    cfg: Mapping[str, Any],
    universe_snapshot: UniverseSnapshot,
) -> DatasetSnapshot:
    frequency = str(cfg.get("freq", "1d"))
    provider = str(cfg.get("data_provider", {}).get("provider", "unknown"))
    start_date = str(cfg.get("start_date")) if cfg.get("start_date") else None
    end_date = str(cfg.get("end_date")) if cfg.get("end_date") else None
    hash_payload = {
        "validated_report": dict(report),
        "universe_hash": universe_snapshot.hash,
        "freq": frequency,
        "provider": provider,
        "start_date": start_date,
        "end_date": end_date,
    }
    return DatasetSnapshot(
        frequency=frequency,
        provider=provider,
        start_date=start_date,
        end_date=end_date,
        universe_hash=universe_snapshot.hash,
        report=dict(report),
        hash=stable_hash(hash_payload),
    )


def build_opportunity_spec(*, cfg: Mapping[str, Any], hypothesis: str) -> OpportunitySpec:
    strategy_mode = str(cfg.get("strategy_mode", "limit_up_screening"))
    params = {
        "lookback": cfg.get("lookback"),
        "rebalance_every": cfg.get("rebalance_every"),
        "topk": cfg.get("topk"),
        "topn_max": cfg.get("topn_max"),
        "limit_days_window": cfg.get("limit_days_window"),
        "top_pct_limit_up": cfg.get("top_pct_limit_up"),
    }
    compact_params = {key: value for key, value in params.items() if value is not None}
    return OpportunitySpec(strategy_mode=strategy_mode, hypothesis=hypothesis, params=compact_params)


def build_subagent_tasks(machine_state: Mapping[str, Any]) -> list[SubagentTask]:
    tasks: list[SubagentTask] = []
    for item in machine_state.get("subagents", []) if isinstance(machine_state, Mapping) else []:
        if not isinstance(item, Mapping):
            continue
        tasks.append(
            SubagentTask(
                subagent_id=str(item.get("subagent_id", "")),
                role=str(item.get("role", item.get("kind", "unknown"))),
                status=str(item.get("status", "unknown")),
                summary=str(item.get("summary", "")),
            ),
        )
    return tasks


def _extract_output_refs(value: Any) -> list[str]:
    refs: list[str] = []
    if isinstance(value, Mapping):
        for item in value.values():
            refs.extend(_extract_output_refs(item))
        return refs
    if isinstance(value, list):
        for item in value:
            refs.extend(_extract_output_refs(item))
        return refs
    if isinstance(value, Path):
        return [str(value)]
    if isinstance(value, str):
        text = value.strip()
        if (":" in text or "\\" in text or "/" in text) and len(text) > 3:
            refs.append(text)
    return refs


def build_tool_specs(*, planned_steps: list[str], execution: Mapping[str, Any] | None = None) -> list[ToolSpec]:
    execution = execution or {}
    executed_steps = set(execution.get("executed_steps", [])) if isinstance(execution, Mapping) else set()
    outputs = execution.get("outputs", {}) if isinstance(execution, Mapping) else {}
    specs: list[ToolSpec] = []
    for step in planned_steps:
        payload = outputs.get(step, {}) if isinstance(outputs, Mapping) else {}
        if step in executed_steps:
            status = "executed"
            reason = ""
        elif isinstance(payload, Mapping) and payload.get("skipped"):
            status = "skipped"
            reason = str(payload.get("reason", "skipped"))
        else:
            status = "planned"
            reason = ""
        output_refs = sorted(dict.fromkeys(_extract_output_refs(payload)))
        specs.append(ToolSpec(name=step, status=status, reason=reason, output_refs=output_refs))
    return specs


def new_experiment(
    *,
    project: str,
    experiment_id: str,
    hypothesis: str,
    mode: str,
    plan_steps: list[str],
    success_criteria: list[str],
    universe_snapshot: UniverseSnapshot,
    dataset_snapshot: DatasetSnapshot,
    opportunity_spec: OpportunitySpec,
    subagent_tasks: list[SubagentTask],
    mission_id: str | None = None,
    branch_id: str | None = None,
    core_universe_snapshot_id: str | None = None,
    branch_pool_snapshot_id: str | None = None,
    opportunity_generator_id: str | None = None,
    strategy_candidate_id: str | None = None,
) -> Experiment:
    now = _utc_now()
    return Experiment(
        experiment_id=experiment_id,
        project=project,
        created_at=now,
        updated_at=now,
        status="planned",
        hypothesis=hypothesis,
        mode=mode,
        plan_steps=list(plan_steps),
        success_criteria=list(success_criteria),
        universe_snapshot=universe_snapshot,
        dataset_snapshot=dataset_snapshot,
        factor_specs=[],
        opportunity_spec=opportunity_spec,
        tool_specs=build_tool_specs(planned_steps=plan_steps),
        subagent_tasks=list(subagent_tasks),
        mission_id=mission_id,
        branch_id=branch_id,
        core_universe_snapshot_id=core_universe_snapshot_id,
        branch_pool_snapshot_id=branch_pool_snapshot_id,
        opportunity_generator_id=opportunity_generator_id,
        strategy_candidate_id=strategy_candidate_id,
    )


def update_experiment(
    experiment: Experiment,
    *,
    status: str,
    execution: Mapping[str, Any] | None = None,
    evaluation: EvaluationRecord | None = None,
    subagent_tasks: list[SubagentTask] | None = None,
    artifact_refs: Iterable[str] | None = None,
    related_cycle_id: str | None = None,
) -> Experiment:
    refs = sorted(dict.fromkeys([*experiment.artifact_refs, *[str(item) for item in (artifact_refs or []) if str(item).strip()]]))
    return Experiment(
        experiment_id=experiment.experiment_id,
        project=experiment.project,
        created_at=experiment.created_at,
        updated_at=_utc_now(),
        status=status,
        hypothesis=experiment.hypothesis,
        mode=experiment.mode,
        plan_steps=list(experiment.plan_steps),
        success_criteria=list(experiment.success_criteria),
        universe_snapshot=experiment.universe_snapshot,
        dataset_snapshot=experiment.dataset_snapshot,
        factor_specs=list(experiment.factor_specs),
        opportunity_spec=experiment.opportunity_spec,
        tool_specs=build_tool_specs(planned_steps=experiment.plan_steps, execution=execution or experiment.execution),
        subagent_tasks=list(subagent_tasks) if subagent_tasks is not None else list(experiment.subagent_tasks),
        execution=dict(to_jsonable(execution or experiment.execution)),
        evaluation=evaluation or experiment.evaluation,
        related_cycle_id=related_cycle_id or experiment.related_cycle_id,
        mission_id=experiment.mission_id,
        branch_id=experiment.branch_id,
        core_universe_snapshot_id=experiment.core_universe_snapshot_id,
        branch_pool_snapshot_id=experiment.branch_pool_snapshot_id,
        opportunity_generator_id=experiment.opportunity_generator_id,
        strategy_candidate_id=experiment.strategy_candidate_id,
        artifact_refs=refs,
    )


def experiment_record_path(project: str, experiment_id: str, *, repo_root: Path | None = None) -> Path:
    paths = resolve_project_paths(project, root=repo_root)
    paths.experiments_dir.mkdir(parents=True, exist_ok=True)
    return paths.experiments_dir / f"{experiment_id}.json"


def write_experiment_record(experiment: Experiment, *, repo_root: Path | None = None) -> Path:
    path = experiment_record_path(experiment.project, experiment.experiment_id, repo_root=repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(to_jsonable(experiment.to_dict()), ensure_ascii=False, indent=2, sort_keys=True).rstrip() + "\n"
    path.write_text(text, encoding="utf-8")
    return path


def read_experiment_record(project: str, experiment_id: str, *, repo_root: Path | None = None) -> Experiment:
    path = experiment_record_path(project, experiment_id, repo_root=repo_root)
    payload = json.loads(path.read_text(encoding="utf-8"))
    universe_snapshot = UniverseSnapshot(**payload["universe_snapshot"])
    dataset_snapshot = DatasetSnapshot(**payload["dataset_snapshot"])
    factor_specs = [FactorSpec(**item) for item in payload.get("factor_specs", [])]
    opportunity = OpportunitySpec(**payload["opportunity_spec"]) if payload.get("opportunity_spec") else None
    tool_specs = [ToolSpec(**item) for item in payload.get("tool_specs", [])]
    subagent_tasks = [SubagentTask(**item) for item in payload.get("subagent_tasks", [])]
    evaluation = EvaluationRecord(**payload["evaluation"]) if payload.get("evaluation") else None
    return Experiment(
        experiment_id=str(payload["experiment_id"]),
        project=str(payload["project"]),
        created_at=str(payload["created_at"]),
        updated_at=str(payload["updated_at"]),
        status=str(payload["status"]),
        hypothesis=str(payload["hypothesis"]),
        mode=str(payload["mode"]),
        plan_steps=list(payload.get("plan_steps", [])),
        success_criteria=list(payload.get("success_criteria", [])),
        universe_snapshot=universe_snapshot,
        dataset_snapshot=dataset_snapshot,
        factor_specs=factor_specs,
        opportunity_spec=opportunity,
        tool_specs=tool_specs,
        subagent_tasks=subagent_tasks,
        execution=dict(payload.get("execution", {})),
        evaluation=evaluation,
        related_cycle_id=payload.get("related_cycle_id"),
        mission_id=payload.get("mission_id"),
        branch_id=payload.get("branch_id"),
        core_universe_snapshot_id=payload.get("core_universe_snapshot_id"),
        branch_pool_snapshot_id=payload.get("branch_pool_snapshot_id"),
        opportunity_generator_id=payload.get("opportunity_generator_id"),
        strategy_candidate_id=payload.get("strategy_candidate_id"),
        artifact_refs=list(payload.get("artifact_refs", [])),
    )


def recent_experiment_summaries(project: str, *, repo_root: Path | None = None, limit: int = 3) -> list[dict[str, Any]]:
    paths = resolve_project_paths(project, root=repo_root)
    if not paths.experiments_dir.exists():
        return []
    files = sorted(paths.experiments_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    summaries: list[dict[str, Any]] = []
    for path in files[:limit]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        evaluation = payload.get("evaluation") or {}
        summaries.append(
            {
                "experiment_id": payload.get("experiment_id", path.stem),
                "status": payload.get("status", "unknown"),
                "hypothesis": payload.get("hypothesis", ""),
                "classification": evaluation.get("classification", ""),
                "summary": evaluation.get("summary", ""),
                "primary_blockers": evaluation.get("primary_blockers", []),
                "mission_id": payload.get("mission_id", ""),
                "branch_id": payload.get("branch_id", ""),
                "path": str(path),
            },
        )
    return summaries
