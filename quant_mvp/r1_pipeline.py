from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from .backtest_engine import rank_targets, run_topn_suite
from .config import load_config
from .experiment_graph import EvaluationRecord, Experiment, RegimeSpec, new_experiment, update_experiment, write_experiment_record
from .f1_verify import (
    _build_control_rank,
    _dedupe,
    _intersect_rank_frames,
    _load_f1_train_report,
    _load_latest_f1_experiment,
    _load_shared_close_panel,
    _shared_backtest_config,
    _validate_freshness,
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


@dataclass(frozen=True)
class RegimeControlConfig:
    profile: str
    ic_window_rebalances: int
    shortfall_window_rebalances: int
    min_history_rebalances: int
    caution_ic_threshold: float
    defensive_ic_threshold: float
    caution_shortfall_threshold: float
    defensive_shortfall_threshold: float
    caution_exposure: float
    defensive_exposure: float
    cooldown_rebalances: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "ic_window_rebalances": self.ic_window_rebalances,
            "shortfall_window_rebalances": self.shortfall_window_rebalances,
            "min_history_rebalances": self.min_history_rebalances,
            "caution_ic_threshold": self.caution_ic_threshold,
            "defensive_ic_threshold": self.defensive_ic_threshold,
            "caution_shortfall_threshold": self.caution_shortfall_threshold,
            "defensive_shortfall_threshold": self.defensive_shortfall_threshold,
            "caution_exposure": self.caution_exposure,
            "defensive_exposure": self.defensive_exposure,
            "cooldown_rebalances": self.cooldown_rebalances,
        }


@dataclass(frozen=True)
class R1Variant:
    profile: str
    display_label: str
    strategy_candidate_id: str
    candidate_name: str
    reject_decision: str
    reject_next_action: str
    reject_next_build_target: str
    followup_strategy_id: str | None
    hypothesis: str
    notes: str

    @property
    def artifact_slug(self) -> str:
        return self.profile.replace("/", "_")

    @property
    def compare_label(self) -> str:
        return f"F1+{self.display_label}"

    @property
    def current_phase(self) -> str:
        return f"{self.display_label} bounded verifier"


def _regime_control_config(cfg: dict[str, Any]) -> RegimeControlConfig:
    raw = dict(cfg.get("regime_control", {}) or {})
    return RegimeControlConfig(
        profile=str(raw.get("profile", "r1_predictive_error_overlay_v1")),
        ic_window_rebalances=int(raw.get("ic_window_rebalances", 6)),
        shortfall_window_rebalances=int(raw.get("shortfall_window_rebalances", 6)),
        min_history_rebalances=int(raw.get("min_history_rebalances", 6)),
        caution_ic_threshold=float(raw.get("caution_ic_threshold", 0.00)),
        defensive_ic_threshold=float(raw.get("defensive_ic_threshold", -0.03)),
        caution_shortfall_threshold=float(raw.get("caution_shortfall_threshold", -0.005)),
        defensive_shortfall_threshold=float(raw.get("defensive_shortfall_threshold", -0.015)),
        caution_exposure=float(raw.get("caution_exposure", 0.5)),
        defensive_exposure=float(raw.get("defensive_exposure", 0.25)),
        cooldown_rebalances=int(raw.get("cooldown_rebalances", 2)),
    )


def _r1_variant(profile: str) -> R1Variant:
    normalized = str(profile or "r1_predictive_error_overlay_v1").strip() or "r1_predictive_error_overlay_v1"
    if normalized == "r1_predictive_error_overlay_v2":
        return R1Variant(
            profile=normalized,
            display_label="R1.2",
            strategy_candidate_id="r1_predictive_error_overlay_v2",
            candidate_name="R1.2 Predictive Error Overlay",
            reject_decision="reject_r1_v2_and_promote_f2_next",
            reject_next_action="Retain F1 as the mainline and promote F2.1 to the next implementation slot.",
            reject_next_build_target="f2_structured_latent_factor_v1",
            followup_strategy_id="f2_structured_latent_factor_v1",
            hypothesis="A gentler lagged predictive-error regime overlay should preserve more F1 return while keeping part of the drawdown improvement.",
            notes="R1.2 stays exposure-only, keeps the same lagged detector family, and only softens the throttle relative to v1.",
        )
    return R1Variant(
        profile=normalized,
        display_label="R1.1",
        strategy_candidate_id="r1_predictive_error_overlay_v1",
        candidate_name="R1.1 Predictive Error Overlay",
        reject_decision="reject_r1_v1_and_retain_f1_mainline",
        reject_next_action="Retain F1 as the mainline and reopen frontier reselection before choosing the next challenger.",
        reject_next_build_target="frontier_reselection_required",
        followup_strategy_id=None,
        hypothesis="A lagged predictive-error regime overlay should reduce F1 drawdown on the same core universe without destroying return.",
        notes="R1.1 is bounded to lagged predictive-error signals; it never updates F1 weights online.",
    )


def _decision_texts(variant: R1Variant, decision: str) -> dict[str, str]:
    if decision == "promote_r1_control_layer_next":
        return {
            "summary": f"{variant.display_label} improved drawdown enough to become the next bounded control-layer target on top of F1.",
            "next_action": f"Integrate {variant.display_label} as the next formal bounded control layer on top of F1, then reopen LIGHT scouting for F2.1.",
            "candidate_next_validation": f"Promote {variant.display_label} to the next formal control-layer implementation step.",
            "f1_next_validation": f"Keep F1 as mainline and integrate {variant.display_label} as the next bounded control layer.",
        }
    if decision == "keep_r1_challenger":
        return {
            "summary": f"{variant.display_label} showed some promise, but not enough to become the next control-layer target yet.",
            "next_action": f"Run one bounded {variant.display_label} sanity variant before promoting it or reopening broader search.",
            "candidate_next_validation": f"Run one bounded {variant.display_label} sanity variant before any broader regime work.",
            "f1_next_validation": f"Keep F1 as the mainline while {variant.display_label} remains bounded but unpromoted.",
        }
    if decision == variant.reject_decision:
        return {
            "summary": f"{variant.display_label} did not clear the economics gate strongly enough to remain the next control-layer target.",
            "next_action": variant.reject_next_action,
            "candidate_next_validation": (
                "Reject this bounded overlay and promote F2.1 to the next implementation slot."
                if variant.followup_strategy_id == "f2_structured_latent_factor_v1"
                else "Reject this bounded overlay and return to frontier reselection."
            ),
            "f1_next_validation": (
                "Keep F1 as the mainline and promote F2.1 to the next implementation slot."
                if variant.followup_strategy_id == "f2_structured_latent_factor_v1"
                else "Keep F1 as the mainline while the overlay path returns to frontier reselection."
            ),
        }
    raise RuntimeError(f"Unknown R1 decision: {decision}")


def _topk_metrics(metrics_df: pd.DataFrame, *, topk: int) -> dict[str, Any]:
    row = metrics_df.loc[metrics_df["topn"].astype(int) == int(topk)]
    if row.empty:
        raise RuntimeError(f"Missing Top{topk} metrics in the shared-shell suite.")
    return {str(key): value for key, value in row.iloc[0].to_dict().items()}


