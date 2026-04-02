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


def _object_id(prefix: str, payload: Mapping[str, Any]) -> str:
    return f"{prefix}-{stable_hash(dict(payload))[:12]}"


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
class FactorCandidate:
    factor_id: str
    name: str
    family: str
    description: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    source: str = "manual"
    status: str = "seed"
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FeatureView:
    feature_view_id: str
    name: str
    inputs: list[str] = field(default_factory=list)
    transforms: list[str] = field(default_factory=list)
    sampling: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LabelSpec:
    label_spec_id: str
    target_name: str
    horizon: str
    objective: str
    definition: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ModelCandidate:
    model_id: str
    name: str
    family: str
    params: dict[str, Any] = field(default_factory=dict)
    is_online_adaptive: bool = False
    update_frequency: str = "offline"
    training_mode: str = "batch"
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RegimeSpec:
    regime_id: str
    detector_name: str
    transition_signal: str
    regime_transition_latency: float | None = None
    adaptive_policy: str = "static"
    notes: str = ""

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
class BackendAdapter:
    adapter_id: str
    adapter_name: str
    adapter_type: str
    provider: str
    provider_display_name: str = ""
    capabilities: list[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BackendRun:
    backend_run_id: str
    adapter_id: str
    status: str
    workflow_template_id: str
    reproducibility_fingerprint: str
    submitted_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    parameter_overrides: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    artifact_refs: list[str] = field(default_factory=list)
    log_refs: list[str] = field(default_factory=list)
    lineage_metadata: dict[str, Any] = field(default_factory=dict)
    failure_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DecisionRecord:
    decision: str
    summary: str
    reasons: list[str] = field(default_factory=list)
    next_action: str = ""
    decision_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FailureRecord:
    failure_class: str
    summary: str
    root_cause: str
    corrective_action: str = ""
    resolution_status: str = "not_fixed"
    recorded_at: str = ""

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
    adversarial_robustness: dict[str, Any] = field(default_factory=dict)
    regime_transition_drawdown: float | None = None

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
    factor_candidates: list[FactorCandidate] = field(default_factory=list)
    feature_view: FeatureView | None = None
    label_spec: LabelSpec | None = None
    model_candidate: ModelCandidate | None = None
    regime_spec: RegimeSpec | None = None
    factor_specs: list[FactorSpec] = field(default_factory=list)
    opportunity_spec: OpportunitySpec | None = None
    tool_specs: list[ToolSpec] = field(default_factory=list)
    subagent_tasks: list[SubagentTask] = field(default_factory=list)
    backend_adapter: BackendAdapter | None = None
    backend_run: BackendRun | None = None
    execution: dict[str, Any] = field(default_factory=dict)
    evaluation: EvaluationRecord | None = None
    decision_record: DecisionRecord | None = None
    failure_record: FailureRecord | None = None
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
        payload["factor_candidates"] = [item.to_dict() for item in self.factor_candidates]
        payload["feature_view"] = self.feature_view.to_dict() if self.feature_view else None
        payload["label_spec"] = self.label_spec.to_dict() if self.label_spec else None
        payload["model_candidate"] = self.model_candidate.to_dict() if self.model_candidate else None
        payload["regime_spec"] = self.regime_spec.to_dict() if self.regime_spec else None
        payload["factor_specs"] = [item.to_dict() for item in self.factor_specs]
        payload["opportunity_spec"] = self.opportunity_spec.to_dict() if self.opportunity_spec else None
        payload["tool_specs"] = [item.to_dict() for item in self.tool_specs]
        payload["subagent_tasks"] = [item.to_dict() for item in self.subagent_tasks]
        payload["backend_adapter"] = self.backend_adapter.to_dict() if self.backend_adapter else None
        payload["backend_run"] = self.backend_run.to_dict() if self.backend_run else None
        payload["evaluation"] = self.evaluation.to_dict() if self.evaluation else None
        payload["decision_record"] = self.decision_record.to_dict() if self.decision_record else None
        payload["failure_record"] = self.failure_record.to_dict() if self.failure_record else None
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


def build_factor_candidates(
    *,
    cfg: Mapping[str, Any],
    branch_id: str | None = None,
    strategy_params: Mapping[str, Any] | None = None,
) -> list[FactorCandidate]:
    strategy_mode = str(cfg.get("strategy_mode", "limit_up_screening"))
    compact_params = {
        key: value
        for key, value in {
            "strategy_mode": strategy_mode,
            "branch_id": branch_id,
            "top_pct_limit_up": cfg.get("top_pct_limit_up"),
            "limit_days_window": cfg.get("limit_days_window"),
            "variant": dict(strategy_params or {}).get("variant"),
        }.items()
        if value is not None
    }
    return [
        FactorCandidate(
            factor_id=_object_id("factor", compact_params),
            name=f"{strategy_mode}_event_seed",
            family="event_seed",
            description="Bridge a legacy event rule into the factor-first object layer before F1 factor models arrive.",
            params=compact_params,
            source="legacy_control_branch",
            status="seed",
            tags=["stage_f0", "control_branch"],
        ),
    ]


def build_feature_view(
    *,
    cfg: Mapping[str, Any],
    branch_id: str | None = None,
    branch_pool_snapshot_id: str | None = None,
) -> FeatureView:
    payload = {
        "strategy_mode": str(cfg.get("strategy_mode", "limit_up_screening")),
        "freq": str(cfg.get("freq", "1d")),
        "branch_id": branch_id,
        "branch_pool_snapshot_id": branch_pool_snapshot_id,
    }
    return FeatureView(
        feature_view_id=_object_id("feature-view", payload),
        name="legacy_event_panel_v1",
        inputs=["daily_ohlcv", "branch_pool_membership", "limit_up_event_flags"],
        transforms=["panel_align", "branch_pool_mask", "tradability_guard"],
        sampling=f"{payload['freq']} cross_sectional_panel",
        notes="F0 placeholder feature view for control branches; F1 will replace it with explicit factor features.",
    )


def build_label_spec(*, cfg: Mapping[str, Any]) -> LabelSpec:
    horizon = str(cfg.get("rebalance_every", cfg.get("freq", "1d")))
    payload = {
        "target_name": "next_rebalance_excess_return",
        "horizon": horizon,
        "objective": "cross_sectional_ranking",
    }
    return LabelSpec(
        label_spec_id=_object_id("label", payload),
        target_name="next_rebalance_excess_return",
        horizon=horizon,
        objective="cross_sectional_ranking",
        definition="Relative forward return over the next rebalance window versus a simple market baseline.",
        notes="F0 keeps the label explicit so F1 factor models and later adaptive models share one target contract.",
    )


def build_model_candidate(
    *,
    cfg: Mapping[str, Any],
    branch_id: str | None = None,
    strategy_params: Mapping[str, Any] | None = None,
) -> ModelCandidate:
    strategy_mode = str(cfg.get("strategy_mode", "limit_up_screening"))
    payload = {
        "strategy_mode": strategy_mode,
        "branch_id": branch_id,
        "variant": dict(strategy_params or {}).get("variant"),
    }
    return ModelCandidate(
        model_id=_object_id("model", payload),
        name=f"{strategy_mode}_control_harness",
        family="rule_based_control",
        params={key: value for key, value in payload.items() if value is not None},
        is_online_adaptive=False,
        update_frequency="offline",
        training_mode="deterministic",
        notes="Control-harness model used before the first explicit factor model lands in F1.",
    )


def build_regime_spec(*, cfg: Mapping[str, Any], branch_id: str | None = None) -> RegimeSpec:
    payload = {
        "branch_id": branch_id,
        "freq": str(cfg.get("freq", "1d")),
        "adaptive_policy": "static",
    }
    return RegimeSpec(
        regime_id=_object_id("regime", payload),
        detector_name="static_baseline",
        transition_signal="not_enabled",
        regime_transition_latency=None,
        adaptive_policy="static",
        notes="F0 reserves the regime interface; R1 will later replace it with predictive-error and TTA-driven logic.",
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
    factor_candidates: list[FactorCandidate] | None = None,
    feature_view: FeatureView | None = None,
    label_spec: LabelSpec | None = None,
    model_candidate: ModelCandidate | None = None,
    regime_spec: RegimeSpec | None = None,
    backend_adapter: BackendAdapter | None = None,
    backend_run: BackendRun | None = None,
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
        factor_candidates=list(factor_candidates or []),
        feature_view=feature_view,
        label_spec=label_spec,
        model_candidate=model_candidate,
        regime_spec=regime_spec,
        factor_specs=[],
        opportunity_spec=opportunity_spec,
        tool_specs=build_tool_specs(planned_steps=plan_steps),
        subagent_tasks=list(subagent_tasks),
        backend_adapter=backend_adapter,
        backend_run=backend_run,
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
    backend_adapter: BackendAdapter | None = None,
    backend_run: BackendRun | None = None,
    decision_record: DecisionRecord | None = None,
    failure_record: FailureRecord | None = None,
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
        factor_candidates=list(experiment.factor_candidates),
        feature_view=experiment.feature_view,
        label_spec=experiment.label_spec,
        model_candidate=experiment.model_candidate,
        regime_spec=experiment.regime_spec,
        factor_specs=list(experiment.factor_specs),
        opportunity_spec=experiment.opportunity_spec,
        tool_specs=build_tool_specs(planned_steps=experiment.plan_steps, execution=execution or experiment.execution),
        subagent_tasks=list(subagent_tasks) if subagent_tasks is not None else list(experiment.subagent_tasks),
        backend_adapter=backend_adapter if backend_adapter is not None else experiment.backend_adapter,
        backend_run=backend_run if backend_run is not None else experiment.backend_run,
        execution=dict(to_jsonable(execution or experiment.execution)),
        evaluation=evaluation or experiment.evaluation,
        decision_record=decision_record if decision_record is not None else experiment.decision_record,
        failure_record=failure_record if failure_record is not None else experiment.failure_record,
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
    factor_candidates = [FactorCandidate(**item) for item in payload.get("factor_candidates", [])]
    feature_view = FeatureView(**payload["feature_view"]) if payload.get("feature_view") else None
    label_spec = LabelSpec(**payload["label_spec"]) if payload.get("label_spec") else None
    model_candidate = ModelCandidate(**payload["model_candidate"]) if payload.get("model_candidate") else None
    regime_spec = RegimeSpec(**payload["regime_spec"]) if payload.get("regime_spec") else None
    factor_specs = [FactorSpec(**item) for item in payload.get("factor_specs", [])]
    opportunity = OpportunitySpec(**payload["opportunity_spec"]) if payload.get("opportunity_spec") else None
    tool_specs = [ToolSpec(**item) for item in payload.get("tool_specs", [])]
    subagent_tasks = [SubagentTask(**item) for item in payload.get("subagent_tasks", [])]
    backend_adapter = BackendAdapter(**payload["backend_adapter"]) if payload.get("backend_adapter") else None
    backend_run = BackendRun(**payload["backend_run"]) if payload.get("backend_run") else None
    evaluation = EvaluationRecord(**payload["evaluation"]) if payload.get("evaluation") else None
    decision_record = DecisionRecord(**payload["decision_record"]) if payload.get("decision_record") else None
    failure_record = FailureRecord(**payload["failure_record"]) if payload.get("failure_record") else None
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
        factor_candidates=factor_candidates,
        feature_view=feature_view,
        label_spec=label_spec,
        model_candidate=model_candidate,
        regime_spec=regime_spec,
        factor_specs=factor_specs,
        opportunity_spec=opportunity,
        tool_specs=tool_specs,
        subagent_tasks=subagent_tasks,
        backend_adapter=backend_adapter,
        backend_run=backend_run,
        execution=dict(payload.get("execution", {})),
        evaluation=evaluation,
        decision_record=decision_record,
        failure_record=failure_record,
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
                "backend_adapter_id": ((payload.get("backend_adapter") or {}).get("adapter_id", "")),
                "backend_run_status": ((payload.get("backend_run") or {}).get("status", "")),
                "decision": ((payload.get("decision_record") or {}).get("decision", "")),
                "failure_class": ((payload.get("failure_record") or {}).get("failure_class", "")),
                "path": str(path),
            },
        )
    return summaries
