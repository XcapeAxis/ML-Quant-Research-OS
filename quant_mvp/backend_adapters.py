from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Iterable, Mapping

from .experiment_graph import BackendAdapter, BackendRun, DecisionRecord, FailureRecord
from .memory.ledger import stable_hash, to_jsonable


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def build_local_pipeline_adapter() -> BackendAdapter:
    return BackendAdapter(
        adapter_id="local_pipeline",
        adapter_name="Local Pipeline",
        adapter_type="local_pipeline",
        provider="local.quant_mvp",
        provider_display_name="Local Quant MVP Pipeline",
        capabilities=[
            "f1_train",
            "f1_verify",
            "f2_train",
            "f2_verify",
            "r1_verify",
            "shared_shell_backtest",
            "memory_writeback",
        ],
        notes="Built-in local execution backend used as the auditable baseline adapter.",
    )


def build_flow_bridge_adapter(
    *,
    provider: str = "pandaai.quantflow",
    provider_display_name: str = "Panda QuantFlow",
) -> BackendAdapter:
    return BackendAdapter(
        adapter_id="flow_bridge",
        adapter_name="Flow Bridge",
        adapter_type="external_flow_engine",
        provider=provider,
        provider_display_name=provider_display_name,
        capabilities=[
            "healthcheck",
            "template_catalog",
            "submit_run",
            "poll_run",
            "fetch_outputs",
            "import_completed_run",
        ],
        notes="External Flow Engine bridge. Provider-specific details stay in provider metadata.",
    )


def build_local_backend_run(
    *,
    workflow_template_id: str,
    status: str,
    parameter_overrides: Mapping[str, Any] | None = None,
    metrics: Mapping[str, Any] | None = None,
    artifact_refs: Iterable[str] | None = None,
    log_refs: Iterable[str] | None = None,
    lineage_metadata: Mapping[str, Any] | None = None,
    failure_reason: str = "",
    submitted_at: str | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
) -> BackendRun:
    submitted_value = submitted_at or _utc_now()
    started_value = started_at or submitted_value
    fingerprint_payload = {
        "workflow_template_id": workflow_template_id,
        "parameter_overrides": dict(to_jsonable(parameter_overrides or {})),
        "lineage_metadata": dict(to_jsonable(lineage_metadata or {})),
    }
    return BackendRun(
        backend_run_id=f"local-run-{stable_hash(fingerprint_payload)[:12]}",
        adapter_id="local_pipeline",
        status=status,
        workflow_template_id=workflow_template_id,
        reproducibility_fingerprint=stable_hash(fingerprint_payload),
        submitted_at=submitted_value,
        started_at=started_value,
        finished_at=finished_at,
        parameter_overrides=dict(to_jsonable(parameter_overrides or {})),
        metrics=dict(to_jsonable(metrics or {})),
        artifact_refs=[str(item) for item in artifact_refs or [] if str(item).strip()],
        log_refs=[str(item) for item in log_refs or [] if str(item).strip()],
        lineage_metadata=dict(to_jsonable(lineage_metadata or {})),
        failure_reason=str(failure_reason or ""),
    )


def build_decision_record(
    *,
    decision: str,
    summary: str,
    reasons: Iterable[str] | None = None,
    next_action: str = "",
    decision_at: str | None = None,
) -> DecisionRecord:
    return DecisionRecord(
        decision=decision,
        summary=summary,
        reasons=[str(item) for item in reasons or [] if str(item).strip()],
        next_action=str(next_action or ""),
        decision_at=decision_at or _utc_now(),
    )


def infer_failure_class(root_cause: str) -> str:
    lowered = str(root_cause or "").strip().lower()
    if not lowered:
        return "execution_failure"
    if any(token in lowered for token in ["leakage", "future leak"]):
        return "contract_failure"
    if any(token in lowered for token in ["drawdown", "calmar", "sharpe", "annualized return"]):
        return "drawdown_failure"
    if any(token in lowered for token in ["freshness", "mismatch", "duplicate", "rank frame", "shared-shell", "shared shell"]):
        return "contract_failure"
    if any(token in lowered for token in ["missing", "snapshot", "empty", "no experiment records", "no shared rebalance dates"]):
        return "data_failure"
    if any(token in lowered for token in ["adapter", "provider", "flow engine", "submit_run", "fetch_outputs"]):
        return "adapter_failure"
    return "execution_failure"


def build_failure_record(
    *,
    summary: str,
    root_cause: str,
    corrective_action: str = "",
    resolution_status: str = "not_fixed",
    failure_class: str | None = None,
    recorded_at: str | None = None,
) -> FailureRecord:
    return FailureRecord(
        failure_class=str(failure_class or infer_failure_class(root_cause)),
        summary=str(summary),
        root_cause=str(root_cause),
        corrective_action=str(corrective_action or ""),
        resolution_status=str(resolution_status or "not_fixed"),
        recorded_at=recorded_at or _utc_now(),
    )