def _validate_r1_freshness(
    *,
    cfg: dict[str, Any],
    paths,
    core_snapshot,
    f1_experiment: Experiment,
    f1_report: dict[str, Any],
) -> int:
    topk = _validate_freshness(
        cfg=cfg,
        paths=paths,
        core_snapshot=core_snapshot,
        f1_experiment=f1_experiment,
        f1_report=f1_report,
    )
    missing: list[str] = []
    for path in [
        paths.signals_dir / "f1_elasticnet_candidate_scores.parquet",
        paths.features_dir / "f1_next5d_excess_label_v1.parquet",
    ]:
        if not path.exists():
            missing.append(path.name)
    if missing:
        raise RuntimeError(
            "Latest F1 artifacts are incomplete for R1 verification; rerun f1_train first. Missing: "
            + ", ".join(missing)
        )
    return topk


def _load_candidate_scores(paths) -> pd.DataFrame:
    path = paths.signals_dir / "f1_elasticnet_candidate_scores.parquet"
    df = pd.read_parquet(path).copy()
    df["date"] = pd.to_datetime(df["date"])
    df["code"] = df["code"].astype(str).str.zfill(6)
    return df.loc[:, ["date", "code", "score", "rank"]].sort_values(["date", "rank", "code"]).reset_index(drop=True)


def _load_label_frame(paths) -> pd.DataFrame:
    path = paths.features_dir / "f1_next5d_excess_label_v1.parquet"
    df = pd.read_parquet(path).copy()
    df["date"] = pd.to_datetime(df["date"])
    df["code"] = df["code"].astype(str).str.zfill(6)
    return df.loc[:, ["date", "code", "next_5d_excess_return"]].sort_values(["date", "code"]).reset_index(drop=True)


def _spearman_ic(frame: pd.DataFrame) -> float | None:
    usable = frame.loc[:, ["score", "next_5d_excess_return"]].dropna()
    if len(usable) < 3:
        return None
    if usable["score"].nunique(dropna=True) < 2 or usable["next_5d_excess_return"].nunique(dropna=True) < 2:
        return None
    value = usable["score"].corr(usable["next_5d_excess_return"], method="spearman")
    if pd.isna(value):
        return None
    return float(value)


def _build_signal_frame(
    *,
    candidate_scores: pd.DataFrame,
    label_frame: pd.DataFrame,
    f1_shared_rank: pd.DataFrame,
    regime_cfg: RegimeControlConfig,
    topk: int,
) -> pd.DataFrame:
    shared_dates = sorted(pd.to_datetime(f1_shared_rank["date"]).unique().tolist())
    if not shared_dates:
        raise RuntimeError("R1 verifier requires shared rebalance dates from the F1 verifier contract.")

    score_frame = candidate_scores.loc[candidate_scores["date"].isin(shared_dates)].merge(
        label_frame,
        on=["date", "code"],
        how="left",
    )
    ic_rows: list[dict[str, Any]] = []
    for dt, group in score_frame.groupby("date", sort=True):
        ic_rows.append(
            {
                "date": pd.Timestamp(dt),
                "ic": _spearman_ic(group),
                "cross_section_count": int(group.dropna(subset=["score", "next_5d_excess_return"]).shape[0]),
            }
        )
    ic_df = pd.DataFrame(ic_rows)

    topk_frame = (
        f1_shared_rank.loc[f1_shared_rank["rank"] <= int(topk), ["date", "code", "rank"]]
        .merge(label_frame, on=["date", "code"], how="left")
        .sort_values(["date", "rank", "code"])
    )
    shortfall_df = (
        topk_frame.groupby("date", as_index=False)
        .agg(
            topk_excess_return=("next_5d_excess_return", "mean"),
            topk_label_coverage=("next_5d_excess_return", lambda series: int(series.notna().sum())),
        )
        .sort_values("date")
    )

    signal_frame = pd.DataFrame({"date": pd.to_datetime(shared_dates)})
    signal_frame = signal_frame.merge(ic_df, on="date", how="left").merge(shortfall_df, on="date", how="left")
    signal_frame["lagged_ic"] = signal_frame["ic"].shift(1)
    signal_frame["lagged_topk_excess_return"] = signal_frame["topk_excess_return"].shift(1)
    signal_frame["ewma_ic"] = (
        signal_frame["lagged_ic"]
        .astype(float)
        .ewm(span=regime_cfg.ic_window_rebalances, adjust=False, min_periods=regime_cfg.min_history_rebalances)
        .mean()
    )
    signal_frame["ewma_topk_excess_return"] = (
        signal_frame["lagged_topk_excess_return"]
        .astype(float)
        .ewm(
            span=regime_cfg.shortfall_window_rebalances,
            adjust=False,
            min_periods=regime_cfg.min_history_rebalances,
        )
        .mean()
    )
    signal_frame["lagged_history_count"] = signal_frame["lagged_topk_excess_return"].notna().cumsum()
    return signal_frame.sort_values("date").reset_index(drop=True)


def _desired_state(row: pd.Series, regime_cfg: RegimeControlConfig) -> str:
    history_count = int(row.get("lagged_history_count", 0) or 0)
    if history_count < int(regime_cfg.min_history_rebalances):
        return "normal"
    ewma_ic = row.get("ewma_ic")
    ewma_shortfall = row.get("ewma_topk_excess_return")

    defensive = False
    caution = False
    if pd.notna(ewma_ic):
        defensive = defensive or float(ewma_ic) < regime_cfg.defensive_ic_threshold
        caution = caution or float(ewma_ic) < regime_cfg.caution_ic_threshold
    if pd.notna(ewma_shortfall):
        defensive = defensive or float(ewma_shortfall) < regime_cfg.defensive_shortfall_threshold
        caution = caution or float(ewma_shortfall) < regime_cfg.caution_shortfall_threshold
    if defensive:
        return "defensive"
    if caution:
        return "caution"
    return "normal"


def _state_exposure(state: str, regime_cfg: RegimeControlConfig) -> float:
    if state == "caution":
        return float(regime_cfg.caution_exposure)
    if state == "defensive":
        return float(regime_cfg.defensive_exposure)
    return 1.0


def _build_state_timeline(signal_frame: pd.DataFrame, regime_cfg: RegimeControlConfig) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    current_state = "normal"
    cooldown_remaining = 0
    entry_cooldown = max(int(regime_cfg.cooldown_rebalances) - 1, 0)

    for _, row in signal_frame.iterrows():
        desired = _desired_state(row, regime_cfg)
        next_state = current_state
        can_recover = cooldown_remaining <= 0

        if current_state == "normal":
            if desired in {"caution", "defensive"}:
                next_state = desired
        elif current_state == "caution":
            if desired == "defensive":
                next_state = "defensive"
            elif desired == "normal" and can_recover:
                next_state = "normal"
        elif current_state == "defensive":
            if desired == "defensive":
                next_state = "defensive"
            elif can_recover:
                next_state = "caution"

        state_changed = next_state != current_state
        if state_changed and next_state in {"caution", "defensive"}:
            cooldown_after = entry_cooldown
        elif state_changed and next_state == "normal":
            cooldown_after = 0
        else:
            cooldown_after = max(cooldown_remaining - 1, 0)

        rows.append(
            {
                "date": pd.Timestamp(row["date"]),
                "desired_state": desired,
                "state": next_state,
                "exposure_scale": _state_exposure(next_state, regime_cfg),
                "cooldown_remaining_before": int(cooldown_remaining),
                "cooldown_remaining_after": int(cooldown_after),
                "ic": row.get("ic"),
                "lagged_ic": row.get("lagged_ic"),
                "ewma_ic": row.get("ewma_ic"),
                "topk_excess_return": row.get("topk_excess_return"),
                "lagged_topk_excess_return": row.get("lagged_topk_excess_return"),
                "ewma_topk_excess_return": row.get("ewma_topk_excess_return"),
                "lagged_history_count": int(row.get("lagged_history_count", 0) or 0),
            }
        )
        current_state = next_state
        cooldown_remaining = cooldown_after

    return pd.DataFrame(rows)


