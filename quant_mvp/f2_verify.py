from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from .backtest_engine import run_topn_suite
from .config import load_config
from .experiment_graph import (
    EvaluationRecord,
    Experiment,
    new_experiment,
    read_experiment_record,
    update_experiment,
    write_experiment_record,
)
from .f1_verify import (
    _build_control_rank,
    _dedupe,
    _expected_compare_topk,
    _load_f1_train_report,
    _load_latest_f1_experiment,
    _load_shared_close_panel,
    _shared_backtest_config,
    _topk_metrics,
    _validate_freshness,
)
from .f2_pipeline import (
    _deep_factor_model_config,
    _feature_view,
    build_f2_training_contract_hash,
)
from .manifest import update_run_manifest
from .memory.ledger import stable_hash, to_jsonable
from .memory.writeback import (
    generate_handoff,
    load_machine_state,
    record_experiment_result,
    record_failure,
    save_machine_state,
    sync_research_memory,
    update_hypothesis_queue,
    write_verify_snapshot,
)
from .pools import load_latest_core_pool_snapshot
from .project import resolve_project_paths


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _load_latest_f2_experiment(project: str, *, repo_root: Path | None = None) -> Experiment:
    paths = resolve_project_paths(project, root=repo_root)
    if not paths.experiments_dir.exists():
        raise RuntimeError("No experiment records exist for this project; rerun f2_train first.")
    records = sorted(paths.experiments_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    for path in records:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if (
            str(payload.get("mode", "")) == "f2_train"
            and str(payload.get("branch_id", "")) == "factor_elasticnet_core"
            and str(payload.get("strategy_candidate_id", "")) == "f2_structured_latent_factor_v1"
        ):
            status = str(payload.get("status", "")).strip()
            evaluation = dict(payload.get("evaluation", {}) or {})
            classification = str(evaluation.get("classification", "")).strip()
            if status != "evaluated" or classification != "prototype_deep_factor_result":
                raise RuntimeError(
                    "The latest F2 training attempt did not finish successfully; rerun f2_train first."
                )
            return read_experiment_record(project, str(payload["experiment_id"]), repo_root=repo_root)
    raise RuntimeError("No latest F2 training experiment was found; rerun f2_train first.")


def _load_f2_train_report(paths) -> dict[str, Any]:
    report_path = paths.artifacts_dir / "f2" / "F2_TRAIN_REPORT.json"
    if not report_path.exists():
        raise RuntimeError("Latest F2 train report is missing; rerun f2_train first.")
    return json.loads(report_path.read_text(encoding="utf-8"))


def _validate_f2_freshness(
    *,
    cfg: dict[str, Any],
    paths,
    core_snapshot,
    f2_experiment: Experiment,
    f2_report: dict[str, Any],
) -> int:
    model_cfg = _deep_factor_model_config(cfg)
    expected_topk = _expected_compare_topk(cfg)
    expected_feature_view = _feature_view(model_cfg, str(cfg.get("freq", "1d"))).name
    expected_cfg_hash = build_f2_training_contract_hash(
        cfg=cfg,
        model_cfg=model_cfg,
        core_snapshot_id=str(core_snapshot.snapshot_id),
    )
    rank_path = paths.signals_dir / f"f2_structured_latent_rank_top{expected_topk}.parquet"
    latent_path = paths.features_dir / "f2_latent_factor_frame_v1.parquet"

    mismatch_reasons: list[str] = []
    if str(f2_experiment.core_universe_snapshot_id or "") != str(core_snapshot.snapshot_id):
        mismatch_reasons.append("core_universe_snapshot_id mismatch")
    if str(f2_report.get("core_snapshot_id", "")) != str(core_snapshot.snapshot_id):
        mismatch_reasons.append("f2_train_report core_snapshot_id mismatch")
    if str(f2_report.get("profile", "")) != str(model_cfg.profile):
        mismatch_reasons.append("deep_factor_model.profile mismatch")
    if str(f2_report.get("train_cfg_hash", "")) != expected_cfg_hash:
        mismatch_reasons.append("train_cfg_hash mismatch")
    if str((f2_experiment.feature_view.name if f2_experiment.feature_view else "")) != expected_feature_view:
        mismatch_reasons.append("feature_view.name mismatch")
    if int(f2_report.get("topk", -1)) != int(expected_topk):
        mismatch_reasons.append("topk mismatch")
    if str(f2_report.get("experiment_id", "")) != str(f2_experiment.experiment_id):
        mismatch_reasons.append("f2_train_report experiment_id mismatch")
    if not rank_path.exists():
        mismatch_reasons.append(f"missing rank artifact: {rank_path.name}")
    if not latent_path.exists():
        mismatch_reasons.append(f"missing latent artifact: {latent_path.name}")

    if mismatch_reasons:
        raise RuntimeError(
            "Latest F2 artifacts do not match the current core snapshot/profile/topk; rerun f2_train first. "
            + "; ".join(mismatch_reasons)
        )
    return expected_topk


def _validate_rank_frame(*, name: str, rank_df: pd.DataFrame, topk: int) -> dict[str, int]:
    required_columns = {"date", "code", "score", "rank"}
    missing = required_columns.difference(rank_df.columns)
    if missing:
        raise RuntimeError(f"{name} rank frame is missing required columns: {sorted(missing)}")
    if rank_df.empty:
        raise RuntimeError(f"{name} rank frame is empty.")
    if rank_df[["date", "code"]].duplicated().any():
        raise RuntimeError(f"{name} rank frame has duplicate (date, code) rows.")
    if rank_df[["date", "rank"]].duplicated().any():
        raise RuntimeError(f"{name} rank frame has duplicate (date, rank) rows.")
    rank_values = rank_df["rank"].astype(int)
    if (rank_values < 1).any() or (rank_values > topk).any():
        raise RuntimeError(f"{name} rank frame contains rank values outside 1..{topk}.")
    rows_per_date = rank_df.groupby("date")["code"].size()
    if (rows_per_date > topk).any():
        raise RuntimeError(f"{name} rank frame has more than topk rows on at least one date.")
    return {
        "date_count": int(rows_per_date.shape[0]),
        "min_rows_per_date": int(rows_per_date.min()),
        "max_rows_per_date": int(rows_per_date.max()),
        "row_count": int(rank_df.shape[0]),
    }


def _intersect_three_rank_frames(
    *,
    control_rank: pd.DataFrame,
    f1_rank: pd.DataFrame,
    f2_rank: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    shared_dates = sorted(
        set(pd.to_datetime(control_rank["date"]))
        & set(pd.to_datetime(f1_rank["date"]))
        & set(pd.to_datetime(f2_rank["date"]))
    )
    if not shared_dates:
        raise RuntimeError("No shared rebalance dates exist across control, F1, and F2.")
    control_shared = control_rank.loc[control_rank["date"].isin(shared_dates)].copy()
    f1_shared = f1_rank.loc[f1_rank["date"].isin(shared_dates)].copy()
    f2_shared = f2_rank.loc[f2_rank["date"].isin(shared_dates)].copy()
    if control_shared.empty or f1_shared.empty or f2_shared.empty:
        raise RuntimeError("The F2 verifier produced an empty rank frame after date intersection.")
    sorter = ["date", "rank", "code"]
    return (
        control_shared.sort_values(sorter).reset_index(drop=True),
        f1_shared.sort_values(sorter).reset_index(drop=True),
        f2_shared.sort_values(sorter).reset_index(drop=True),
    )


def _delta_metrics(*, base_metrics: dict[str, Any], challenger_metrics: dict[str, Any]) -> dict[str, float]:
    return {
        "total_return_delta": float(challenger_metrics.get("total_return", 0.0) or 0.0)
        - float(base_metrics.get("total_return", 0.0) or 0.0),
        "annualized_return_delta": float(challenger_metrics.get("annualized_return", 0.0) or 0.0)
        - float(base_metrics.get("annualized_return", 0.0) or 0.0),
        "sharpe_ratio_delta": float(challenger_metrics.get("sharpe_ratio", 0.0) or 0.0)
        - float(base_metrics.get("sharpe_ratio", 0.0) or 0.0),
        "max_drawdown_improvement": abs(float(base_metrics.get("max_drawdown", 0.0) or 0.0))
        - abs(float(challenger_metrics.get("max_drawdown", 0.0) or 0.0)),
        "calmar_ratio_delta": float(challenger_metrics.get("calmar_ratio", 0.0) or 0.0)
        - float(base_metrics.get("calmar_ratio", 0.0) or 0.0),
        "win_rate_delta": float(challenger_metrics.get("win_rate", 0.0) or 0.0)
        - float(base_metrics.get("win_rate", 0.0) or 0.0),
    }


def _decision_from_metrics(*, f1_metrics: dict[str, Any], f2_metrics: dict[str, Any]) -> dict[str, Any]:
    deltas = _delta_metrics(base_metrics=f1_metrics, challenger_metrics=f2_metrics)
    primary_blockers: list[str] = []
    if deltas["calmar_ratio_delta"] <= 0.0:
        primary_blockers.append(f"f2_calmar_ratio_delta {deltas['calmar_ratio_delta']:.4f} is not positive.")
    if deltas["annualized_return_delta"] < -0.02:
        primary_blockers.append(
            f"f2_annualized_return_delta {deltas['annualized_return_delta']:.2%} is below the allowed -2.00% floor."
        )
    if deltas["max_drawdown_improvement"] < 0.03:
        primary_blockers.append(
            f"f2_drawdown_improvement {deltas['max_drawdown_improvement']:.2%} is below the required 3.00% improvement."
        )
    if deltas["sharpe_ratio_delta"] < -0.05:
        primary_blockers.append(
            f"f2_sharpe_ratio_delta {deltas['sharpe_ratio_delta']:.4f} is below the allowed -0.05 floor."
        )

    if deltas["calmar_ratio_delta"] > 0.0 and deltas["annualized_return_delta"] >= -0.02:
        decision = "keep_f2_challenger"
        classification = "verifier_mixed"
        next_action = "run_one_more_bounded_f2_variant"
        if deltas["max_drawdown_improvement"] >= 0.03 and deltas["sharpe_ratio_delta"] >= -0.05:
            decision = "promote_f2_next"
            classification = "verifier_pass"
            next_action = "advance_f2_as_next_challenger"
    else:
        decision = "reject_f2_v1_and_retain_f1_mainline"
        classification = "verifier_mixed" if any(value > 0 for value in deltas.values()) else "verifier_fail"
        next_action = "reselect_next_challenger_after_f2_failure"

    return {
        "decision": decision,
        "classification": classification,
        "next_action": next_action,
        "primary_blockers": _dedupe(primary_blockers),
        "delta_metrics_vs_f1": deltas,
    }


def _save_compare_plot(
    *,
    project: str,
    topk: int,
    control_curves: pd.DataFrame,
    f1_curves: pd.DataFrame,
    f2_curves: pd.DataFrame,
    output_path: Path,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure, axis = plt.subplots(figsize=(10, 5))
    control_equity = control_curves[f"Top{topk}"].astype(float)
    f1_equity = f1_curves[f"Top{topk}"].astype(float)
    f2_equity = f2_curves[f"Top{topk}"].astype(float)
    axis.plot(control_equity.index, control_equity / float(control_equity.iloc[0]), label=f"Control Top{topk}", linewidth=1.8)
    axis.plot(f1_equity.index, f1_equity / float(f1_equity.iloc[0]), label=f"F1 Top{topk}", linewidth=1.8)
    axis.plot(f2_equity.index, f2_equity / float(f2_equity.iloc[0]), label=f"F2 Top{topk}", linewidth=1.8)
    axis.set_title(f"{project}: F2 vs F1 vs control under shared TopN shell")
    axis.set_ylabel("Normalized equity")
    axis.grid(alpha=0.25)
    axis.legend()
    figure.autofmt_xdate()
    figure.tight_layout()
    figure.savefig(output_path, dpi=150)
    plt.close(figure)
    return output_path


def _write_report(*, output_dir: Path, report: dict[str, Any]) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "F2_BOUNDED_VERIFIER.json"
    md_path = output_dir / "F2_BOUNDED_VERIFIER.md"
    json_path.write_text(json.dumps(to_jsonable(report), ensure_ascii=False, indent=2).rstrip() + "\n", encoding="utf-8")

    blockers = list(report.get("primary_blockers", []) or [])
    lines = [
        "# F2 Bounded Verifier",
        "",
        f"- project: `{report['project']}`",
        f"- generated_at: `{report['generated_at']}`",
        f"- core_snapshot_id: `{report['core_snapshot_id']}`",
        f"- source_f1_experiment_id: `{report['source_f1_experiment_id']}`",
        f"- source_f2_experiment_id: `{report['source_f2_experiment_id']}`",
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
        "## F2 Metrics",
        *(f"- `{key}`: `{value}`" for key, value in dict(report.get("f2_metrics", {}) or {}).items()),
        "",
        "## Control Metrics",
        *(f"- `{key}`: `{value}`" for key, value in dict(report.get("control_metrics", {}) or {}).items()),
        "",
        "## Delta vs F1",
        *(f"- `{key}`: `{value}`" for key, value in dict(report.get("delta_metrics_vs_f1", {}) or {}).items()),
        "",
        "## Primary Blockers",
        *([f"- {item}" for item in blockers] or ["- none"]),
        "",
        "## Artifact Paths",
        *(f"- `{key}`: `{value}`" for key, value in dict(report.get("artifact_paths", {}) or {}).items()),
    ]
    md_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return json_path, md_path


def _refresh_strategy_candidates(
    *,
    state: dict[str, Any],
    topk: int,
    f1_metrics: dict[str, Any],
    f2_metrics: dict[str, Any],
    decision_payload: dict[str, Any],
    artifact_refs: list[str],
) -> list[dict[str, Any]]:
    current = [dict(item) for item in list(state.get("strategy_candidates", []) or []) if isinstance(item, dict)]
    updated: list[dict[str, Any]] = []
    saw_f1 = False
    saw_f2 = False
    for item in current:
        strategy_id = str(item.get("strategy_id", "")).strip()
        candidate = dict(item)
        if strategy_id == "f1_elasticnet_v1":
            saw_f1 = True
            candidate["track"] = "primary"
            candidate["decision"] = "continue"
            candidate["current_stage"] = "validation"
            candidate["latest_action"] = "Completed one shared-shell verifier against F2.1 and the control branch."
            candidate["latest_result"] = (
                f"F1 shared-shell Top{topk}: annualized_return={float(f1_metrics.get('annualized_return', 0.0)):.2%}, "
                f"max_drawdown={abs(float(f1_metrics.get('max_drawdown', 0.0))):.2%}, "
                f"sharpe={float(f1_metrics.get('sharpe_ratio', 0.0)):.4f}."
            )
            candidate["next_validation"] = (
                "Keep F1 as mainline and advance F2.1 as the next bounded challenger."
                if decision_payload["decision"] == "promote_f2_next"
                else (
                    "Keep F1 as mainline while F2.1 stays a bounded challenger."
                    if decision_payload["decision"] == "keep_f2_challenger"
                    else "Keep F1 as mainline and reselect the next challenger after F2.1 failed."
                )
            )
            candidate["artifact_refs"] = _dedupe(list(candidate.get("artifact_refs", []) or []) + artifact_refs)
        elif strategy_id == "f2_structured_latent_factor_v1":
            saw_f2 = True
            candidate["track"] = "secondary"
            candidate["decision"] = (
                "promote"
                if decision_payload["decision"] == "promote_f2_next"
                else ("continue" if decision_payload["decision"] == "keep_f2_challenger" else "reject")
            )
            candidate["current_stage"] = "validation"
            candidate["latest_action"] = "Completed one bounded structured-latent shared-shell verifier."
            candidate["latest_result"] = (
                f"F2.1 shared-shell Top{topk}: annualized_return={float(f2_metrics.get('annualized_return', 0.0)):.2%}, "
                f"max_drawdown={abs(float(f2_metrics.get('max_drawdown', 0.0))):.2%}, "
                f"sharpe={float(f2_metrics.get('sharpe_ratio', 0.0)):.4f}; decision={decision_payload['decision']}."
            )
            candidate["next_validation"] = (
                "Advance F2.1 as the next bounded challenger."
                if decision_payload["decision"] == "promote_f2_next"
                else (
                    "Run one more bounded F2.1 variant before any wider model search."
                    if decision_payload["decision"] == "keep_f2_challenger"
                    else "Reject F2.1 v1 and reselect the next challenger."
                )
            )
            candidate["blocked_by"] = list(decision_payload.get("primary_blockers", []) or [])
            candidate["artifact_refs"] = _dedupe(list(candidate.get("artifact_refs", []) or []) + artifact_refs)
        updated.append(candidate)

    if not saw_f1:
        updated.append(
            {
                "strategy_id": "f1_elasticnet_v1",
                "name": "F1 ElasticNet Mainline",
                "category": "factor_model",
                "core_hypothesis": "A regularized cross-sectional factor model should outperform the legacy control branch on the same core universe.",
                "economic_rationale": "F1 remains the verified mainline while challengers are compared under one fair shell.",
                "required_data": "Core universe snapshot, technical/liquidity feature panel, next_5d_excess_return label, shared-shell TopN backtest.",
                "current_stage": "validation",
                "latest_action": "Completed one shared-shell verifier against F2.1 and the control branch.",
                "latest_result": (
                    f"F1 shared-shell Top{topk}: annualized_return={float(f1_metrics.get('annualized_return', 0.0)):.2%}, "
                    f"max_drawdown={abs(float(f1_metrics.get('max_drawdown', 0.0))):.2%}, "
                    f"sharpe={float(f1_metrics.get('sharpe_ratio', 0.0)):.4f}."
                ),
                "decision": "continue",
                "next_validation": "Keep F1 as the verified mainline while the next challenger path is decided.",
                "owner": "main",
                "subagents_assigned": [],
                "artifact_refs": [],
                "blocked_by": [],
                "track": "primary",
            }
        )
    if not saw_f2:
        updated.append(
            {
                "strategy_id": "f2_structured_latent_factor_v1",
                "name": "F2.1 Structured Latent Factor",
                "category": "deep_factor_model",
                "core_hypothesis": "A small structured latent factor model can improve F1's return/drawdown tradeoff without heavy dependencies.",
                "economic_rationale": "F2.1 reuses the F1 contract but adds a bounded latent bottleneck to test whether a richer non-linear representation helps.",
                "required_data": "Core universe snapshot, F1-compatible excess-return label, technical/liquidity feature panel plus structured group blocks.",
                "current_stage": "validation",
                "latest_action": "Completed one bounded structured-latent shared-shell verifier.",
                "latest_result": (
                    f"F2.1 shared-shell Top{topk}: annualized_return={float(f2_metrics.get('annualized_return', 0.0)):.2%}, "
                    f"max_drawdown={abs(float(f2_metrics.get('max_drawdown', 0.0))):.2%}, "
                    f"sharpe={float(f2_metrics.get('sharpe_ratio', 0.0)):.4f}; decision={decision_payload['decision']}."
                ),
                "decision": (
                    "promote"
                    if decision_payload["decision"] == "promote_f2_next"
                    else ("continue" if decision_payload["decision"] == "keep_f2_challenger" else "reject")
                ),
                "next_validation": (
                    "Advance F2.1 as the next bounded challenger."
                    if decision_payload["decision"] == "promote_f2_next"
                    else (
                        "Run one more bounded F2.1 variant before any wider model search."
                        if decision_payload["decision"] == "keep_f2_challenger"
                        else "Reject F2.1 v1 and reselect the next challenger."
                    )
                ),
                "owner": "main",
                "subagents_assigned": [],
                "artifact_refs": list(artifact_refs),
                "blocked_by": list(decision_payload.get("primary_blockers", []) or []),
                "kill_criteria": "If F2.1 cannot improve F1's tradeoff under the same shared shell, it should not remain the next challenger.",
                "track": "secondary",
            }
        )
    return updated


def _write_frontier_next_step_decision(*, paths, report: dict[str, Any], decision_payload: dict[str, Any]) -> None:
    if decision_payload["decision"] == "promote_f2_next":
        text = "\n".join(
            [
                "# Frontier Next Step Decision",
                "",
                "## Current Bottleneck",
                "- F1 remains the mainline, but the platform still needs a stronger bounded challenger to improve the return/drawdown tradeoff.",
                f"- The latest shared-shell verifier promoted `F2.1` after comparing `control / F1 / F2.1` on `{report['core_snapshot_id']}`.",
                "",
                "## Result",
                "- winner: `F2.1`",
                "- runner-up: `F1 mainline as reference`",
                "- deferred: `frontier reselection not needed yet`",
                "",
                "## Evidence",
                f"- decision: `{decision_payload['decision']}`",
                f"- F1 annualized_return: `{float(report['f1_metrics'].get('annualized_return', 0.0)):.2%}`",
                f"- F2 annualized_return: `{float(report['f2_metrics'].get('annualized_return', 0.0)):.2%}`",
                f"- F1 max_drawdown: `{float(report['f1_metrics'].get('max_drawdown', 0.0)):.2%}`",
                f"- F2 max_drawdown: `{float(report['f2_metrics'].get('max_drawdown', 0.0)):.2%}`",
                "",
                "## Next Build Scope",
                "- Keep `F1` as the verified mainline.",
                "- Advance `F2.1` as the next bounded challenger family.",
                "- Do not claim profitability or promotion readiness from this verifier alone.",
                "",
                "## Artifact",
                f"- verifier_report: `{report['artifact_paths']['report_json_path']}`",
            ]
        )
    else:
        text = "\n".join(
            [
                "# Frontier Next Step Decision",
                "",
                "## Current Bottleneck",
                "- `F2.1` did not improve the `F1` tradeoff strongly enough under the same shared shell.",
                "- `F1` remains the only current mainline, and the next challenger now needs reselection.",
                "",
                "## Result",
                "- winner: `frontier_reselection_required`",
                "- runner-up: `F1 mainline stays active`",
                "- rejected_this_round: `F2.1`",
                "",
                "## Evidence",
                f"- decision: `{decision_payload['decision']}`",
                *[f"- blocker: `{item}`" for item in list(decision_payload.get("primary_blockers", []) or [])],
                f"- verifier_report: `{report['artifact_paths']['report_json_path']}`",
                "",
                "## Next Build Scope",
                "- Keep `F1` as the current mainline.",
                "- Do one new bounded frontier reselection before choosing the next challenger.",
                "- Do not quietly widen dependencies or keep tuning `F2.1 v1.x` without a new explicit selection step.",
                "",
                "## Deferred Backlog",
                "- `Hybrid F1.5`",
                "- `R-family overlays beyond bounded prototypes`",
            ]
        )
    paths.memory_dir.joinpath("FRONTIER_NEXT_STEP_DECISION.md").write_text(text.rstrip() + "\n", encoding="utf-8")


def _append_repo_decision_log(*, repo_root: Path, project: str, report: dict[str, Any], decision_payload: dict[str, Any]) -> None:
    path = repo_root / "docs" / "DECISION_LOG.md"
    existing = path.read_text(encoding="utf-8").rstrip() if path.exists() else "# Decision Log"
    lines = [
        "",
        f"## {_utc_now()} | {project} | {decision_payload['decision']}",
        f"- source: `{report['artifact_paths']['report_json_path']}`",
        f"- summary: F2.1 verifier decision is `{decision_payload['decision']}` after a shared-shell comparison versus control and F1.",
        f"- F1 annualized_return: `{float(report['f1_metrics'].get('annualized_return', 0.0)):.2%}`",
        f"- F2 annualized_return: `{float(report['f2_metrics'].get('annualized_return', 0.0)):.2%}`",
        f"- F1 max_drawdown: `{float(report['f1_metrics'].get('max_drawdown', 0.0)):.2%}`",
        f"- F2 max_drawdown: `{float(report['f2_metrics'].get('max_drawdown', 0.0)):.2%}`",
    ]
    path.write_text((existing + "\n" + "\n".join(lines)).rstrip() + "\n", encoding="utf-8")


def _sync_f2_memory(
    *,
    project: str,
    topk: int,
    experiment_id: str,
    decision_payload: dict[str, Any],
    report: dict[str, Any],
    report_json_path: Path,
    report_md_path: Path,
    f1_metrics: dict[str, Any],
    f2_metrics: dict[str, Any],
    repo_root: Path | None = None,
) -> None:
    _, state = load_machine_state(project, repo_root=repo_root)
    max_drawdown = abs(float(f2_metrics.get("max_drawdown", 0.0) or 0.0))
    blocker = "none"
    if max_drawdown > 0.30:
        blocker = f"F2.1 shared-shell Top{topk} max_drawdown {max_drawdown:.2%} remains above 30.00%."
    if decision_payload["decision"] == "reject_f2_v1_and_retain_f1_mainline":
        blocker = "; ".join(list(decision_payload.get("primary_blockers", []) or [])) or "F2.1 failed to improve the F1 tradeoff."
    next_action = (
        "Advance F2.1 as the next bounded challenger family while keeping F1 mainline."
        if decision_payload["decision"] == "promote_f2_next"
        else (
            "Run one more bounded F2.1 variant before widening the model search."
            if decision_payload["decision"] == "keep_f2_challenger"
            else "Retain F1 mainline and reselect the next challenger after F2.1 failed."
        )
    )
    current_phase = (
        "F2.1 challenger promoted"
        if decision_payload["decision"] == "promote_f2_next"
        else ("F2.1 bounded verifier" if decision_payload["decision"] == "keep_f2_challenger" else "post-F2.1 frontier reselection required")
    )
    current_task = (
        "Advance F2.1 as the next bounded challenger while keeping F1 as the verified mainline."
        if decision_payload["decision"] == "promote_f2_next"
        else (
            "Keep F2.1 bounded and decide whether one more small variant is justified."
            if decision_payload["decision"] == "keep_f2_challenger"
            else "Retain F1 as the verified mainline and reselect the next challenger after F2.1 failed."
        )
    )
    current_capability_boundary = (
        "F2.1 is still only a bounded challenger layer; this verifier does not prove profitability or promotion readiness."
    )
    state.update(
        {
            "current_phase": current_phase,
            "current_task": current_task,
            "current_blocker": blocker,
            "current_capability_boundary": current_capability_boundary,
            "next_priority_action": next_action,
            "last_verified_capability": (
                f"F2.1 bounded verifier compared control, F1, and F2.1 on the same core universe and shared Top{topk} shell; "
                f"decision={decision_payload['decision']}."
            ),
            "last_failed_capability": "none" if blocker == "none" else blocker,
            "current_strategy_focus": (
                ["f1_elasticnet_v1", "f2_structured_latent_factor_v1"]
                if decision_payload["decision"] != "reject_f2_v1_and_retain_f1_mainline"
                else ["f1_elasticnet_v1"]
            ),
            "current_strategy_summary": (
                f"F2.1 verifier classification={decision_payload['classification']}; decision={decision_payload['decision']}."
            ),
            "configured_subagent_gate_mode": "OFF",
            "effective_subagent_gate_mode": "OFF",
            "effective_subagent_gate_reason": "F2.1 verifier is a tightly coupled compare path; serial execution stayed cheaper and safer than spawning scouts.",
            "subagent_gate_mode": "OFF",
            "subagent_continue_reason": "F2.1 verifier stayed in OFF mode because this round was a tightly coupled serial implementation.",
            "next_build_target": (
                "f2_structured_latent_factor_v1"
                if decision_payload["decision"] != "reject_f2_v1_and_retain_f1_mainline"
                else "frontier_reselection_required"
            ),
            "f2_verify_report_path": str(report_json_path),
            "f2_verify_decision": str(decision_payload["decision"]),
            "f2_verify_classification": str(decision_payload["classification"]),
            "current_rejected_strategy_ids": _dedupe(
                list(state.get("current_rejected_strategy_ids", []) or [])
                + (
                    ["f2_structured_latent_factor_v1"]
                    if decision_payload["decision"] == "reject_f2_v1_and_retain_f1_mainline"
                    else []
                )
            ),
        }
    )
    artifact_refs = [str(report_json_path), str(report_md_path)]
    state["strategy_candidates"] = _refresh_strategy_candidates(
        state=state,
        topk=topk,
        f1_metrics=f1_metrics,
        f2_metrics=f2_metrics,
        decision_payload=decision_payload,
        artifact_refs=artifact_refs,
    )
    save_machine_state(project, state, repo_root=repo_root)

    durable_facts = _dedupe(
        list(state.get("durable_facts", []) or [])
        + [
            "F2.1 is a bounded structured latent deep-factor challenger built inside the current scikit-learn stack.",
            f"The latest F2.1 verifier decision is {decision_payload['decision']}.",
        ]
    )
    negative_memory = _dedupe(
        list(state.get("negative_memory", []) or [])
        + [
            "Do not treat F2.1 verifier output as profitability proof or promotion evidence.",
            (
                "Do not keep quietly tuning F2.1 v1.x if the fair shared-shell verifier rejects it."
                if decision_payload["decision"] == "reject_f2_v1_and_retain_f1_mainline"
                else "Do not let F2.1 displace F1 mainline until the bounded verifier result is explicitly accepted."
            ),
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
    update_hypothesis_queue(
        project,
        [
            {
                "status": "active",
                "hypothesis": "F1 remains the verified mainline until a challenger improves the shared-shell tradeoff strongly enough.",
            },
            {
                "status": (
                    "active"
                    if decision_payload["decision"] in {"keep_f2_challenger", "promote_f2_next"}
                    else "blocked"
                ),
                "hypothesis": "A bounded structured latent deep-factor model can improve F1's return/drawdown tradeoff on the same core universe without heavy dependencies.",
            },
            {
                "status": (
                    "pending"
                    if decision_payload["decision"] != "reject_f2_v1_and_retain_f1_mainline"
                    else "active"
                ),
                "hypothesis": "If F2.1 fails under the shared shell, the platform should reselect the next challenger instead of widening dependencies by default.",
            },
        ],
        repo_root=repo_root,
    )
    record_experiment_result(
        project,
        {
            "timestamp": _utc_now(),
            "experiment_id": experiment_id,
            "hypothesis": report["hypothesis"],
            "config_hash": stable_hash({"core_snapshot_id": report["core_snapshot_id"], "topk": topk}),
            "result": decision_payload["classification"],
            "blockers": list(decision_payload.get("primary_blockers", []) or []),
            "artifact_refs": artifact_refs,
        },
        repo_root=repo_root,
    )
    write_verify_snapshot(
        project,
        {
            "passed_commands": [f"python -m quant_mvp f2_verify --project {project}"],
            "failed_commands": [],
            "default_project_data_status": f"latest core pool `{report['core_snapshot_id']}` stayed consistent through the F2 verifier run.",
            "conclusion_boundary_engineering": "The F2 shared-shell verifier is now runnable and writes formal experiment plus tracked memory outputs.",
            "conclusion_boundary_research": "The verifier compares F2, F1, and control fairly, but it still does not prove profitability or promotion readiness.",
            "last_verified_capability": state.get("last_verified_capability"),
        },
        repo_root=repo_root,
    )
    if decision_payload["decision"] in {"promote_f2_next", "reject_f2_v1_and_retain_f1_mainline"}:
        paths = resolve_project_paths(project, root=repo_root)
        _write_frontier_next_step_decision(paths=paths, report=report, decision_payload=decision_payload)
        if repo_root is not None:
            _append_repo_decision_log(repo_root=repo_root, project=project, report=report, decision_payload=decision_payload)
    generate_handoff(project, repo_root=repo_root)


def _sync_f2_failure(
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
            "current_phase": "F2.1 bounded verifier",
            "current_task": "Repair the F2.1 verifier contract before trusting any F2 vs F1 comparison.",
            "current_blocker": root_cause,
            "current_capability_boundary": "The F2 verifier path failed, so the platform still lacks a trustworthy F2 vs F1 vs control comparison.",
            "next_priority_action": "Fix the freshness or shared-shell verifier contract and rerun f2_verify.",
            "last_failed_capability": root_cause,
            "configured_subagent_gate_mode": "OFF",
            "effective_subagent_gate_mode": "OFF",
            "effective_subagent_gate_reason": "Keep F2 verifier repair serial until the compare contract is stable.",
            "current_strategy_focus": ["f1_elasticnet_v1", "f2_structured_latent_factor_v1"],
            "next_build_target": "f2_structured_latent_factor_v1",
        }
    )
    save_machine_state(project, state, repo_root=repo_root)
    sync_research_memory(
        project,
        durable_facts=list(state.get("durable_facts", []) or []),
        negative_memory=_dedupe(
            list(state.get("negative_memory", []) or [])
            + ["Do not trust any F2 vs F1 conclusion while the shared-shell F2 verifier contract is failing."]
        ),
        next_step_memory=_dedupe(
            ["Fix the F2 verifier contract and rerun it before reopening challenger selection.", *list(state.get("next_step_memory", []) or [])]
        )[:5],
        repo_root=repo_root,
    )
    update_hypothesis_queue(
        project,
        [
            {
                "status": "blocked",
                "hypothesis": "A bounded structured latent deep-factor model can improve F1's return/drawdown tradeoff on the same core universe without heavy dependencies.",
            },
            {
                "status": "pending",
                "hypothesis": "Repair the F2 verifier contract before any new challenger selection is attempted.",
            },
        ],
        repo_root=repo_root,
    )
    record_failure(
        project,
        {
            "timestamp": _utc_now(),
            "experiment_id": experiment_id,
            "summary": "F2 bounded verifier failed.",
            "root_cause": root_cause,
            "corrective_action": "Repair the freshness or compare-shell contract before rerunning the verifier.",
            "resolution_status": "not_fixed",
        },
        repo_root=repo_root,
        append_ledger=True,
        ledger_entry={
            "timestamp": _utc_now(),
            "experiment_id": experiment_id,
            "hypothesis": "F2.1 should improve F1's return/drawdown tradeoff on the same core universe under one shared TopN shell.",
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
            "failed_commands": [f"python -m quant_mvp f2_verify --project {project}"],
            "default_project_data_status": state.get("verify_last", {}).get("default_project_data_status", "validation-ready"),
            "conclusion_boundary_engineering": "The F2 verifier interface exists, but this run failed before it produced a trustworthy result.",
            "conclusion_boundary_research": "No new F2 vs F1 conclusion should be trusted from this failed verifier run.",
            "last_verified_capability": state.get("last_verified_capability"),
        },
        repo_root=repo_root,
    )
    generate_handoff(project, repo_root=repo_root)


def run_f2_verify(project: str, *, config_path: Path | None = None, repo_root: Path | None = None) -> dict[str, Any]:
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
        raise RuntimeError("F2 verifier requires an existing core pool snapshot.")

    experiment_id = f"{project}__factor_elasticnet_core__f2_verify__{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
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
        f2_experiment = _load_latest_f2_experiment(project, repo_root=repo_root)
        f2_report = _load_f2_train_report(paths)
        _validate_f2_freshness(
            cfg=cfg,
            paths=paths,
            core_snapshot=core_snapshot,
            f2_experiment=f2_experiment,
            f2_report=f2_report,
        )

        f1_rank_path = paths.signals_dir / f"f1_elasticnet_rank_top{topk}.parquet"
        f2_rank_path = paths.signals_dir / f"f2_structured_latent_rank_top{topk}.parquet"
        f1_rank = pd.read_parquet(f1_rank_path).copy()
        f2_rank = pd.read_parquet(f2_rank_path).copy()
        for frame in (f1_rank, f2_rank):
            frame["date"] = pd.to_datetime(frame["date"])
            frame["code"] = frame["code"].astype(str).str.zfill(6)
            frame["rank"] = frame["rank"].astype(int)
        f1_rank_stats = _validate_rank_frame(name="f1", rank_df=f1_rank, topk=topk)
        f2_rank_stats = _validate_rank_frame(name="f2", rank_df=f2_rank, topk=topk)

        hypothesis = "F2.1 should improve F1's return/drawdown tradeoff on the same core universe under one shared TopN shell."
        experiment = new_experiment(
            project=project,
            experiment_id=experiment_id,
            hypothesis=hypothesis,
            mode="f2_verify",
            plan_steps=["freshness_check", "control_rank", "shared_shell_backtest", "f2_report"],
            success_criteria=[
                "The verifier must compare control, F1, and F2.1 on the same core universe and shared TopN shell.",
                "The verifier must write a formal experiment record, report artifacts, and tracked memory updates.",
            ],
            universe_snapshot=f2_experiment.universe_snapshot,
            dataset_snapshot=f2_experiment.dataset_snapshot,
            opportunity_spec=f2_experiment.opportunity_spec,
            subagent_tasks=[],
            factor_candidates=f2_experiment.factor_candidates,
            feature_view=f2_experiment.feature_view,
            label_spec=f2_experiment.label_spec,
            model_candidate=f2_experiment.model_candidate,
            regime_spec=f2_experiment.regime_spec,
            mission_id=f2_experiment.mission_id,
            branch_id="factor_elasticnet_core",
            core_universe_snapshot_id=core_snapshot.snapshot_id,
            branch_pool_snapshot_id=f2_experiment.branch_pool_snapshot_id,
            opportunity_generator_id=f2_experiment.opportunity_generator_id,
            strategy_candidate_id="f2_structured_latent_factor_v1",
        )
        write_experiment_record(experiment, repo_root=repo_root)

        control_rank = _build_control_rank(cfg=cfg, core_codes=list(core_snapshot.codes))
        control_rank_stats = _validate_rank_frame(name="control", rank_df=control_rank, topk=topk)
        control_shared, f1_shared, f2_shared = _intersect_three_rank_frames(
            control_rank=control_rank,
            f1_rank=f1_rank.loc[:, ["date", "code", "score", "rank"]],
            f2_rank=f2_rank.loc[:, ["date", "code", "score", "rank"]],
        )

        all_codes = sorted(
            set(control_shared["code"].tolist())
            | set(f1_shared["code"].tolist())
            | set(f2_shared["code"].tolist())
        )
        start = min(
            pd.Timestamp(control_shared["date"].min()),
            pd.Timestamp(f1_shared["date"].min()),
            pd.Timestamp(f2_shared["date"].min()),
        )
        end = max(
            pd.Timestamp(control_shared["date"].max()),
            pd.Timestamp(f1_shared["date"].max()),
            pd.Timestamp(f2_shared["date"].max()),
        )
        close_panel = _load_shared_close_panel(cfg=cfg, codes=all_codes, start=start, end=end)
        bt_cfg = _shared_backtest_config(cfg)
        control_curves, control_metrics_df = run_topn_suite(close_panel=close_panel, rank_df=control_shared, cfg=bt_cfg, topn_max=topk)
        f1_curves, f1_metrics_df = run_topn_suite(close_panel=close_panel, rank_df=f1_shared, cfg=bt_cfg, topn_max=topk)
        f2_curves, f2_metrics_df = run_topn_suite(close_panel=close_panel, rank_df=f2_shared, cfg=bt_cfg, topn_max=topk)

        control_metrics = _topk_metrics(control_metrics_df, topk=topk)
        f1_metrics = _topk_metrics(f1_metrics_df, topk=topk)
        f2_metrics = _topk_metrics(f2_metrics_df, topk=topk)
        decision_payload = _decision_from_metrics(f1_metrics=f1_metrics, f2_metrics=f2_metrics)

        f2_dir = paths.artifacts_dir / "f2"
        f2_dir.mkdir(parents=True, exist_ok=True)
        metrics_output = f2_dir / "f2_vs_f1_vs_control_metrics.csv"
        pd.DataFrame(
            [
                {"series": "control", **control_metrics},
                {"series": "f1", **f1_metrics},
                {"series": "f2", **f2_metrics},
                {"series": "delta_vs_f1", **decision_payload["delta_metrics_vs_f1"]},
            ]
        ).to_csv(metrics_output, index=False, encoding="utf-8-sig")
        plot_output = _save_compare_plot(
            project=project,
            topk=topk,
            control_curves=control_curves,
            f1_curves=f1_curves,
            f2_curves=f2_curves,
            output_path=f2_dir / "f2_vs_f1_vs_control.png",
        )

        report = {
            "project": project,
            "generated_at": _utc_now(),
            "hypothesis": hypothesis,
            "core_snapshot_id": core_snapshot.snapshot_id,
            "source_f1_experiment_id": f1_experiment.experiment_id,
            "source_f2_experiment_id": f2_experiment.experiment_id,
            "compare_shell": "topn_suite_no_stoploss_v1",
            "date_intersection_start": start.strftime("%Y-%m-%d"),
            "date_intersection_end": end.strftime("%Y-%m-%d"),
            "topk": topk,
            "deep_factor_model": dict(cfg.get("deep_factor_model", {}) or {}),
            "f1_metrics": f1_metrics,
            "f2_metrics": f2_metrics,
            "control_metrics": control_metrics,
            "delta_metrics_vs_f1": decision_payload["delta_metrics_vs_f1"],
            "decision": decision_payload["decision"],
            "classification": decision_payload["classification"],
            "next_action": decision_payload["next_action"],
            "primary_blockers": decision_payload["primary_blockers"],
            "rank_frame_stats": {
                "control": control_rank_stats,
                "f1": f1_rank_stats,
                "f2": f2_rank_stats,
                "shared_date_count": int(control_shared["date"].nunique()),
            },
            "artifact_paths": {
                "source_f1_rank_path": str(f1_rank_path),
                "source_f2_rank_path": str(f2_rank_path),
                "metrics_csv_path": str(metrics_output),
                "plot_path": str(plot_output),
            },
        }
        report_json_path, report_md_path = _write_report(output_dir=f2_dir, report=report)
        report["artifact_paths"]["report_json_path"] = str(report_json_path)
        report["artifact_paths"]["report_md_path"] = str(report_md_path)
        report_json_path, report_md_path = _write_report(output_dir=f2_dir, report=report)

        evaluation = EvaluationRecord(
            status="f2_bounded_verifier",
            summary=(
                "F2.1 improved the F1 tradeoff enough to stay in the bounded challenger set."
                if decision_payload["decision"] != "reject_f2_v1_and_retain_f1_mainline"
                else "F2.1 did not improve the F1 tradeoff strongly enough under the shared shell."
            ),
            classification=decision_payload["classification"],
            primary_blockers=list(decision_payload["primary_blockers"]),
            promotion_decision={"evaluated": False, "reason": "bounded_f2_only", "decision": decision_payload["decision"]},
            next_experiment_themes=[
                (
                    "Advance F2.1 as the next bounded challenger family."
                    if decision_payload["decision"] == "promote_f2_next"
                    else (
                        "Run one more bounded F2.1 variant before widening the search."
                        if decision_payload["decision"] == "keep_f2_challenger"
                        else "Retain F1 and reselect the next challenger after F2.1 failed."
                    )
                )
            ],
            adversarial_robustness={"status": "not_evaluated", "score": None},
            regime_transition_drawdown=None,
        )
        execution = {
            "executed_steps": list(experiment.plan_steps),
            "outputs": {
                "freshness_check": {
                    "source_f1_experiment_id": f1_experiment.experiment_id,
                    "source_f2_experiment_id": f2_experiment.experiment_id,
                    "core_snapshot_id": core_snapshot.snapshot_id,
                },
                "control_rank": {"date_count": int(control_shared["date"].nunique())},
                "shared_shell_backtest": {
                    "metrics_path": str(metrics_output),
                    "plot_path": str(plot_output),
                    "date_intersection_start": report["date_intersection_start"],
                    "date_intersection_end": report["date_intersection_end"],
                },
                "f2_report": {"json_path": str(report_json_path), "md_path": str(report_md_path)},
            },
        }
        experiment = update_experiment(
            experiment,
            status="evaluated",
            execution=execution,
            evaluation=evaluation,
            artifact_refs=[
                str(metrics_output),
                str(plot_output),
                str(report_json_path),
                str(report_md_path),
            ],
        )
        experiment_path = write_experiment_record(experiment, repo_root=repo_root)
        report["artifact_paths"]["experiment_record_path"] = str(experiment_path)
        report_json_path, report_md_path = _write_report(output_dir=f2_dir, report=report)

        update_run_manifest(
            project,
            {
                "f2_verifier": {
                    "core_snapshot_id": core_snapshot.snapshot_id,
                    "source_f1_experiment_id": f1_experiment.experiment_id,
                    "source_f2_experiment_id": f2_experiment.experiment_id,
                    "metrics_path": str(metrics_output),
                    "plot_path": str(plot_output),
                    "report_json_path": str(report_json_path),
                    "report_md_path": str(report_md_path),
                    "experiment_record_path": str(experiment_path),
                    "decision": decision_payload["decision"],
                    "classification": decision_payload["classification"],
                }
            },
        )
        _sync_f2_memory(
            project=project,
            topk=topk,
            experiment_id=experiment_id,
            decision_payload=decision_payload,
            report=report,
            report_json_path=report_json_path,
            report_md_path=report_md_path,
            f1_metrics=f1_metrics,
            f2_metrics=f2_metrics,
            repo_root=repo_root,
        )
        if decision_payload["decision"] == "reject_f2_v1_and_retain_f1_mainline":
            record_failure(
                project,
                {
                    "timestamp": _utc_now(),
                    "experiment_id": experiment_id,
                    "summary": "F2.1 bounded verifier did not improve the F1 tradeoff strongly enough.",
                    "root_cause": "; ".join(decision_payload["primary_blockers"]) or "F2.1 decision rule did not pass.",
                    "corrective_action": "Retain F1 mainline and reselect the next challenger.",
                    "resolution_status": "not_fixed",
                },
                repo_root=repo_root,
                preserve_progress=True,
            )
        return {
            "experiment_id": experiment_id,
            "experiment_record_path": str(experiment_path),
            "report_json_path": str(report_json_path),
            "report_md_path": str(report_md_path),
            "metrics_path": str(metrics_output),
            "plot_path": str(plot_output),
            "decision": decision_payload["decision"],
            "classification": decision_payload["classification"],
            "next_action": decision_payload["next_action"],
            "f1_metrics": f1_metrics,
            "f2_metrics": f2_metrics,
            "control_metrics": control_metrics,
            "delta_metrics_vs_f1": decision_payload["delta_metrics_vs_f1"],
        }
    except Exception as exc:
        artifact_refs: list[str] = []
        if experiment is not None:
            evaluation = EvaluationRecord(
                status="failed",
                summary=f"F2 bounded verifier failed: {exc}",
                classification="verifier_fail",
                primary_blockers=[str(exc)],
                promotion_decision={"evaluated": False, "reason": "f2_verifier_failed"},
                next_experiment_themes=["Repair the F2 freshness or shared-shell contract before rerunning the verifier."],
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
        _sync_f2_failure(
            project=project,
            experiment_id=experiment_id,
            root_cause=str(exc),
            artifact_refs=artifact_refs,
            repo_root=repo_root,
        )
        raise
