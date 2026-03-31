from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from .backtest_engine import BacktestConfig, run_topn_suite
from .config import load_config
from .db import load_close_volume_panel
from .experiment_graph import (
    EvaluationRecord,
    Experiment,
    new_experiment,
    read_experiment_record,
    update_experiment,
    write_experiment_record,
)
from .f1_pipeline import (
    _dedupe,
    _factor_model_config,
    _feature_view,
)
from .manifest import update_run_manifest
from .memory.ledger import stable_hash, to_jsonable
from .memory.writeback import (
    generate_handoff,
    load_machine_state,
    record_experiment_result,
    record_failure,
    save_machine_state,
    sync_project_state,
    sync_research_memory,
    update_hypothesis_queue,
    write_verify_snapshot,
)
from .pools import load_latest_core_pool_snapshot
from .project import resolve_project_paths
from .research_core import resolve_limit_up_config
from .selection import build_limit_up_screening_rank


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _load_latest_f1_experiment(project: str, *, repo_root: Path | None = None) -> Experiment:
    paths = resolve_project_paths(project, root=repo_root)
    if not paths.experiments_dir.exists():
        raise RuntimeError("No experiment records exist for this project; rerun f1_train first.")
    records = sorted(paths.experiments_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    for path in records:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if (
            str(payload.get("mode", "")) == "f1_train"
            and str(payload.get("branch_id", "")) == "factor_elasticnet_core"
            and str(payload.get("strategy_candidate_id", "")) == "f1_elasticnet_v1"
        ):
            return read_experiment_record(project, str(payload["experiment_id"]), repo_root=repo_root)
    raise RuntimeError("No latest F1 training experiment was found; rerun f1_train first.")


def _load_f1_train_report(paths) -> dict[str, Any]:
    report_path = paths.artifacts_dir / "f1" / "f1_train_report.json"
    if not report_path.exists():
        raise RuntimeError("Latest F1 train report is missing; rerun f1_train first.")
    return json.loads(report_path.read_text(encoding="utf-8"))


def _expected_compare_topk(cfg: dict[str, Any]) -> int:
    return int(cfg.get("stock_num", cfg.get("topk", 6)))


def _validate_freshness(
    *,
    cfg: dict[str, Any],
    paths,
    core_snapshot,
    f1_experiment: Experiment,
    f1_report: dict[str, Any],
) -> int:
    model_cfg = _factor_model_config(cfg)
    expected_topk = _expected_compare_topk(cfg)
    expected_feature_view = _feature_view(model_cfg, str(cfg.get("freq", "1d"))).name
    rank_path = paths.signals_dir / f"f1_elasticnet_rank_top{expected_topk}.parquet"

    mismatch_reasons: list[str] = []
    if str(f1_experiment.core_universe_snapshot_id or "") != str(core_snapshot.snapshot_id):
        mismatch_reasons.append("core_universe_snapshot_id mismatch")
    if str(f1_report.get("core_snapshot_id", "")) != str(core_snapshot.snapshot_id):
        mismatch_reasons.append("f1_train_report core_snapshot_id mismatch")
    if str(f1_report.get("profile", "")) != str(model_cfg.profile):
        mismatch_reasons.append("factor_model.profile mismatch")
    if str((f1_experiment.feature_view.name if f1_experiment.feature_view else "")) != expected_feature_view:
        mismatch_reasons.append("feature_view.name mismatch")
    if int(f1_report.get("topk", -1)) != int(expected_topk):
        mismatch_reasons.append("topk mismatch")
    if not rank_path.exists():
        mismatch_reasons.append(f"missing rank artifact: {rank_path.name}")

    if mismatch_reasons:
        raise RuntimeError(
            "Latest F1 artifacts do not match the current core snapshot/profile/topk; rerun f1_train first. "
            + "; ".join(mismatch_reasons)
        )
    return expected_topk


def _build_control_rank(
    *,
    cfg: dict[str, Any],
    core_codes: list[str],
) -> pd.DataFrame:
    sel_cfg = resolve_limit_up_config(cfg)
    sel_cfg.stock_num = _expected_compare_topk(cfg)
    result = build_limit_up_screening_rank(
        db_path=Path(str(cfg["db_path"])),
        freq=str(cfg["freq"]),
        universe_codes=list(core_codes),
        cfg=sel_cfg,
        start_date=cfg.get("start_date"),
        end_date=cfg.get("end_date"),
    )
    rank_df = result.rank_df.loc[result.rank_df["rank"] <= sel_cfg.stock_num, ["date", "code", "score", "rank"]].copy()
    if rank_df.empty:
        raise RuntimeError("Control rank on the current core pool is empty.")
    rank_df["date"] = pd.to_datetime(rank_df["date"])
    rank_df["code"] = rank_df["code"].astype(str).str.zfill(6)
    rank_df["rank"] = rank_df["rank"].astype(int)
    return rank_df.sort_values(["date", "rank", "code"]).reset_index(drop=True)


def _intersect_rank_frames(*, f1_rank: pd.DataFrame, control_rank: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    shared_dates = sorted(set(pd.to_datetime(f1_rank["date"])) & set(pd.to_datetime(control_rank["date"])))
    if not shared_dates:
        raise RuntimeError("No shared rebalance dates exist between the latest F1 rank and the control rank.")
    f1_shared = f1_rank.loc[f1_rank["date"].isin(shared_dates)].copy()
    control_shared = control_rank.loc[control_rank["date"].isin(shared_dates)].copy()
    if f1_shared.empty or control_shared.empty:
        raise RuntimeError("The shared-shell verifier produced an empty rank frame after date intersection.")
    return (
        f1_shared.sort_values(["date", "rank", "code"]).reset_index(drop=True),
        control_shared.sort_values(["date", "rank", "code"]).reset_index(drop=True),
    )


def _load_shared_close_panel(
    *,
    cfg: dict[str, Any],
    codes: list[str],
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.DataFrame:
    configured_end = cfg.get("end_date")
    effective_end = min(
        pd.Timestamp(configured_end) if configured_end else end + pd.Timedelta(days=7),
        end + pd.Timedelta(days=7),
    )
    close_panel, _ = load_close_volume_panel(
        db_path=Path(str(cfg["db_path"])),
        freq=str(cfg["freq"]),
        codes=list(codes),
        start=start.strftime("%Y-%m-%d"),
        end=effective_end.strftime("%Y-%m-%d"),
    )
    panel = close_panel.reindex(columns=list(codes)).astype(float)
    if panel.empty:
        raise RuntimeError("Shared-shell verifier close panel is empty.")
    return panel


def _shared_backtest_config(cfg: dict[str, Any]) -> BacktestConfig:
    return BacktestConfig(
        cash=float(cfg["cash"]),
        commission=float(cfg["commission"]),
        stamp_duty=float(cfg["stamp_duty"]),
        slippage=float(cfg["slippage"]),
        risk_free_rate=float(cfg["risk_free_rate"]),
        risk_overlay={},
        min_commission=cfg.get("min_commission"),
    )


def _topk_metrics(metrics_df: pd.DataFrame, *, topk: int) -> dict[str, Any]:
    row = metrics_df.loc[metrics_df["topn"].astype(int) == int(topk)]
    if row.empty:
        raise RuntimeError(f"Verifier metrics are missing the Top{topk} row.")
    return {str(key): value for key, value in row.iloc[0].to_dict().items()}


def _delta_metrics(*, f1_metrics: dict[str, Any], control_metrics: dict[str, Any]) -> dict[str, float]:
    return {
        "total_return_delta": float(f1_metrics.get("total_return", 0.0) or 0.0) - float(control_metrics.get("total_return", 0.0) or 0.0),
        "annualized_return_delta": float(f1_metrics.get("annualized_return", 0.0) or 0.0) - float(control_metrics.get("annualized_return", 0.0) or 0.0),
        "sharpe_ratio_delta": float(f1_metrics.get("sharpe_ratio", 0.0) or 0.0) - float(control_metrics.get("sharpe_ratio", 0.0) or 0.0),
        "max_drawdown_improvement": abs(float(control_metrics.get("max_drawdown", 0.0) or 0.0)) - abs(float(f1_metrics.get("max_drawdown", 0.0) or 0.0)),
        "calmar_ratio_delta": float(f1_metrics.get("calmar_ratio", 0.0) or 0.0) - float(control_metrics.get("calmar_ratio", 0.0) or 0.0),
        "win_rate_delta": float(f1_metrics.get("win_rate", 0.0) or 0.0) - float(control_metrics.get("win_rate", 0.0) or 0.0),
    }


def _decision_from_metrics(*, f1_metrics: dict[str, Any], control_metrics: dict[str, Any]) -> dict[str, Any]:
    deltas = _delta_metrics(f1_metrics=f1_metrics, control_metrics=control_metrics)
    drawdown_improvement = deltas["max_drawdown_improvement"]
    annualized_return_delta = deltas["annualized_return_delta"]
    sharpe_delta = deltas["sharpe_ratio_delta"]

    primary_blockers: list[str] = []
    if drawdown_improvement < 0.05:
        primary_blockers.append(
            f"shared_shell_drawdown_improvement {drawdown_improvement:.2%} is below the required 5.00% improvement."
        )
    if annualized_return_delta < -0.02:
        primary_blockers.append(
            f"shared_shell_annualized_return_delta {annualized_return_delta:.2%} is below the allowed -2.00% floor."
        )
    if drawdown_improvement >= 0.05 and annualized_return_delta >= -0.02:
        decision = "keep_f1_mainline"
        if sharpe_delta >= 0.0:
            classification = "verifier_pass"
            next_action = "reopen_light_scouting_for_f2_r1"
        else:
            classification = "verifier_mixed"
            next_action = "run_f1_1_bounded_risk_overlay_variant"
            primary_blockers.append(
                f"shared_shell_sharpe_ratio_delta {sharpe_delta:.4f} is still below the control branch."
            )
    else:
        decision = "keep_f1_local_and_do_one_more_bounded_risk_variant"
        next_action = "run_f1_1_bounded_risk_overlay_variant"
        if drawdown_improvement > 0 or annualized_return_delta > 0 or sharpe_delta > 0:
            classification = "verifier_mixed"
        else:
            classification = "verifier_fail"

    next_themes = (
        [
            "Re-run Subagent Gate at LIGHT and reopen Zeno / Popper / Fermat for F2 and R1 frontier scouting.",
            "Keep the F1 verifier result as the control point for future deep-factor and regime-adaptation challengers.",
        ]
        if next_action == "reopen_light_scouting_for_f2_r1"
        else [
            "Run one bounded F1.1 risk-overlay variant with rolling_days=20, vol_target=0.18, max_leverage=1.0.",
            "Do not open broad parameter search or F2/R1 scouting before the bounded F1.1 comparison is complete.",
        ]
    )

    return {
        "decision": decision,
        "classification": classification,
        "next_action": next_action,
        "primary_blockers": _dedupe(primary_blockers),
        "delta_metrics": deltas,
        "next_experiment_themes": next_themes,
    }


def _refresh_strategy_candidates(
    *,
    state: dict[str, Any],
    decision_payload: dict[str, Any],
    topk: int,
    f1_metrics: dict[str, Any],
    control_metrics: dict[str, Any],
    artifact_refs: list[str],
) -> list[dict[str, Any]]:
    current = [dict(item) for item in list(state.get("strategy_candidates", []) or []) if isinstance(item, dict)]
    updated: list[dict[str, Any]] = []
    saw_f1 = False
    for item in current:
        strategy_id = str(item.get("strategy_id", "")).strip()
        candidate = dict(item)
        if strategy_id == "baseline_limit_up":
            candidate["track"] = "secondary"
            candidate["decision"] = "continue"
            candidate["current_stage"] = "validation"
            candidate["latest_action"] = "Completed the shared-shell bounded verifier as the control branch."
            candidate["latest_result"] = (
                f"Control branch shared-shell Top{topk}: annualized_return={float(control_metrics.get('annualized_return', 0.0)):.2%}, "
                f"max_drawdown={abs(float(control_metrics.get('max_drawdown', 0.0))):.2%}, "
                f"sharpe={float(control_metrics.get('sharpe_ratio', 0.0)):.4f}."
            )
            candidate["next_validation"] = "Keep as the control branch while F2/R1 challengers are scoped."
            candidate["blocked_by"] = []
            candidate["artifact_refs"] = _dedupe(list(candidate.get("artifact_refs", []) or []) + artifact_refs)
        elif strategy_id == "f1_elasticnet_v1":
            saw_f1 = True
            candidate["track"] = "primary"
            candidate["decision"] = "continue"
            candidate["current_stage"] = "validation"
            candidate["latest_action"] = "Completed one shared-shell bounded verifier against baseline_limit_up."
            candidate["latest_result"] = (
                f"F1 shared-shell Top{topk}: annualized_return={float(f1_metrics.get('annualized_return', 0.0)):.2%}, "
                f"max_drawdown={abs(float(f1_metrics.get('max_drawdown', 0.0))):.2%}, "
                f"sharpe={float(f1_metrics.get('sharpe_ratio', 0.0)):.4f}; decision={decision_payload['decision']}."
            )
            candidate["next_validation"] = (
                "Reopen LIGHT scouting for Zeno / Popper / Fermat and define F2/R1 challengers."
                if decision_payload["next_action"] == "reopen_light_scouting_for_f2_r1"
                else "Run the bounded F1.1 risk-overlay variant before reopening broader search."
            )
            candidate["blocked_by"] = list(decision_payload.get("primary_blockers", []) or [])
            candidate["artifact_refs"] = _dedupe(list(candidate.get("artifact_refs", []) or []) + artifact_refs)
        updated.append(candidate)

    if not saw_f1:
        updated.append(
            {
                "strategy_id": "f1_elasticnet_v1",
                "name": "F1 ElasticNet 因子主线",
                "category": "other",
                "core_hypothesis": "技术+流动性因子与 5 日超额收益标签的正则化横截面模型，可以在当前 core universe 上提供比 control branch 更强的 shared-shell 排名。",
                "economic_rationale": "如果可解释的技术与流动性特征已经能稳定区分未来 5 日横截面收益，平台应先把这条因子主线立起来，再继续扩展更深模型与 regime 层。",
                "required_data": "主板 A 股日频 OHLCV、core pool 快照、benchmark 收盘序列、5 日超额收益标签。",
                "current_stage": "validation",
                "latest_action": "Completed one shared-shell bounded verifier against baseline_limit_up.",
                "latest_result": (
                    f"F1 shared-shell Top{topk}: annualized_return={float(f1_metrics.get('annualized_return', 0.0)):.2%}, "
                    f"max_drawdown={abs(float(f1_metrics.get('max_drawdown', 0.0))):.2%}, "
                    f"sharpe={float(f1_metrics.get('sharpe_ratio', 0.0)):.4f}; decision={decision_payload['decision']}."
                ),
                "decision": "continue",
                "next_validation": (
                    "Reopen LIGHT scouting for Zeno / Popper / Fermat and define F2/R1 challengers."
                    if decision_payload["next_action"] == "reopen_light_scouting_for_f2_r1"
                    else "Run the bounded F1.1 risk-overlay variant before reopening broader search."
                ),
                "owner": "main",
                "subagents_assigned": [],
                "artifact_refs": list(artifact_refs),
                "blocked_by": list(decision_payload.get("primary_blockers", []) or []),
                "kill_criteria": "如果后续 bounded 风险变体和后续 challenger 都无法把回撤压到 30% 附近，就不要把 F1 当前形态包装成可晋级主线。",
                "track": "primary",
            }
        )
    return updated


def _load_native_shell_reference(paths, f1_report: dict[str, Any]) -> dict[str, Any]:
    diagnostic_path = paths.artifacts_dir / "baseline_strategy_diagnostic.json"
    payload: dict[str, Any] = {
        "status": "unavailable",
        "f1_train_report_path": str(paths.artifacts_dir / "f1" / "f1_train_report.json"),
        "f1_native_topk_metrics": dict(f1_report.get("topk_metrics", {}) or {}),
        "control_baseline_strategy_diagnostic_path": str(diagnostic_path),
        "control_native_metrics": None,
    }
    if not diagnostic_path.exists():
        return payload
    try:
        diagnostic = json.loads(diagnostic_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        payload["status"] = "partial"
        return payload

    summary = dict(diagnostic.get("summary", {}) or {})
    research_profile_id = str(summary.get("research_profile_id", "")).strip()
    results = dict(diagnostic.get("results", {}) or {})
    profile_results = dict(results.get(research_profile_id, {}) or {})
    baseline = dict(profile_results.get("baseline_limit_up", {}) or {})
    metrics = dict(baseline.get("metrics", {}) or {})
    if metrics:
        payload["status"] = "available"
        payload["control_native_metrics"] = metrics
    else:
        payload["status"] = "partial"
    return payload


def _save_compare_plot(
    *,
    f1_curves: pd.DataFrame,
    control_curves: pd.DataFrame,
    topk: int,
    output_path: Path,
    project: str,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure, axis = plt.subplots(figsize=(10, 5))
    f1_equity = f1_curves[f"Top{topk}"].astype(float)
    control_equity = control_curves[f"Top{topk}"].astype(float)
    axis.plot(f1_equity.index, f1_equity / float(f1_equity.iloc[0]), label=f"F1 Top{topk}", linewidth=1.8)
    axis.plot(
        control_equity.index,
        control_equity / float(control_equity.iloc[0]),
        label=f"Control Top{topk}",
        linewidth=1.8,
    )
    axis.set_title(f"{project}: F1 vs control under shared TopN shell")
    axis.set_ylabel("Normalized equity")
    axis.grid(alpha=0.25)
    axis.legend()
    figure.autofmt_xdate()
    figure.tight_layout()
    figure.savefig(output_path, dpi=150)
    plt.close(figure)
    return output_path


def _write_verifier_report(
    *,
    paths,
    report: dict[str, Any],
) -> tuple[Path, Path]:
    output_dir = paths.artifacts_dir / "f1"
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "F1_BOUNDED_VERIFIER.json"
    md_path = output_dir / "F1_BOUNDED_VERIFIER.md"
    json_path.write_text(json.dumps(to_jsonable(report), ensure_ascii=False, indent=2).rstrip() + "\n", encoding="utf-8")

    blockers = list(report.get("primary_blockers", []) or [])
    next_themes = list(report.get("next_experiment_themes", []) or [])
    blocker_lines = [f"- {item}" for item in blockers] or ["- none"]
    lines = [
        "# F1 Bounded Verifier",
        "",
        f"- project: `{report['project']}`",
        f"- generated_at: `{report['generated_at']}`",
        f"- core_snapshot_id: `{report['core_snapshot_id']}`",
        f"- source_f1_experiment_id: `{report['source_f1_experiment_id']}`",
        f"- compare_shell: `{report['compare_shell']}`",
        f"- date_intersection: `{report['date_intersection_start']}` -> `{report['date_intersection_end']}`",
        f"- topk: `{report['topk']}`",
        f"- decision: `{report['decision']}`",
        f"- classification: `{report['classification']}`",
        f"- next_action: `{report['next_action']}`",
        "",
        "## F1 Metrics",
        *(f"- `{key}`: `{value}`" for key, value in dict(report.get("f1_metrics", {}) or {}).items()),
        "",
        "## Control Metrics",
        *(f"- `{key}`: `{value}`" for key, value in dict(report.get("control_metrics", {}) or {}).items()),
        "",
        "## Delta Metrics",
        *(f"- `{key}`: `{value}`" for key, value in dict(report.get("delta_metrics", {}) or {}).items()),
        "",
        "## Primary Blockers",
        *blocker_lines,
        "",
        "## Next Experiment Themes",
        *(f"- {item}" for item in next_themes),
        "",
        "## Native Shell Reference",
        f"- status: `{dict(report.get('native_shell_reference', {}) or {}).get('status', 'unknown')}`",
        f"- f1_train_report_path: `{dict(report.get('native_shell_reference', {}) or {}).get('f1_train_report_path', '')}`",
        f"- control_baseline_strategy_diagnostic_path: `{dict(report.get('native_shell_reference', {}) or {}).get('control_baseline_strategy_diagnostic_path', '')}`",
        "",
        "## Artifact Paths",
        *(f"- `{key}`: `{value}`" for key, value in dict(report.get("artifact_paths", {}) or {}).items()),
    ]
    md_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return json_path, md_path


def _append_repo_decision_log(
    *,
    repo_root: Path,
    project: str,
    report: dict[str, Any],
) -> None:
    decision_log_path = repo_root / "docs" / "DECISION_LOG.md"
    existing = decision_log_path.read_text(encoding="utf-8") if decision_log_path.exists() else "# Decision Log\n"
    block = "\n".join(
        [
            "",
            f"## {report['generated_at']} - {project}",
            f"- Decision: `{report['decision']}`",
            "- Reason: the shared-shell bounded verifier says F1 now beats the control branch strongly enough to keep the factor mainline and reopen LIGHT scouting for F2/R1.",
            f"- Evidence: `{report['artifact_paths']['verifier_md_path']}`",
        ]
    )
    decision_log_path.write_text(existing.rstrip() + block + "\n", encoding="utf-8")


def _sync_verifier_memory(
    *,
    project: str,
    decision_payload: dict[str, Any],
    topk: int,
    experiment_id: str,
    verifier_json_path: Path,
    verifier_md_path: Path,
    f1_metrics: dict[str, Any],
    report: dict[str, Any],
    repo_root: Path | None = None,
) -> None:
    _, state = load_machine_state(project, repo_root=repo_root)
    max_drawdown = abs(float(f1_metrics.get("max_drawdown", 0.0) or 0.0))
    if max_drawdown > 0.30:
        blocker = f"F1 shared-shell Top{topk} max_drawdown {max_drawdown:.2%} remains above 30.00%."
    elif decision_payload["decision"] != "keep_f1_mainline":
        blocker = "F1 does not beat the control branch strongly enough under the shared TopN shell."
    else:
        blocker = "none"

    next_action = (
        "Reopen LIGHT scouting for Zeno / Popper / Fermat and start F2/R1 frontier scanning."
        if decision_payload["next_action"] == "reopen_light_scouting_for_f2_r1"
        else "Run one bounded F1.1 risk-overlay variant with rolling_days=20, vol_target=0.18, max_leverage=1.0."
    )
    capability = (
        f"F1 bounded verifier compared F1 against baseline_limit_up on the same core universe and shared Top{topk} shell; decision={decision_payload['decision']}."
    )
    state.update(
        {
            "current_phase": "F1 bounded verifier",
            "current_task": "Verify whether F1 beats baseline_limit_up under one shared TopN shell.",
            "current_blocker": blocker,
            "current_capability_boundary": "F1 now has a fair shared-shell verifier, but the result is still prototype-only and is not promotion evidence.",
            "next_priority_action": next_action,
            "last_verified_capability": capability,
            "last_failed_capability": "none" if blocker == "none" else blocker,
            "current_strategy_focus": ["f1_elasticnet_v1"],
            "current_strategy_summary": (
                f"F1 shared-shell verifier classification={decision_payload['classification']}; decision={decision_payload['decision']}."
            ),
            "configured_subagent_gate_mode": "OFF",
            "effective_subagent_gate_mode": "OFF",
            "effective_subagent_gate_reason": "This verifier is a tightly coupled compare path; serial execution is cheaper and cleaner than parallel subagents.",
            "f1_verifier_report_path": str(verifier_json_path),
            "f1_verifier_decision": str(decision_payload["decision"]),
            "f1_verifier_classification": str(decision_payload["classification"]),
        }
    )
    state["strategy_candidates"] = _refresh_strategy_candidates(
        state=state,
        decision_payload=decision_payload,
        topk=topk,
        f1_metrics=f1_metrics,
        control_metrics=dict(report.get("control_metrics", {}) or {}),
        artifact_refs=[str(verifier_json_path), str(verifier_md_path)],
    )
    save_machine_state(project, state, repo_root=repo_root)

    durable_facts = _dedupe(
        list(state.get("durable_facts", []) or [])
        + [
            "F1 bounded verifier now compares F1 and baseline_limit_up on the same core universe under one shared TopN shell.",
            f"The latest F1 bounded verifier decision is {decision_payload['decision']}.",
        ]
    )
    negative_memory = _dedupe(
        list(state.get("negative_memory", []) or [])
        + [
            "Do not compare F1 against the old legacy baseline output when the verifier requires the latest core pool only.",
            "Do not reopen F2/R1 scouting unless the shared-shell verifier says F1 keeps the mainline strongly enough.",
        ]
    )
    next_step_memory = _dedupe(
        [next_action, *list(state.get("next_step_memory", []) or [])]
    )[:5]
    sync_research_memory(
        project,
        durable_facts=durable_facts,
        negative_memory=negative_memory,
        next_step_memory=next_step_memory,
        repo_root=repo_root,
    )

    hypotheses = [
        {
            "status": "done",
            "hypothesis": "A bounded verifier should compare F1 against the control branch before any broader search is reopened.",
        },
        {
            "status": "active" if decision_payload["decision"] == "keep_f1_mainline" else "pending",
            "hypothesis": "Regularized ElasticNet on technical + liquidity features can become the main factor branch after it beats the control branch under one shared TopN shell.",
        },
        {
            "status": "active" if decision_payload["decision"] != "keep_f1_mainline" else "pending",
            "hypothesis": "A bounded F1.1 risk-overlay variant can reduce drawdown without changing features, label, or model.",
        },
        {
            "status": "pending",
            "hypothesis": "Only after the shared-shell verifier clears should the system reopen F2 deep-factor and R1 regime-control scouting.",
        },
    ]
    update_hypothesis_queue(project, hypotheses, repo_root=repo_root)

    record_experiment_result(
        project,
        {
            "timestamp": _utc_now(),
            "experiment_id": experiment_id,
            "hypothesis": report["hypothesis"],
            "config_hash": stable_hash({"core_snapshot_id": report["core_snapshot_id"], "topk": topk}),
            "result": decision_payload["classification"],
            "blockers": list(decision_payload.get("primary_blockers", []) or []),
            "artifact_refs": [str(verifier_json_path), str(verifier_md_path)],
        },
        repo_root=repo_root,
    )
    if decision_payload["decision"] != "keep_f1_mainline":
        record_failure(
            project,
            {
                "timestamp": _utc_now(),
                "experiment_id": experiment_id,
                "summary": "F1 bounded verifier did not clear the shared-shell control comparison.",
                "root_cause": "; ".join(list(decision_payload.get("primary_blockers", []) or [])) or decision_payload["decision"],
                "corrective_action": "Run the bounded F1.1 risk-overlay variant before reopening broader search.",
                "resolution_status": "not_fixed",
            },
            repo_root=repo_root,
            append_ledger=False,
            preserve_progress=True,
        )

    write_verify_snapshot(
        project,
        {
            "passed_commands": [f"python -m quant_mvp f1_verify --project {project}"],
            "failed_commands": [],
            "default_project_data_status": f"latest core pool `{report['core_snapshot_id']}` stayed consistent through the verifier run.",
            "conclusion_boundary_engineering": "The shared-shell verifier is now runnable and writes formal experiment plus tracked memory outputs.",
            "conclusion_boundary_research": (
                "The verifier compares F1 and the control branch fairly, but it still does not prove profitability or promotion readiness."
            ),
            "last_verified_capability": capability,
        },
        repo_root=repo_root,
    )
    if decision_payload["next_action"] == "reopen_light_scouting_for_f2_r1" and repo_root is not None:
        _append_repo_decision_log(repo_root=repo_root, project=project, report=report)
    generate_handoff(project, repo_root=repo_root)


def _sync_verifier_failure(
    *,
    project: str,
    experiment_id: str,
    root_cause: str,
    artifact_refs: list[str],
    repo_root: Path | None = None,
) -> None:
    _, state = load_machine_state(project, repo_root=repo_root)
    state.update(
        {
            "current_phase": "F1 bounded verifier",
            "current_task": "Repair the shared-shell F1 verifier contract before trusting any F1 vs control comparison.",
            "current_blocker": root_cause,
            "current_capability_boundary": "The verifier path failed, so the platform still lacks a fair F1 vs control comparison.",
            "next_priority_action": "Fix the freshness or shared-shell verifier contract and rerun f1_verify.",
            "last_verified_capability": state.get("last_verified_capability", "none"),
            "last_failed_capability": root_cause,
            "configured_subagent_gate_mode": "OFF",
            "effective_subagent_gate_mode": "OFF",
            "effective_subagent_gate_reason": "The verifier failed before a trustworthy compare result existed; keep serial repair until the contract is stable.",
        }
    )
    save_machine_state(project, state, repo_root=repo_root)
    sync_research_memory(
        project,
        durable_facts=list(state.get("durable_facts", []) or []),
        negative_memory=_dedupe(
            list(state.get("negative_memory", []) or [])
            + ["Do not trust any F1 vs control conclusion while the shared-shell verifier contract is failing."]
        ),
        next_step_memory=_dedupe(
            ["Fix the F1 verifier contract and rerun it before reopening any broader search.", *list(state.get("next_step_memory", []) or [])]
        )[:5],
        repo_root=repo_root,
    )
    update_hypothesis_queue(
        project,
        [
            {
                "status": "blocked",
                "hypothesis": "A bounded verifier should compare F1 against the control branch before any broader search is reopened.",
            },
            {
                "status": "pending",
                "hypothesis": "F2 and R1 scouting must remain closed until the shared-shell F1 verifier is stable.",
            },
        ],
        repo_root=repo_root,
    )
    record_failure(
        project,
        {
            "timestamp": _utc_now(),
            "experiment_id": experiment_id,
            "summary": "F1 bounded verifier failed.",
            "root_cause": root_cause,
            "corrective_action": "Repair the freshness or compare-shell contract before rerunning the verifier.",
            "resolution_status": "not_fixed",
        },
        repo_root=repo_root,
        append_ledger=True,
        ledger_entry={
            "timestamp": _utc_now(),
            "experiment_id": experiment_id,
            "hypothesis": "F1 should beat the control branch on the same core universe under one shared TopN shell.",
            "result": "failed",
            "blockers": [root_cause],
            "artifact_refs": artifact_refs,
        },
        preserve_progress=True,
    )
    write_verify_snapshot(
        project,
        {
            "passed_commands": [],
            "failed_commands": [f"python -m quant_mvp f1_verify --project {project}"],
            "default_project_data_status": state.get("default_project_data_status", "unknown"),
            "conclusion_boundary_engineering": "The verifier interface exists, but this run failed before it produced a trustworthy result.",
            "conclusion_boundary_research": "No new F1 vs control conclusion should be trusted from this failed verifier run.",
            "last_verified_capability": state.get("last_verified_capability"),
        },
        repo_root=repo_root,
    )
    generate_handoff(project, repo_root=repo_root)


def run_f1_verify(project: str, *, config_path: Path | None = None, repo_root: Path | None = None) -> dict[str, Any]:
    cfg, paths = load_config(project, config_path=config_path)
    if repo_root is not None:
        paths = resolve_project_paths(project, root=repo_root)
    paths.ensure_dirs()

    core_snapshot = load_latest_core_pool_snapshot(
        project,
        repo_root=repo_root,
        build_if_missing=False,
        config_path=config_path,
    )
    if core_snapshot is None or not core_snapshot.codes:
        raise RuntimeError("F1 verifier requires an existing core pool snapshot.")

    experiment_id = f"{project}__factor_elasticnet_core_verify__{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
    experiment: Experiment | None = None
    try:
        f1_experiment = _load_latest_f1_experiment(project, repo_root=repo_root)
        f1_report = _load_f1_train_report(paths)
        topk = _validate_freshness(
            cfg=cfg,
            paths=paths,
            core_snapshot=core_snapshot,
            f1_experiment=f1_experiment,
            f1_report=f1_report,
        )

        f1_rank_path = paths.signals_dir / f"f1_elasticnet_rank_top{topk}.parquet"
        f1_rank = pd.read_parquet(f1_rank_path).copy()
        f1_rank["date"] = pd.to_datetime(f1_rank["date"])
        f1_rank["code"] = f1_rank["code"].astype(str).str.zfill(6)
        f1_rank["rank"] = f1_rank["rank"].astype(int)
        f1_rank = f1_rank.loc[:, ["date", "code", "score", "rank"]].sort_values(["date", "rank", "code"]).reset_index(drop=True)

        hypothesis = "F1 should beat the control branch on the same core universe under one shared TopN shell."
        experiment = new_experiment(
            project=project,
            experiment_id=experiment_id,
            hypothesis=hypothesis,
            mode="f1_verify",
            plan_steps=["freshness_check", "control_rank", "shared_shell_backtest", "verifier_report"],
            success_criteria=[
                "The verifier must compare F1 and baseline_limit_up on the same core universe and shared TopN shell.",
                "The verifier must write a formal experiment record, report artifacts, and tracked memory updates.",
            ],
            universe_snapshot=f1_experiment.universe_snapshot,
            dataset_snapshot=f1_experiment.dataset_snapshot,
            opportunity_spec=f1_experiment.opportunity_spec,
            subagent_tasks=[],
            factor_candidates=f1_experiment.factor_candidates,
            feature_view=f1_experiment.feature_view,
            label_spec=f1_experiment.label_spec,
            model_candidate=f1_experiment.model_candidate,
            regime_spec=f1_experiment.regime_spec,
            mission_id=f1_experiment.mission_id,
            branch_id="factor_elasticnet_core",
            core_universe_snapshot_id=core_snapshot.snapshot_id,
            branch_pool_snapshot_id=f1_experiment.branch_pool_snapshot_id,
            opportunity_generator_id=f1_experiment.opportunity_generator_id,
            strategy_candidate_id="f1_elasticnet_v1",
        )
        write_experiment_record(experiment, repo_root=repo_root)

        control_rank = _build_control_rank(cfg=cfg, core_codes=list(core_snapshot.codes))
        f1_shared, control_shared = _intersect_rank_frames(f1_rank=f1_rank, control_rank=control_rank)

        control_rank_output = paths.signals_dir / f"f1_control_rank_top{topk}_common_shell.parquet"
        control_shared.to_parquet(control_rank_output, index=False)

        all_codes = sorted(set(f1_shared["code"].tolist()) | set(control_shared["code"].tolist()))
        start = min(pd.Timestamp(f1_shared["date"].min()), pd.Timestamp(control_shared["date"].min()))
        end = max(pd.Timestamp(f1_shared["date"].max()), pd.Timestamp(control_shared["date"].max()))
        close_panel = _load_shared_close_panel(cfg=cfg, codes=all_codes, start=start, end=end)
        bt_cfg = _shared_backtest_config(cfg)
        f1_curves, f1_metrics_df = run_topn_suite(close_panel=close_panel, rank_df=f1_shared, cfg=bt_cfg, topn_max=topk)
        control_curves, control_metrics_df = run_topn_suite(
            close_panel=close_panel,
            rank_df=control_shared,
            cfg=bt_cfg,
            topn_max=topk,
        )

        f1_metrics = _topk_metrics(f1_metrics_df, topk=topk)
        control_metrics = _topk_metrics(control_metrics_df, topk=topk)
        decision_payload = _decision_from_metrics(f1_metrics=f1_metrics, control_metrics=control_metrics)
        native_shell_reference = _load_native_shell_reference(paths, f1_report)

        metrics_output = paths.artifacts_dir / "f1" / "f1_vs_control_common_shell_metrics.csv"
        metrics_output.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(
            [
                {"series": "f1", **f1_metrics},
                {"series": "control", **control_metrics},
                {"series": "delta", **decision_payload["delta_metrics"]},
            ]
        ).to_csv(metrics_output, index=False, encoding="utf-8-sig")
        plot_output = _save_compare_plot(
            f1_curves=f1_curves,
            control_curves=control_curves,
            topk=topk,
            output_path=paths.artifacts_dir / "f1" / "f1_vs_control_common_shell.png",
            project=project,
        )

        report = {
            "project": project,
            "generated_at": _utc_now(),
            "hypothesis": hypothesis,
            "core_snapshot_id": core_snapshot.snapshot_id,
            "source_f1_experiment_id": f1_experiment.experiment_id,
            "compare_shell": "topn_suite_no_stoploss_v1",
            "date_intersection_start": start.strftime("%Y-%m-%d"),
            "date_intersection_end": end.strftime("%Y-%m-%d"),
            "topk": topk,
            "f1_metrics": f1_metrics,
            "control_metrics": control_metrics,
            "delta_metrics": decision_payload["delta_metrics"],
            "decision": decision_payload["decision"],
            "classification": decision_payload["classification"],
            "next_action": decision_payload["next_action"],
            "primary_blockers": decision_payload["primary_blockers"],
            "next_experiment_themes": decision_payload["next_experiment_themes"],
            "native_shell_reference": native_shell_reference,
            "artifact_paths": {
                "source_f1_experiment_path": str(paths.experiments_dir / f"{f1_experiment.experiment_id}.json"),
                "source_f1_rank_path": str(f1_rank_path),
                "control_rank_path": str(control_rank_output),
                "metrics_csv_path": str(metrics_output),
                "plot_path": str(plot_output),
            },
        }
        verifier_json_path, verifier_md_path = _write_verifier_report(paths=paths, report=report)
        report["artifact_paths"]["verifier_json_path"] = str(verifier_json_path)
        report["artifact_paths"]["verifier_md_path"] = str(verifier_md_path)
        verifier_json_path, verifier_md_path = _write_verifier_report(paths=paths, report=report)

        summary = (
            "F1 beats the control branch strongly enough under the shared TopN shell."
            if decision_payload["decision"] == "keep_f1_mainline"
            else "F1 did not beat the control branch strongly enough under the shared TopN shell."
        )
        evaluation = EvaluationRecord(
            status="f1_bounded_verifier",
            summary=summary,
            classification=decision_payload["classification"],
            primary_blockers=list(decision_payload["primary_blockers"]),
            promotion_decision={"evaluated": False, "reason": "bounded_verifier_only", "decision": decision_payload["decision"]},
            next_experiment_themes=list(decision_payload["next_experiment_themes"]),
            adversarial_robustness={"status": "not_evaluated", "score": None},
            regime_transition_drawdown=None,
        )
        execution = {
            "executed_steps": list(experiment.plan_steps),
            "outputs": {
                "freshness_check": {
                    "source_f1_experiment_id": f1_experiment.experiment_id,
                    "core_snapshot_id": core_snapshot.snapshot_id,
                    "profile": _factor_model_config(cfg).profile,
                },
                "control_rank": {"path": str(control_rank_output), "date_count": int(control_shared["date"].nunique())},
                "shared_shell_backtest": {
                    "metrics_path": str(metrics_output),
                    "plot_path": str(plot_output),
                    "date_intersection_start": report["date_intersection_start"],
                    "date_intersection_end": report["date_intersection_end"],
                },
                "verifier_report": {"json_path": str(verifier_json_path), "md_path": str(verifier_md_path)},
            },
        }
        experiment = update_experiment(
            experiment,
            status="evaluated",
            execution=execution,
            evaluation=evaluation,
            artifact_refs=[
                str(control_rank_output),
                str(metrics_output),
                str(plot_output),
                str(verifier_json_path),
                str(verifier_md_path),
            ],
        )
        experiment_path = write_experiment_record(experiment, repo_root=repo_root)
        report["artifact_paths"]["experiment_record_path"] = str(experiment_path)
        verifier_json_path, verifier_md_path = _write_verifier_report(paths=paths, report=report)
        update_run_manifest(
            project,
            {
                "f1_verifier": {
                    "core_snapshot_id": core_snapshot.snapshot_id,
                    "source_f1_experiment_id": f1_experiment.experiment_id,
                    "control_rank_path": str(control_rank_output),
                    "metrics_path": str(metrics_output),
                    "plot_path": str(plot_output),
                    "verifier_json_path": str(verifier_json_path),
                    "verifier_md_path": str(verifier_md_path),
                    "experiment_record_path": str(experiment_path),
                    "decision": decision_payload["decision"],
                    "classification": decision_payload["classification"],
                }
            },
        )
        _sync_verifier_memory(
            project=project,
            decision_payload=decision_payload,
            topk=topk,
            experiment_id=experiment_id,
            verifier_json_path=verifier_json_path,
            verifier_md_path=verifier_md_path,
            f1_metrics=f1_metrics,
            report=report,
            repo_root=repo_root,
        )
        return {
            "experiment_id": experiment_id,
            "experiment_record_path": str(experiment_path),
            "verifier_json_path": str(verifier_json_path),
            "verifier_md_path": str(verifier_md_path),
            "control_rank_path": str(control_rank_output),
            "metrics_path": str(metrics_output),
            "plot_path": str(plot_output),
            "decision": decision_payload["decision"],
            "classification": decision_payload["classification"],
            "next_action": decision_payload["next_action"],
            "f1_metrics": f1_metrics,
            "control_metrics": control_metrics,
            "delta_metrics": decision_payload["delta_metrics"],
        }
    except Exception as exc:
        artifact_refs: list[str] = []
        if experiment is not None:
            evaluation = EvaluationRecord(
                status="failed",
                summary=f"F1 bounded verifier failed: {exc}",
                classification="verifier_fail",
                primary_blockers=[str(exc)],
                promotion_decision={"evaluated": False, "reason": "verifier_failed"},
                next_experiment_themes=["Repair the verifier freshness or shared-shell contract before rerunning it."],
                adversarial_robustness={"status": "not_evaluated", "score": None},
                regime_transition_drawdown=None,
            )
            experiment = update_experiment(
                experiment,
                status="failed",
                execution={"executed_steps": ["freshness_check"]},
                evaluation=evaluation,
            )
            experiment_path = write_experiment_record(experiment, repo_root=repo_root)
            artifact_refs.append(str(experiment_path))
        _sync_verifier_failure(
            project=project,
            experiment_id=experiment_id,
            root_cause=str(exc),
            artifact_refs=artifact_refs,
            repo_root=repo_root,
        )
        raise