def _build_daily_exposure_schedule(
    *,
    calendar: pd.DatetimeIndex,
    state_timeline: pd.DataFrame,
) -> dict[pd.Timestamp, float]:
    if state_timeline.empty:
        return {}
    schedule: dict[pd.Timestamp, float] = {pd.Timestamp(item): 1.0 for item in calendar}
    rebalance_dates = [pd.Timestamp(item) for item in state_timeline["date"].tolist()]
    exposures = [float(item) for item in state_timeline["exposure_scale"].tolist()]
    for idx, dt in enumerate(rebalance_dates):
        start_pos = int(calendar.searchsorted(dt, side="right"))
        if idx + 1 < len(rebalance_dates):
            end_pos = int(calendar.searchsorted(rebalance_dates[idx + 1], side="right"))
        else:
            end_pos = len(calendar)
        for ts in calendar[start_pos:end_pos]:
            schedule[pd.Timestamp(ts)] = exposures[idx]
    return schedule


def _average_turnover(
    *,
    rank_df: pd.DataFrame,
    topk: int,
    exposure_by_rebalance: Mapping[pd.Timestamp, float] | None = None,
) -> float:
    targets = rank_targets(rank_df, topn=topk)
    codes = sorted({str(code).zfill(6) for items in targets.values() for code in items})
    previous = pd.Series(0.0, index=codes, dtype=float)
    turnovers: list[float] = []
    for dt in sorted(targets.keys()):
        chosen = [str(code).zfill(6) for code in list(targets[dt])]
        exposure = float((exposure_by_rebalance or {}).get(pd.Timestamp(dt), 1.0))
        target = pd.Series(0.0, index=codes, dtype=float)
        if chosen:
            target.loc[chosen] = exposure / len(chosen)
        turnovers.append(float((target - previous).abs().sum() / 2.0))
        previous = target
    return float(pd.Series(turnovers).mean()) if turnovers else 0.0


def _regime_transition_drawdown(
    *,
    equity: pd.Series,
    exposure_scale_by_date: Mapping[pd.Timestamp, float],
) -> float | None:
    if equity.empty or not exposure_scale_by_date:
        return None
    drawdown = equity / equity.cummax() - 1.0
    active_dates = [dt for dt, scale in exposure_scale_by_date.items() if float(scale) < 1.0 and pd.Timestamp(dt) in drawdown.index]
    if not active_dates:
        return None
    active_drawdown = drawdown.loc[sorted(set(pd.to_datetime(active_dates)))]
    if active_drawdown.empty:
        return None
    return float(active_drawdown.min())


def _false_trigger_rate(state_timeline: pd.DataFrame) -> float | None:
    if state_timeline.empty:
        return None
    active = state_timeline.loc[state_timeline["state"] != "normal"].copy()
    active = active.dropna(subset=["topk_excess_return"])
    if active.empty:
        return None
    return float((active["topk_excess_return"] >= 0.0).mean())


def _save_compare_plot(
    *,
    project: str,
    topk: int,
    variant: R1Variant,
    control_curves: pd.DataFrame,
    f1_curves: pd.DataFrame,
    r1_curves: pd.DataFrame,
    output_path: Path,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure, axis = plt.subplots(figsize=(10, 5))
    series_map = {
        f"Control Top{topk}": control_curves[f"Top{topk}"].astype(float),
        f"F1 Top{topk}": f1_curves[f"Top{topk}"].astype(float),
        f"{variant.compare_label} Top{topk}": r1_curves[f"Top{topk}"].astype(float),
    }
    for label, series in series_map.items():
        axis.plot(series.index, series / float(series.iloc[0]), label=label, linewidth=1.8)
    axis.set_title(f"{project}: control vs F1 vs {variant.compare_label} under shared TopN shell")
    axis.set_ylabel("Normalized equity")
    axis.grid(alpha=0.25)
    axis.legend()
    figure.autofmt_xdate()
    figure.tight_layout()
    figure.savefig(output_path, dpi=150)
    plt.close(figure)
    return output_path


def _delta_metrics(*, base_metrics: dict[str, Any], challenger_metrics: dict[str, Any]) -> dict[str, float]:
    return {
        "annualized_return_delta": float(challenger_metrics.get("annualized_return", 0.0) or 0.0)
        - float(base_metrics.get("annualized_return", 0.0) or 0.0),
        "sharpe_ratio_delta": float(challenger_metrics.get("sharpe_ratio", 0.0) or 0.0)
        - float(base_metrics.get("sharpe_ratio", 0.0) or 0.0),
        "max_drawdown_improvement": abs(float(base_metrics.get("max_drawdown", 0.0) or 0.0))
        - abs(float(challenger_metrics.get("max_drawdown", 0.0) or 0.0)),
        "calmar_ratio_delta": float(challenger_metrics.get("calmar_ratio", 0.0) or 0.0)
        - float(base_metrics.get("calmar_ratio", 0.0) or 0.0),
        "max_drawdown_duration_delta": float(challenger_metrics.get("max_drawdown_duration", 0.0) or 0.0)
        - float(base_metrics.get("max_drawdown_duration", 0.0) or 0.0),
    }


def _decision_from_r1_metrics(
    *,
    variant: R1Variant,
    f1_metrics: dict[str, Any],
    r1_metrics: dict[str, Any],
    f1_turnover: float,
    r1_turnover: float,
) -> dict[str, Any]:
    deltas = _delta_metrics(base_metrics=f1_metrics, challenger_metrics=r1_metrics)
    turnover_delta = float(r1_turnover - f1_turnover)
    turnover_ratio = turnover_delta / max(abs(float(f1_turnover)), 1e-12)
    deltas["turnover_delta"] = turnover_delta
    deltas["turnover_ratio"] = turnover_ratio

    primary_blockers: list[str] = []
    if deltas["max_drawdown_improvement"] < 0.05:
        primary_blockers.append(
            f"r1_drawdown_improvement {deltas['max_drawdown_improvement']:.2%} is below the required 5.00% improvement."
        )
    if deltas["annualized_return_delta"] < -0.03:
        primary_blockers.append(
            f"r1_annualized_return_delta {deltas['annualized_return_delta']:.2%} is below the allowed -3.00% floor."
        )
    if deltas["calmar_ratio_delta"] <= 0.0:
        primary_blockers.append(
            f"r1_calmar_ratio_delta {deltas['calmar_ratio_delta']:.4f} is not positive."
        )
    if turnover_ratio > 0.15:
        primary_blockers.append(
            f"r1_turnover_ratio {turnover_ratio:.2%} exceeds the allowed 15.00% deterioration."
        )

    if deltas["max_drawdown_improvement"] >= 0.05 and deltas["annualized_return_delta"] >= -0.03:
        if deltas["calmar_ratio_delta"] > 0.0 and turnover_ratio <= 0.15:
            decision = "promote_r1_control_layer_next"
            classification = "verifier_pass"
            next_action = "integrate_r1_as_next_control_layer"
        else:
            decision = "keep_r1_challenger"
            classification = "verifier_mixed"
            next_action = "run_one_threshold_and_cooldown_sanity_variant"
    else:
        decision = variant.reject_decision
        classification = "verifier_mixed" if any(value > 0 for value in deltas.values() if isinstance(value, float)) else "verifier_fail"
        next_action = "promote_next_model_branch" if variant.followup_strategy_id else "retain_f1_and_reopen_frontier_reselection"

    return {
        "decision": decision,
        "classification": classification,
        "next_action": next_action,
        "primary_blockers": _dedupe(primary_blockers),
        "delta_metrics_vs_f1": deltas,
    }


def _write_report(*, output_dir: Path, report: dict[str, Any]) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "R1_VERIFY_REPORT.json"
    md_path = output_dir / "R1_VERIFY_REPORT.md"
    json_path.write_text(json.dumps(to_jsonable(report), ensure_ascii=False, indent=2).rstrip() + "\n", encoding="utf-8")

    blockers = list(report.get("primary_blockers", []) or [])
    lines = [
        "# R1 Verify Report",
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
        "## R1 Metrics",
        *(f"- `{key}`: `{value}`" for key, value in dict(report.get("r1_metrics", {}) or {}).items()),
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
    variant: R1Variant,
    state: dict[str, Any],
    topk: int,
    f1_metrics: dict[str, Any],
    r1_metrics: dict[str, Any],
    decision_payload: dict[str, Any],
    artifact_refs: list[str],
) -> list[dict[str, Any]]:
    current = [dict(item) for item in list(state.get("strategy_candidates", []) or []) if isinstance(item, dict)]
    updated: list[dict[str, Any]] = []
    saw_f1 = False
    saw_r1 = False
    saw_f2 = False
    decision_text = _decision_texts(variant, decision_payload["decision"])
    for item in current:
        strategy_id = str(item.get("strategy_id", "")).strip()
        candidate = dict(item)
        if strategy_id == "f1_elasticnet_v1":
            saw_f1 = True
            candidate["track"] = "primary"
            candidate["decision"] = "continue"
            candidate["current_stage"] = "validation"
            candidate["latest_action"] = f"Completed one bounded {variant.display_label} verifier on top of F1."
            candidate["latest_result"] = (
                f"F1 shared-shell Top{topk}: annualized_return={float(f1_metrics.get('annualized_return', 0.0)):.2%}, "
                f"max_drawdown={abs(float(f1_metrics.get('max_drawdown', 0.0))):.2%}, "
                f"sharpe={float(f1_metrics.get('sharpe_ratio', 0.0)):.4f}."
            )
            candidate["next_validation"] = decision_text["f1_next_validation"]
            candidate["artifact_refs"] = _dedupe(list(candidate.get("artifact_refs", []) or []) + artifact_refs)
        elif strategy_id == variant.strategy_candidate_id:
            saw_r1 = True
            candidate["track"] = "candidate"
            candidate["decision"] = "continue" if decision_payload["decision"] != variant.reject_decision else "hold"
            candidate["current_stage"] = "validation"
            candidate["latest_action"] = "Completed one bounded predictive-error regime-overlay verifier."
            candidate["latest_result"] = (
                f"{variant.compare_label} shared-shell Top{topk}: annualized_return={float(r1_metrics.get('annualized_return', 0.0)):.2%}, "
                f"max_drawdown={abs(float(r1_metrics.get('max_drawdown', 0.0))):.2%}, "
                f"sharpe={float(r1_metrics.get('sharpe_ratio', 0.0)):.4f}; decision={decision_payload['decision']}."
            )
            candidate["next_validation"] = decision_text["candidate_next_validation"]
            candidate["blocked_by"] = list(decision_payload.get("primary_blockers", []) or [])
            candidate["artifact_refs"] = _dedupe(list(candidate.get("artifact_refs", []) or []) + artifact_refs)
        elif strategy_id == "f2_structured_latent_factor_v1" and variant.followup_strategy_id == "f2_structured_latent_factor_v1":
            saw_f2 = True
            if decision_payload["decision"] == variant.reject_decision:
                candidate["track"] = "secondary"
                candidate["decision"] = "continue"
                candidate["current_stage"] = "selected_next"
                candidate["latest_action"] = f"Promoted to the next implementation slot after {variant.display_label} failed the return floor."
                candidate["latest_result"] = "F2.1 is now the next model challenger because the softer bounded overlay still did not preserve enough return."
                candidate["next_validation"] = "Implement the bounded F2.1 prototype on the same F1 object contract and shared evaluation shell."
        updated.append(candidate)

    if not saw_f1:
        updated.append(
            {
                "strategy_id": "f1_elasticnet_v1",
                "name": "F1 ElasticNet Mainline",
                "category": "factor_model",
                "core_hypothesis": "A regularized cross-sectional factor model should outperform the legacy control branch on the same core universe.",
                "economic_rationale": "F1 is the current verified mainline and the reference point for every bounded challenger.",
                "required_data": "Core universe snapshot, technical/liquidity feature panel, next_5d_excess_return label, shared-shell TopN backtest.",
                "current_stage": "validation",
                "latest_action": f"Completed one bounded {variant.display_label} verifier on top of F1.",
                "latest_result": (
                    f"F1 shared-shell Top{topk}: annualized_return={float(f1_metrics.get('annualized_return', 0.0)):.2%}, "
                    f"max_drawdown={abs(float(f1_metrics.get('max_drawdown', 0.0))):.2%}, "
                    f"sharpe={float(f1_metrics.get('sharpe_ratio', 0.0)):.4f}."
                ),
                "decision": "continue",
                "next_validation": decision_text["f1_next_validation"],
                "owner": "main",
                "subagents_assigned": [],
                "artifact_refs": list(artifact_refs),
                "blocked_by": [],
                "kill_criteria": "If F1 cannot keep the mainline against bounded challengers or its drawdown cannot be controlled without destroying return, it should no longer define the near-term stack.",
                "track": "primary",
            }
        )

    if not saw_r1:
        updated.append(
            {
                "strategy_id": variant.strategy_candidate_id,
                "name": variant.candidate_name,
                "category": "other",
                "core_hypothesis": variant.hypothesis,
                "economic_rationale": "When the F1 cross-section starts failing out of sample, the platform should reduce gross exposure before losses compound.",
                "required_data": "F1 candidate scores, next_5d_excess_return labels, core pool snapshot, shared-shell TopN backtest.",
                "current_stage": "validation",
                "latest_action": "Completed one bounded predictive-error regime-overlay verifier.",
                "latest_result": (
                    f"{variant.compare_label} shared-shell Top{topk}: annualized_return={float(r1_metrics.get('annualized_return', 0.0)):.2%}, "
                    f"max_drawdown={abs(float(r1_metrics.get('max_drawdown', 0.0))):.2%}, "
                    f"sharpe={float(r1_metrics.get('sharpe_ratio', 0.0)):.4f}; decision={decision_payload['decision']}."
                ),
                "decision": "continue" if decision_payload["decision"] != variant.reject_decision else "hold",
                "next_validation": decision_text["candidate_next_validation"],
                "owner": "main",
                "subagents_assigned": [],
                "artifact_refs": list(artifact_refs),
                "blocked_by": list(decision_payload.get("primary_blockers", []) or []),
                "kill_criteria": "If the overlay cannot materially reduce drawdown without heavily harming return, keep it out of the mainline.",
                "track": "candidate",
            }
        )
    if (
        variant.followup_strategy_id == "f2_structured_latent_factor_v1"
        and decision_payload["decision"] == variant.reject_decision
        and not saw_f2
    ):
        updated.append(
            {
                "strategy_id": "f2_structured_latent_factor_v1",
                "name": "F2.1 Structured Latent Deep Factor",
                "category": "factor_model",
                "core_hypothesis": "A structured latent deep factor should be the next challenger once the exposure-only overlay family fails the return floor.",
                "economic_rationale": "F2.1 is the next model branch because the softer overlay family still could not preserve enough return.",
                "required_data": "The current F1 feature view, label contract, core universe snapshot, and shared-shell evaluation harness.",
                "current_stage": "selected_next",
                "latest_action": f"Promoted to the next implementation slot after {variant.display_label} failed the return floor.",
                "latest_result": "F2.1 is now the next model challenger because the softer bounded overlay still did not preserve enough return.",
                "decision": "continue",
                "next_validation": "Implement the bounded F2.1 prototype on the same F1 object contract and shared evaluation shell.",
                "owner": "main",
                "subagents_assigned": [],
                "artifact_refs": list(artifact_refs),
                "blocked_by": [],
                "kill_criteria": "Do not proceed if the prototype needs heavier dependencies, richer data, or a looser walk-forward contract than the current platform can audit.",
                "track": "secondary",
            }
        )
    return updated


def _append_repo_decision_log(*, repo_root: Path, project: str, report: dict[str, Any], variant: R1Variant) -> None:
    decision_log_path = repo_root / "docs" / "DECISION_LOG.md"
    existing = decision_log_path.read_text(encoding="utf-8") if decision_log_path.exists() else "# Decision Log\n"
    decision = str(report.get("decision", "unknown"))
    if decision == "promote_r1_control_layer_next":
        decision_line = "- Decision: `promote_r1_control_layer_next`"
        reason_line = f"- Reason: the bounded {variant.display_label} verifier improved drawdown enough on top of F1 to justify making it the next control-layer implementation target."
    elif decision == variant.reject_decision and variant.followup_strategy_id == "f2_structured_latent_factor_v1":
        decision_line = "- Decision: `promote_f2_1_next_after_r1_2_reject`"
        reason_line = f"- Reason: {variant.display_label} still reduced too much return, so F2.1 is now the next implementation slot while F1 remains mainline."
    else:
        decision_line = f"- Decision: `{decision}`"
        reason_line = f"- Reason: recorded bounded {variant.display_label} decision."
    block = "\n".join(
        [
            "",
            f"## {report['generated_at']} - {project}",
            decision_line,
            reason_line,
            f"- Evidence: `{report['artifact_paths']['report_md_path']}`",
        ]
    )
    decision_log_path.write_text(existing.rstrip() + block + "\n", encoding="utf-8")


def _sync_r1_memory(
    *,
    variant: R1Variant,
    project: str,
    decision_payload: dict[str, Any],
    topk: int,
    experiment_id: str,
    report_json_path: Path,
    report_md_path: Path,
    f1_metrics: dict[str, Any],
    r1_metrics: dict[str, Any],
    report: dict[str, Any],
    repo_root: Path | None = None,
) -> None:
    _, state = load_machine_state(project, repo_root=repo_root)
    r1_drawdown = abs(float(r1_metrics.get("max_drawdown", 0.0) or 0.0))
    decision_text = _decision_texts(variant, decision_payload["decision"])
    if r1_drawdown > 0.30:
        blocker = f"{variant.compare_label} shared-shell Top{topk} max_drawdown {r1_drawdown:.2%} remains above 30.00%."
    elif decision_payload["decision"] == variant.reject_decision:
        blocker = (
            f"{variant.display_label} still sacrificed too much return, so F2.1 becomes the next model challenger."
            if variant.followup_strategy_id == "f2_structured_latent_factor_v1"
            else f"{variant.display_label} did not reduce drawdown strongly enough to justify becoming the next control layer."
        )
    else:
        blocker = "none"
    next_action = decision_text["next_action"]
    current_phase = variant.current_phase
    current_task = f"Verify whether {variant.display_label} can lower F1 drawdown without destroying return."
    current_capability_boundary = (
        f"{variant.display_label} now exists as a bounded verifier prototype only; it is not promotion evidence and it does not change F1 weights online."
    )
    current_strategy_focus = ["f1_elasticnet_v1", variant.strategy_candidate_id]
    current_strategy_summary = (
        f"{variant.display_label} verifier classification={decision_payload['classification']}; decision={decision_payload['decision']}."
    )
    if decision_payload["decision"] == variant.reject_decision and variant.followup_strategy_id == "f2_structured_latent_factor_v1":
        current_phase = "F2.1 next challenger selected"
        current_task = "Prepare the bounded F2.1 structured latent factor challenger while keeping F1 as the mainline."
        current_capability_boundary = (
            "F2.1 is selected as the next challenger, but it is not implemented yet; F1 remains the only verified mainline and no deeper model result exists yet."
        )
        current_strategy_focus = ["f1_elasticnet_v1", "f2_structured_latent_factor_v1"]
        current_strategy_summary = (
            f"{variant.display_label} was rejected on the return floor, so F2.1 is now the next implementation slot while F1 stays mainline."
        )

    state.update(
        {
            "current_phase": current_phase,
            "current_task": current_task,
            "current_blocker": blocker,
            "current_capability_boundary": current_capability_boundary,
            "next_priority_action": next_action,
            "last_verified_capability": (
                f"{variant.display_label} bounded verifier compared control, F1, and {variant.compare_label} on the same core universe and shared Top{topk} shell; "
                f"decision={decision_payload['decision']}."
            ),
            "last_failed_capability": "none" if blocker == "none" else blocker,
            "current_strategy_focus": current_strategy_focus,
            "current_strategy_summary": current_strategy_summary,
            "configured_subagent_gate_mode": "OFF",
            "effective_subagent_gate_mode": "OFF",
            "effective_subagent_gate_reason": f"{variant.display_label} is a tightly coupled verifier path; serial execution is cheaper and safer than spawning scouts.",
            "subagent_gate_mode": "OFF",
            "subagent_continue_reason": f"{variant.display_label} verifier stayed in OFF mode because this round was a tightly coupled serial implementation.",
            "next_build_target": (
                variant.strategy_candidate_id
                if decision_payload["decision"] != variant.reject_decision
                else variant.reject_next_build_target
            ),
            "current_secondary_strategy_ids": _dedupe(
                [
                    item
                    for item in (
                        variant.strategy_candidate_id if decision_payload["decision"] != variant.reject_decision else variant.followup_strategy_id,
                        "f2_structured_latent_factor_v1" if variant.strategy_candidate_id != "f2_structured_latent_factor_v1" else None,
                        "baseline_limit_up",
                        "risk_constrained_limit_up",
                        "tighter_entry_limit_up",
                    )
                    if item and item != "f1_elasticnet_v1"
                ]
            ),
            "current_rejected_strategy_ids": _dedupe(
                list(state.get("current_rejected_strategy_ids", []) or [])
                + ([variant.strategy_candidate_id] if decision_payload["decision"] == variant.reject_decision else [])
            ),
            "iterative_loop": {
                **dict(state.get("iterative_loop", {}) or {}),
                "stop_reason": "task_completed",
                "next_recommendation": next_action,
                "blocker_escalation": blocker != "none",
                "direction_change": decision_payload["decision"] == "promote_r1_control_layer_next",
            },
            "r1_verify_report_path": str(report_json_path),
            "r1_verify_decision": str(decision_payload["decision"]),
            "r1_verify_classification": str(decision_payload["classification"]),
        }
    )
    artifact_refs = [str(report_json_path), str(report_md_path)]
    state["strategy_candidates"] = _refresh_strategy_candidates(
        variant=variant,
        state=state,
        topk=topk,
        f1_metrics=f1_metrics,
        r1_metrics=r1_metrics,
        decision_payload=decision_payload,
        artifact_refs=artifact_refs,
    )
    save_machine_state(project, state, repo_root=repo_root)

    durable_facts = _dedupe(
        list(state.get("durable_facts", []) or [])
        + [
            f"{variant.display_label} is a bounded predictive-error overlay on top of F1; it only scales exposure and does not update F1 weights.",
            f"The latest {variant.display_label} verifier decision is {decision_payload['decision']}.",
        ]
    )
    prior_negative_memory = [
        str(item).replace("old 715-name legacy baseline output", "old legacy baseline output")
        for item in list(state.get("negative_memory", []) or [])
    ]
    negative_memory = _dedupe(
        prior_negative_memory
        + [
            f"Do not treat {variant.display_label} verifier output as promotion evidence or proof of profitability.",
            f"Do not let {variant.display_label} silently change F1 weights; this overlay family must stay exposure-only.",
        ]
    )
    next_step_memory = _dedupe([next_action, *list(state.get("next_step_memory", []) or [])])[:5]
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
                "status": "active" if decision_payload["decision"] != variant.reject_decision else "blocked",
                "hypothesis": variant.hypothesis,
            },
            {
                "status": "active" if decision_payload["decision"] == variant.reject_decision and variant.followup_strategy_id == "f2_structured_latent_factor_v1" else "pending",
                "hypothesis": "F2.1 structured latent deep factor should be the next model challenger if the overlay family still cannot clear the return floor.",
            },
            {
                "status": "deferred",
                "hypothesis": "Hybrid F1.5 should stay deferred until a frozen sidecar contract and offline reproducibility are proven.",
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
            "config_hash": stable_hash({"factor_model": report["factor_model"], "regime_control": report["regime_control"]}),
            "result": decision_payload["decision"],
            "blockers": decision_payload.get("primary_blockers", []),
            "artifact_refs": [
                str(report_json_path),
                str(report_md_path),
                *list(report.get("artifact_paths", {}).values()),
            ],
        },
        repo_root=repo_root,
    )
    write_verify_snapshot(
        project,
        {
            "passed_commands": [f"python -m quant_mvp r1_verify --project {project}"],
            "failed_commands": [],
            "default_project_data_status": state.get("verify_last", {}).get("default_project_data_status", "validation-ready"),
            "conclusion_boundary_engineering": f"{variant.display_label} bounded verifier now exists and compares control, F1, and {variant.compare_label} on one shared shell.",
            "conclusion_boundary_research": f"{variant.display_label} is still prototype-only. It may improve drawdown control, but this is not proof of profitability.",
            "last_verified_capability": state.get("last_verified_capability"),
        },
        repo_root=repo_root,
    )
    generate_handoff(project, repo_root=repo_root)


def _sync_r1_failure(
    *,
    variant: R1Variant,
    project: str,
    experiment_id: str,
    root_cause: str,
    artifact_refs: list[str],
    repo_root: Path | None = None,
) -> None:
    _, state = load_machine_state(project, repo_root=repo_root)
    state.update(
        {
            "current_phase": variant.current_phase,
            "current_task": f"Repair the {variant.display_label} verifier contract before trusting any {variant.compare_label} conclusion.",
            "current_blocker": root_cause,
            "current_capability_boundary": f"The {variant.display_label} path failed, so there is still no trustworthy bounded regime-overlay result.",
            "next_priority_action": f"Fix the {variant.display_label} freshness, leakage, or shared-shell contract and rerun r1_verify.",
            "last_failed_capability": root_cause,
            "configured_subagent_gate_mode": "OFF",
            "effective_subagent_gate_mode": "OFF",
            "effective_subagent_gate_reason": f"Keep serial repair until the {variant.display_label} verifier contract is stable.",
            "subagent_gate_mode": "OFF",
            "subagent_continue_reason": f"{variant.display_label} verifier failure stayed in OFF mode while the contract was repaired.",
            "iterative_loop": {
                **dict(state.get("iterative_loop", {}) or {}),
                "stop_reason": "verification_failed",
                "next_recommendation": f"Fix the {variant.display_label} verifier contract and rerun it before trusting any regime-overlay conclusion.",
                "blocker_escalation": True,
                "direction_change": False,
            },
        }
    )
    save_machine_state(project, state, repo_root=repo_root)
    sync_research_memory(
        project,
        durable_facts=list(state.get("durable_facts", []) or []),
        negative_memory=_dedupe(
            list(state.get("negative_memory", []) or [])
            + [f"Do not trust any {variant.display_label} conclusion while the bounded verifier contract is failing."]
        ),
        next_step_memory=_dedupe(
            [f"Fix the {variant.display_label} verifier contract and rerun it before choosing the next control-layer target.", *list(state.get("next_step_memory", []) or [])]
        )[:5],
        repo_root=repo_root,
    )
    update_hypothesis_queue(
        project,
        [
            {
                "status": "blocked",
                "hypothesis": variant.hypothesis,
            },
            {
                "status": "pending",
                "hypothesis": f"The {variant.display_label} verifier contract must be stable before any F2 or hybrid route is reconsidered.",
            },
        ],
        repo_root=repo_root,
    )
    record_failure(
        project,
        {
            "timestamp": _utc_now(),
            "experiment_id": experiment_id,
            "summary": f"{variant.display_label} bounded verifier failed.",
            "root_cause": root_cause,
            "corrective_action": "Repair the freshness, leakage, or shared-shell contract before rerunning the verifier.",
            "resolution_status": "not_fixed",
        },
        repo_root=repo_root,
        append_ledger=True,
        ledger_entry={
            "timestamp": _utc_now(),
            "experiment_id": experiment_id,
            "hypothesis": variant.hypothesis,
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
            "failed_commands": [f"python -m quant_mvp r1_verify --project {project}"],
            "default_project_data_status": state.get("verify_last", {}).get("default_project_data_status", "validation-ready"),
            "conclusion_boundary_engineering": f"The {variant.display_label} verifier interface exists, but this run failed before it produced a trustworthy result.",
            "conclusion_boundary_research": f"No new regime-overlay conclusion should be trusted from this failed {variant.display_label} verifier run.",
            "last_verified_capability": state.get("last_verified_capability"),
        },
        repo_root=repo_root,
    )
    generate_handoff(project, repo_root=repo_root)


def run_r1_verify(project: str, *, config_path: Path | None = None, repo_root: Path | None = None) -> dict[str, Any]:
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
        raise RuntimeError("R1 verifier requires an existing core pool snapshot.")

    regime_cfg = _regime_control_config(cfg)
    variant = _r1_variant(regime_cfg.profile)
    experiment_id = f"{project}__factor_elasticnet_core__{variant.profile}__{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
    experiment: Experiment | None = None
    try:
        f1_experiment = _load_latest_f1_experiment(project, repo_root=repo_root)
        f1_report = _load_f1_train_report(paths)
        topk = _validate_r1_freshness(
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

        hypothesis = variant.hypothesis
        experiment = new_experiment(
            project=project,
            experiment_id=experiment_id,
            hypothesis=hypothesis,
            mode="r1_verify",
            plan_steps=["freshness_check", "signal_build", "regime_overlay", "shared_shell_backtest", "r1_report"],
            success_criteria=[
                f"{variant.display_label} must compare control, F1, and {variant.compare_label} on the same core universe and shared TopN shell.",
                f"{variant.display_label} must stay bounded: exposure scaling only, no online weight updates, no new factor model training.",
            ],
            universe_snapshot=f1_experiment.universe_snapshot,
            dataset_snapshot=f1_experiment.dataset_snapshot,
            opportunity_spec=f1_experiment.opportunity_spec,
            subagent_tasks=[],
            factor_candidates=f1_experiment.factor_candidates,
            feature_view=f1_experiment.feature_view,
            label_spec=f1_experiment.label_spec,
            model_candidate=f1_experiment.model_candidate,
            regime_spec=RegimeSpec(
                regime_id=f"regime-{stable_hash(regime_cfg.to_dict())[:12]}",
                detector_name=variant.profile,
                transition_signal="lagged_ic_and_topk_shortfall_ewma",
                regime_transition_latency=1.0,
                adaptive_policy="exposure_scaling_only",
                notes=variant.notes,
            ),
            mission_id=f1_experiment.mission_id,
            branch_id="factor_elasticnet_core",
            core_universe_snapshot_id=core_snapshot.snapshot_id,
            branch_pool_snapshot_id=f1_experiment.branch_pool_snapshot_id,
            opportunity_generator_id=f1_experiment.opportunity_generator_id,
            strategy_candidate_id=variant.strategy_candidate_id,
        )
        write_experiment_record(experiment, repo_root=repo_root)

        control_rank = _build_control_rank(cfg=cfg, core_codes=list(core_snapshot.codes))
        f1_shared, control_shared = _intersect_rank_frames(f1_rank=f1_rank, control_rank=control_rank)
        candidate_scores = _load_candidate_scores(paths)
        label_frame = _load_label_frame(paths)
        signal_frame = _build_signal_frame(
            candidate_scores=candidate_scores,
            label_frame=label_frame,
            f1_shared_rank=f1_shared,
            regime_cfg=regime_cfg,
            topk=topk,
        )
        state_timeline = _build_state_timeline(signal_frame, regime_cfg)

        r1_dir = paths.artifacts_dir / "r1" / variant.artifact_slug
        r1_dir.mkdir(parents=True, exist_ok=True)
        signal_frame_path = r1_dir / "r1_signal_frame.parquet"
        state_timeline_path = r1_dir / "r1_state_timeline.csv"
        signal_frame.to_parquet(signal_frame_path, index=False)
        state_timeline.to_csv(state_timeline_path, index=False, encoding="utf-8-sig")

        all_codes = sorted(set(f1_shared["code"].tolist()) | set(control_shared["code"].tolist()))
        start = min(pd.Timestamp(f1_shared["date"].min()), pd.Timestamp(control_shared["date"].min()))
        end = max(pd.Timestamp(f1_shared["date"].max()), pd.Timestamp(control_shared["date"].max()))
        close_panel = _load_shared_close_panel(cfg=cfg, codes=all_codes, start=start, end=end)
        exposure_scale_by_date = _build_daily_exposure_schedule(calendar=close_panel.index.sort_values(), state_timeline=state_timeline)
        exposure_by_rebalance = {
            pd.Timestamp(row["date"]): float(row["exposure_scale"])
            for _, row in state_timeline.iterrows()
        }

        bt_cfg = _shared_backtest_config(cfg)
        control_curves, control_metrics_df = run_topn_suite(close_panel=close_panel, rank_df=control_shared, cfg=bt_cfg, topn_max=topk)
        f1_curves, f1_metrics_df = run_topn_suite(close_panel=close_panel, rank_df=f1_shared, cfg=bt_cfg, topn_max=topk)
        r1_curves, r1_metrics_df = run_topn_suite(
            close_panel=close_panel,
            rank_df=f1_shared,
            cfg=bt_cfg,
            topn_max=topk,
            exposure_scale_by_date=exposure_scale_by_date,
        )

        control_metrics = _topk_metrics(control_metrics_df, topk=topk)
        f1_metrics = _topk_metrics(f1_metrics_df, topk=topk)
        r1_metrics = _topk_metrics(r1_metrics_df, topk=topk)
        f1_turnover = _average_turnover(rank_df=f1_shared, topk=topk)
        r1_turnover = _average_turnover(rank_df=f1_shared, topk=topk, exposure_by_rebalance=exposure_by_rebalance)
        control_turnover = _average_turnover(rank_df=control_shared, topk=topk)
        control_metrics["turnover"] = control_turnover
        f1_metrics["turnover"] = f1_turnover
        r1_metrics["turnover"] = r1_turnover
        r1_metrics["false_trigger_rate"] = _false_trigger_rate(state_timeline)
        r1_metrics["regime_transition_drawdown"] = _regime_transition_drawdown(
            equity=r1_curves[f"Top{topk}"],
            exposure_scale_by_date=exposure_scale_by_date,
        )

        decision_payload = _decision_from_r1_metrics(
            variant=variant,
            f1_metrics=f1_metrics,
            r1_metrics=r1_metrics,
            f1_turnover=f1_turnover,
            r1_turnover=r1_turnover,
        )
        decision_text = _decision_texts(variant, decision_payload["decision"])

        metrics_output = r1_dir / "r1_vs_f1_vs_control_metrics.csv"
        pd.DataFrame(
            [
                {"series": "control", **control_metrics},
                {"series": "f1", **f1_metrics},
                {"series": "f1_plus_r1", **r1_metrics},
                {"series": "delta_vs_f1", **decision_payload["delta_metrics_vs_f1"]},
            ]
        ).to_csv(metrics_output, index=False, encoding="utf-8-sig")
        plot_output = _save_compare_plot(
            project=project,
            topk=topk,
            variant=variant,
            control_curves=control_curves,
            f1_curves=f1_curves,
            r1_curves=r1_curves,
            output_path=r1_dir / "r1_vs_f1_vs_control.png",
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
            "factor_model": dict(cfg.get("factor_model", {}) or {}),
            "regime_control": regime_cfg.to_dict(),
            "f1_metrics": f1_metrics,
            "r1_metrics": r1_metrics,
            "control_metrics": control_metrics,
            "delta_metrics_vs_f1": decision_payload["delta_metrics_vs_f1"],
            "decision": decision_payload["decision"],
            "classification": decision_payload["classification"],
            "next_action": decision_text["next_action"],
            "primary_blockers": decision_payload["primary_blockers"],
            "artifact_paths": {
                "source_f1_experiment_path": str(paths.experiments_dir / f"{f1_experiment.experiment_id}.json"),
                "source_f1_rank_path": str(f1_rank_path),
                "signal_frame_path": str(signal_frame_path),
                "state_timeline_path": str(state_timeline_path),
                "metrics_csv_path": str(metrics_output),
                "plot_path": str(plot_output),
            },
        }
        report_json_path, report_md_path = _write_report(output_dir=r1_dir, report=report)
        report["artifact_paths"]["report_json_path"] = str(report_json_path)
        report["artifact_paths"]["report_md_path"] = str(report_md_path)
        report_json_path, report_md_path = _write_report(output_dir=r1_dir, report=report)

        summary = decision_text["summary"]
        evaluation = EvaluationRecord(
            status="r1_bounded_verifier",
            summary=summary,
            classification=decision_payload["classification"],
            primary_blockers=list(decision_payload["primary_blockers"]),
            promotion_decision={"evaluated": False, "reason": "bounded_r1_only", "decision": decision_payload["decision"]},
            next_experiment_themes=[
                (
                    f"If {variant.display_label} is promoted, integrate it as the next bounded control layer before reopening F2.1."
                    if variant.followup_strategy_id == "f2_structured_latent_factor_v1"
                    else f"If {variant.display_label} is promoted, integrate it as the next bounded control layer before reopening broader scouting."
                ),
                (
                    "If the softer overlay still fails the return floor, promote F2.1 to the next implementation slot."
                    if variant.followup_strategy_id == "f2_structured_latent_factor_v1"
                    else f"If {variant.display_label} is not promoted, keep F1 mainline and re-run frontier reselection before deeper model work."
                ),
            ],
            adversarial_robustness={"status": "not_evaluated", "score": None},
            regime_transition_drawdown=r1_metrics.get("regime_transition_drawdown"),
        )
        execution = {
            "executed_steps": list(experiment.plan_steps),
            "outputs": {
                "freshness_check": {
                    "source_f1_experiment_id": f1_experiment.experiment_id,
                    "core_snapshot_id": core_snapshot.snapshot_id,
                    "factor_profile": str((cfg.get("factor_model", {}) or {}).get("profile", "unknown")),
                },
                "signal_build": {
                    "signal_frame_path": str(signal_frame_path),
                    "state_timeline_path": str(state_timeline_path),
                },
                "regime_overlay": {
                    "regime_profile": regime_cfg.profile,
                    "active_regime_days": int(sum(1 for value in exposure_scale_by_date.values() if float(value) < 1.0)),
                },
                "shared_shell_backtest": {
                    "metrics_path": str(metrics_output),
                    "plot_path": str(plot_output),
                },
                "r1_report": {"json_path": str(report_json_path), "md_path": str(report_md_path)},
            },
        }
        experiment = update_experiment(
            experiment,
            status="evaluated",
            execution=execution,
            evaluation=evaluation,
            artifact_refs=[
                str(signal_frame_path),
                str(state_timeline_path),
                str(metrics_output),
                str(plot_output),
                str(report_json_path),
                str(report_md_path),
            ],
        )
        experiment_path = write_experiment_record(experiment, repo_root=repo_root)
        report["artifact_paths"]["experiment_record_path"] = str(experiment_path)
        report_json_path, report_md_path = _write_report(output_dir=r1_dir, report=report)

        update_run_manifest(
            project,
            {
                "r1_verifier": {
                    "profile": regime_cfg.profile,
                    "core_snapshot_id": core_snapshot.snapshot_id,
                    "source_f1_experiment_id": f1_experiment.experiment_id,
                    "signal_frame_path": str(signal_frame_path),
                    "state_timeline_path": str(state_timeline_path),
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
        _sync_r1_memory(
            variant=variant,
            project=project,
            decision_payload=decision_payload,
            topk=topk,
            experiment_id=experiment_id,
            report_json_path=report_json_path,
            report_md_path=report_md_path,
            f1_metrics=f1_metrics,
            r1_metrics=r1_metrics,
            report=report,
            repo_root=repo_root,
        )
        if decision_payload["decision"] == variant.reject_decision:
            record_failure(
                project,
                {
                    "timestamp": _utc_now(),
                    "experiment_id": experiment_id,
                    "summary": f"{variant.display_label} bounded verifier did not preserve enough economics to clear the gate.",
                    "root_cause": "; ".join(decision_payload["primary_blockers"]) or f"{variant.display_label} decision rule did not pass.",
                    "corrective_action": decision_text["next_action"],
                    "resolution_status": "not_fixed",
                },
                repo_root=repo_root,
                preserve_progress=True,
            )
        if decision_payload["decision"] in {"promote_r1_control_layer_next", variant.reject_decision}:
            _append_repo_decision_log(repo_root=paths.root, project=project, report=report, variant=variant)

        return {
            "experiment_id": experiment_id,
            "experiment_record_path": str(experiment_path),
            "report_json_path": str(report_json_path),
            "report_md_path": str(report_md_path),
            "signal_frame_path": str(signal_frame_path),
            "state_timeline_path": str(state_timeline_path),
            "metrics_path": str(metrics_output),
            "plot_path": str(plot_output),
            "decision": decision_payload["decision"],
            "classification": decision_payload["classification"],
            "next_action": decision_text["next_action"],
            "f1_metrics": f1_metrics,
            "r1_metrics": r1_metrics,
            "control_metrics": control_metrics,
            "delta_metrics_vs_f1": decision_payload["delta_metrics_vs_f1"],
        }
    except Exception as exc:
        artifact_refs: list[str] = []
        if experiment is not None:
            evaluation = EvaluationRecord(
                status="failed",
                summary=f"{variant.display_label} bounded verifier failed: {exc}",
                classification="verifier_fail",
                primary_blockers=[str(exc)],
                promotion_decision={"evaluated": False, "reason": "r1_verifier_failed"},
                next_experiment_themes=[f"Repair the freshness, leakage, or shared-shell contract before rerunning the {variant.display_label} verifier."],
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
        _sync_r1_failure(
            variant=variant,
            project=project,
            experiment_id=experiment_id,
            root_cause=str(exc),
            artifact_refs=artifact_refs,
            repo_root=repo_root,
        )
        raise
