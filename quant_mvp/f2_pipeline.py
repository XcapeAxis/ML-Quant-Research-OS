from __future__ import annotations

import json
import warnings
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning
from sklearn.neural_network import MLPRegressor

from .backtest_engine import BacktestConfig, run_topn_suite
from .config import load_config
from .db import load_close_volume_panel
from .experiment_graph import (
    EvaluationRecord,
    FactorCandidate,
    FeatureView,
    LabelSpec,
    ModelCandidate,
    OpportunitySpec,
    RegimeSpec,
    build_dataset_snapshot,
    build_universe_snapshot,
    new_experiment,
    update_experiment,
    write_experiment_record,
)
from .f1_pipeline import (
    _build_label_frame,
    _cross_sectional_preprocess,
    _dedupe,
    _load_benchmark_close,
    _monthly_retrain_dates,
    _rebalance_dates,
    _save_curve_plot,
    _stack_panel,
    _topn_metrics,
)
from .factors import compute_factor_panel
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
)
from .pools import load_latest_core_pool_snapshot
from .project import resolve_project_paths


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class DeepFactorModelConfig:
    profile: str
    base_feature_names: tuple[str, ...]
    group_features: bool
    latent_dim: int
    hidden_sizes: tuple[int, ...]
    activation: str
    alpha: float
    learning_rate_init: float
    max_iter: int
    early_stopping: bool
    validation_fraction: float
    random_state: int
    label_horizon_days: int
    refit_frequency: str
    training_window_days: int
    min_train_days: int
    winsorize_quantile: float
    standardization: str

    @property
    def group_feature_names(self) -> tuple[str, ...]:
        return ("momentum_block", "risk_block", "liquidity_block") if self.group_features else ()

    @property
    def feature_names(self) -> tuple[str, ...]:
        return (*self.base_feature_names, *self.group_feature_names)

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "base_feature_names": list(self.base_feature_names),
            "group_features": self.group_features,
            "latent_dim": self.latent_dim,
            "hidden_sizes": list(self.hidden_sizes),
            "activation": self.activation,
            "alpha": self.alpha,
            "learning_rate_init": self.learning_rate_init,
            "max_iter": self.max_iter,
            "early_stopping": self.early_stopping,
            "validation_fraction": self.validation_fraction,
            "random_state": self.random_state,
            "label_horizon_days": self.label_horizon_days,
            "refit_frequency": self.refit_frequency,
            "training_window_days": self.training_window_days,
            "min_train_days": self.min_train_days,
            "winsorize_quantile": self.winsorize_quantile,
            "standardization": self.standardization,
        }


def _deep_factor_model_config(cfg: dict[str, Any]) -> DeepFactorModelConfig:
    raw = dict(cfg.get("deep_factor_model", {}) or {})
    model_cfg = DeepFactorModelConfig(
        profile=str(raw.get("profile", "f2_structured_latent_factor_v1")),
        base_feature_names=tuple(
            str(item).strip() for item in raw.get("base_feature_names", []) if str(item).strip()
        ),
        group_features=bool(raw.get("group_features", True)),
        latent_dim=int(raw.get("latent_dim", 4)),
        hidden_sizes=tuple(int(item) for item in raw.get("hidden_sizes", [12, 4])),
        activation=str(raw.get("activation", "relu")),
        alpha=float(raw.get("alpha", 0.0001)),
        learning_rate_init=float(raw.get("learning_rate_init", 0.001)),
        max_iter=int(raw.get("max_iter", 300)),
        early_stopping=bool(raw.get("early_stopping", True)),
        validation_fraction=float(raw.get("validation_fraction", 0.1)),
        random_state=int(raw.get("random_state", 42)),
        label_horizon_days=int(raw.get("label_horizon_days", 5)),
        refit_frequency=str(raw.get("refit_frequency", "monthly")),
        training_window_days=int(raw.get("training_window_days", 756)),
        min_train_days=int(raw.get("min_train_days", 504)),
        winsorize_quantile=float(raw.get("winsorize_quantile", 0.01)),
        standardization=str(raw.get("standardization", "cross_sectional_zscore")),
    )
    if not model_cfg.base_feature_names:
        raise ValueError("deep_factor_model.base_feature_names cannot be empty")
    if not model_cfg.hidden_sizes:
        raise ValueError("deep_factor_model.hidden_sizes cannot be empty")
    if model_cfg.hidden_sizes[-1] != model_cfg.latent_dim:
        raise ValueError("deep_factor_model.latent_dim must match the final hidden layer size")
    return model_cfg


def build_f2_training_contract_payload(
    *,
    cfg: dict[str, Any],
    model_cfg: DeepFactorModelConfig,
    core_snapshot_id: str,
) -> dict[str, Any]:
    baselines = dict(cfg.get("baselines", {}) or {})
    return {
        "core_snapshot_id": core_snapshot_id,
        "profile": model_cfg.profile,
        "deep_factor_model": model_cfg.to_dict(),
        "benchmark_code": str(baselines.get("benchmark_code", "000001")).zfill(6),
        "freq": str(cfg.get("freq", "1d")),
        "rebalance_every": int(cfg.get("rebalance_every", model_cfg.label_horizon_days)),
        "topk": int(cfg.get("topk", 6)),
        "topn_max": int(cfg.get("topn_max", int(cfg.get("topk", 6)))),
        "start_date": cfg.get("start_date"),
        "end_date": cfg.get("end_date"),
    }


def build_f2_training_contract_hash(
    *,
    cfg: dict[str, Any],
    model_cfg: DeepFactorModelConfig,
    core_snapshot_id: str,
) -> str:
    return stable_hash(
        build_f2_training_contract_payload(
            cfg=cfg,
            model_cfg=model_cfg,
            core_snapshot_id=core_snapshot_id,
        )
    )


def _build_group_features(feature_frame: pd.DataFrame) -> pd.DataFrame:
    frame = feature_frame.copy()
    frame["momentum_block"] = frame.loc[:, ["mom20", "rev5", "ma_gap"]].mean(axis=1)
    frame["risk_block"] = frame.loc[:, ["vol20", "range"]].mean(axis=1)
    frame["liquidity_block"] = frame.loc[:, ["vol_surge", "adv20", "amihud20"]].mean(axis=1)
    return frame


def _build_factor_candidates(model_cfg: DeepFactorModelConfig) -> list[FactorCandidate]:
    family_map = {
        "mom20": "technical_momentum",
        "rev5": "technical_reversal",
        "vol20": "risk_volatility",
        "range": "risk_range",
        "vol_surge": "liquidity_activity",
        "ma_gap": "technical_trend",
        "adv20": "liquidity_turnover",
        "amihud20": "liquidity_impact",
        "momentum_block": "structured_group",
        "risk_block": "structured_group",
        "liquidity_block": "structured_group",
    }
    description_map = {
        "mom20": "20-day momentum.",
        "rev5": "5-day short-term reversal.",
        "vol20": "20-day realized volatility.",
        "range": "20-day mean absolute return.",
        "vol_surge": "Volume versus its 20-day mean.",
        "ma_gap": "Distance to the 20-day moving average.",
        "adv20": "20-day rolling average daily turnover proxy using close * volume.",
        "amihud20": "20-day rolling Amihud-style illiquidity proxy.",
        "momentum_block": "Structured momentum group from mom20, rev5, and ma_gap.",
        "risk_block": "Structured risk group from vol20 and range.",
        "liquidity_block": "Structured liquidity group from vol_surge, adv20, and amihud20.",
    }
    candidates: list[FactorCandidate] = []
    for name in model_cfg.feature_names:
        payload = {"profile": model_cfg.profile, "feature": name}
        candidates.append(
            FactorCandidate(
                factor_id=f"factor-{stable_hash(payload)[:12]}",
                name=name,
                family=family_map.get(name, "factor"),
                description=description_map.get(name, "Structured factor feature."),
                params={"profile": model_cfg.profile},
                source="f2_deep_factor_model",
                status="prototype",
                tags=["stage_f2", "deep_factor_model", model_cfg.profile],
            )
        )
    return candidates


def _feature_view(model_cfg: DeepFactorModelConfig, freq: str) -> FeatureView:
    payload = {
        "profile": model_cfg.profile,
        "feature_names": list(model_cfg.feature_names),
        "freq": freq,
    }
    return FeatureView(
        feature_view_id=f"feature-view-{stable_hash(payload)[:12]}",
        name="technical_liquidity_panel_v2_structured",
        inputs=["daily_ohlcv", "core_pool_membership"],
        transforms=[
            "cross_sectional_winsorize_0.01",
            "cross_sectional_zscore",
            "structured_group_blocks",
        ],
        sampling=f"{freq} cross_sectional_panel",
        notes="F2.1 reuses F1 technical/liquidity inputs and adds structured group blocks before the latent bottleneck.",
    )


def _label_spec(model_cfg: DeepFactorModelConfig) -> LabelSpec:
    payload = {
        "profile": model_cfg.profile,
        "target": "next_5d_excess_return",
        "horizon": model_cfg.label_horizon_days,
    }
    return LabelSpec(
        label_spec_id=f"label-{stable_hash(payload)[:12]}",
        target_name="next_5d_excess_return",
        horizon=str(model_cfg.label_horizon_days),
        objective="cross_sectional_ranking",
        definition="Future 5-day stock return minus the configured benchmark's future 5-day return.",
        notes="F2.1 shares the same excess-return label contract as F1.",
    )


def _model_candidate(model_cfg: DeepFactorModelConfig) -> ModelCandidate:
    return ModelCandidate(
        model_id=f"model-{stable_hash(model_cfg.to_dict())[:12]}",
        name="f2_structured_latent_factor_v1",
        family="mlp_structured_latent_factor",
        params={
            "hidden_sizes": list(model_cfg.hidden_sizes),
            "activation": model_cfg.activation,
            "alpha": model_cfg.alpha,
            "learning_rate_init": model_cfg.learning_rate_init,
            "max_iter": model_cfg.max_iter,
            "early_stopping": model_cfg.early_stopping,
            "validation_fraction": model_cfg.validation_fraction,
            "latent_dim": model_cfg.latent_dim,
        },
        is_online_adaptive=False,
        update_frequency="monthly",
        training_mode="batch",
        notes="Bounded structured latent challenger inside the current scikit-learn stack.",
    )


def _regime_spec() -> RegimeSpec:
    return RegimeSpec(
        regime_id=f"regime-{stable_hash({'detector_name': 'static_baseline'})[:12]}",
        detector_name="static_baseline",
        transition_signal="not_enabled",
        regime_transition_latency=None,
        adaptive_policy="static",
        notes="F2.1 keeps the static regime placeholder; R-series overlays remain separate.",
    )


def _opportunity_spec(model_cfg: DeepFactorModelConfig, hypothesis: str) -> OpportunitySpec:
    return OpportunitySpec(
        strategy_mode="deep_factor_model",
        hypothesis=hypothesis,
        params={
            "profile": model_cfg.profile,
            "feature_names": list(model_cfg.feature_names),
            "label_horizon_days": model_cfg.label_horizon_days,
            "latent_dim": model_cfg.latent_dim,
        },
    )


def _build_feature_frame(
    *,
    close: pd.DataFrame,
    volume: pd.DataFrame,
    model_cfg: DeepFactorModelConfig,
) -> pd.DataFrame:
    processed: dict[str, pd.DataFrame] = {}
    for name in model_cfg.base_feature_names:
        panel = compute_factor_panel(name, close=close, volume=volume)
        processed[name] = _cross_sectional_preprocess(panel, winsorize_quantile=model_cfg.winsorize_quantile)

    if model_cfg.group_features:
        grouped_panels = {
            "momentum_block": (processed["mom20"] + processed["rev5"] + processed["ma_gap"]) / 3.0,
            "risk_block": (processed["vol20"] + processed["range"]) / 2.0,
            "liquidity_block": (
                processed["vol_surge"] + processed["adv20"] + processed["amihud20"]
            )
            / 3.0,
        }
        for name, panel in grouped_panels.items():
            processed[name] = _cross_sectional_preprocess(
                panel,
                winsorize_quantile=model_cfg.winsorize_quantile,
            )

    feature_frame = pd.concat(
        [_stack_panel(panel, name) for name, panel in processed.items()],
        axis=1,
    ).reset_index()
    feature_frame.columns = ["date", "code", *processed.keys()]
    feature_frame["date"] = pd.to_datetime(feature_frame["date"])
    feature_frame["code"] = feature_frame["code"].astype(str).str.zfill(6)
    feature_frame = feature_frame.dropna(subset=list(model_cfg.feature_names), how="all")
    return feature_frame.sort_values(["date", "code"]).reset_index(drop=True)


def _hidden_activation(values: np.ndarray, activation: str) -> np.ndarray:
    if activation == "relu":
        return np.maximum(values, 0.0)
    if activation == "tanh":
        return np.tanh(values)
    if activation == "logistic":
        return 1.0 / (1.0 + np.exp(-values))
    if activation == "identity":
        return values
    raise ValueError(f"Unsupported MLP activation for latent extraction: {activation}")


def _latent_from_model(model: MLPRegressor, feature_matrix: pd.DataFrame | np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    features = np.asarray(feature_matrix, dtype=float)
    activations = features
    latent = features
    hidden_count = len(model.coefs_) - 1
    for idx, (coef, intercept) in enumerate(zip(model.coefs_[:-1], model.intercepts_[:-1], strict=False)):
        activations = _hidden_activation(np.dot(activations, coef) + intercept, model.activation)
        if idx == hidden_count - 1:
            latent = activations
    scores = np.dot(latent, model.coefs_[-1]) + model.intercepts_[-1]
    if scores.ndim == 2 and scores.shape[1] == 1:
        scores = scores[:, 0]
    return latent, np.asarray(scores, dtype=float).reshape(-1)


def _fit_model(model_cfg: DeepFactorModelConfig, train_df: pd.DataFrame) -> MLPRegressor:
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=ConvergenceWarning)
        model = MLPRegressor(
            hidden_layer_sizes=tuple(model_cfg.hidden_sizes),
            activation=model_cfg.activation,
            solver="adam",
            alpha=model_cfg.alpha,
            learning_rate_init=model_cfg.learning_rate_init,
            max_iter=model_cfg.max_iter,
            early_stopping=model_cfg.early_stopping,
            validation_fraction=model_cfg.validation_fraction,
            random_state=model_cfg.random_state,
        )
        model.fit(train_df.loc[:, list(model_cfg.feature_names)], train_df["next_5d_excess_return"])
    return model


def _train_and_score(
    *,
    feature_frame: pd.DataFrame,
    label_frame: pd.DataFrame,
    calendar: pd.DatetimeIndex,
    rebalance_dates: list[pd.Timestamp],
    model_cfg: DeepFactorModelConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, list[dict[str, Any]]]:
    joined = feature_frame.merge(label_frame, on=["date", "code"], how="left")
    date_positions = {pd.Timestamp(item): idx for idx, item in enumerate(calendar)}
    joined["date_pos"] = joined["date"].map(date_positions)
    joined = joined.dropna(subset=["date_pos"]).copy()
    joined["date_pos"] = joined["date_pos"].astype(int)

    retrain_dates = _monthly_retrain_dates(calendar)
    all_scores: list[pd.DataFrame] = []
    all_latent: list[pd.DataFrame] = []
    train_runs: list[dict[str, Any]] = []

    for idx, retrain_date in enumerate(retrain_dates):
        retrain_pos = date_positions.get(pd.Timestamp(retrain_date))
        if retrain_pos is None:
            continue
        train_start_pos = max(0, retrain_pos - model_cfg.training_window_days)
        train_end_exclusive = retrain_pos - model_cfg.label_horizon_days
        if train_end_exclusive - train_start_pos < model_cfg.min_train_days:
            continue

        next_retrain_date = retrain_dates[idx + 1] if idx + 1 < len(retrain_dates) else None
        score_dates = [
            pd.Timestamp(item)
            for item in rebalance_dates
            if pd.Timestamp(item) >= pd.Timestamp(retrain_date)
            and (next_retrain_date is None or pd.Timestamp(item) < pd.Timestamp(next_retrain_date))
        ]
        if not score_dates:
            continue

        train_mask = (joined["date_pos"] >= train_start_pos) & (joined["date_pos"] < train_end_exclusive)
        train_df = joined.loc[train_mask].dropna(subset=[*model_cfg.feature_names, "next_5d_excess_return"]).copy()
        if train_df.empty:
            continue

        model = _fit_model(model_cfg, train_df)
        score_df = feature_frame.loc[
            feature_frame["date"].isin(score_dates)
        ].dropna(subset=list(model_cfg.feature_names)).copy()
        if score_df.empty:
            continue

        latent_values, scores = _latent_from_model(model, score_df.loc[:, list(model_cfg.feature_names)])
        latent_columns = [f"latent_{latent_idx + 1}" for latent_idx in range(model_cfg.latent_dim)]
        score_df["score"] = scores
        score_df["retrain_date"] = pd.Timestamp(retrain_date)
        latent_frame = score_df.loc[:, ["date", "code"]].copy()
        latent_frame["retrain_date"] = pd.Timestamp(retrain_date)
        for latent_idx, column in enumerate(latent_columns):
            latent_frame[column] = latent_values[:, latent_idx]

        all_scores.append(score_df.loc[:, ["date", "code", "score", "retrain_date"]])
        all_latent.append(latent_frame)
        train_runs.append(
            {
                "retrain_date": pd.Timestamp(retrain_date).strftime("%Y-%m-%d"),
                "train_start_date": calendar[train_start_pos].strftime("%Y-%m-%d"),
                "train_end_date": calendar[train_end_exclusive - 1].strftime("%Y-%m-%d"),
                "train_row_count": int(len(train_df)),
                "score_date_count": int(len(score_dates)),
            }
        )

    if not all_scores:
        raise RuntimeError(
            "F2 produced no scored rebalance dates; check the training window, label horizon, or feature coverage."
        )

    candidate_scores = pd.concat(all_scores, ignore_index=True).sort_values(
        ["date", "score", "code"],
        ascending=[True, False, True],
    )
    candidate_scores["date"] = pd.to_datetime(candidate_scores["date"])
    candidate_scores["code"] = candidate_scores["code"].astype(str).str.zfill(6)
    candidate_scores["rank"] = candidate_scores.groupby("date").cumcount() + 1

    latent_frame = pd.concat(all_latent, ignore_index=True).sort_values(["date", "code"]).reset_index(drop=True)
    latent_frame["date"] = pd.to_datetime(latent_frame["date"])
    latent_frame["code"] = latent_frame["code"].astype(str).str.zfill(6)

    return candidate_scores.reset_index(drop=True), latent_frame, train_runs


def _refresh_strategy_candidates_train(
    *,
    state: dict[str, Any],
    topk: int,
    topk_metrics: dict[str, Any],
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
            candidate["next_validation"] = "Keep F1 as the verified mainline while F2.1 is trained and then compared under the same shared shell."
        elif strategy_id == "f2_structured_latent_factor_v1":
            saw_f2 = True
            candidate["track"] = "secondary"
            candidate["decision"] = "continue"
            candidate["current_stage"] = "prototype_trained"
            candidate["latest_action"] = "Completed the first bounded structured latent deep-factor prototype training run."
            candidate["latest_result"] = (
                f"F2.1 prototype Top{topk}: annualized_return={float(topk_metrics.get('annualized_return', 0.0)):.2%}, "
                f"max_drawdown={abs(float(topk_metrics.get('max_drawdown', 0.0))):.2%}, "
                f"sharpe={float(topk_metrics.get('sharpe_ratio', 0.0)):.4f}."
            )
            candidate["next_validation"] = "Run f2_verify against control and F1 under one shared shell."
            candidate["artifact_refs"] = _dedupe(list(candidate.get("artifact_refs", []) or []) + artifact_refs)
        updated.append(candidate)

    if not saw_f1:
        updated.append(
            {
                "strategy_id": "f1_elasticnet_v1",
                "name": "F1 ElasticNet Mainline",
                "category": "factor_model",
                "core_hypothesis": "A regularized cross-sectional factor model should outperform the legacy control branch on the same core universe.",
                "economic_rationale": "F1 is the current verified mainline and remains the reference point for every bounded challenger.",
                "required_data": "Core universe snapshot, technical/liquidity feature panel, next_5d_excess_return label, shared-shell TopN backtest.",
                "current_stage": "validation",
                "latest_action": "Retained as the verified mainline while F2.1 is trained.",
                "latest_result": "F1 remains the current mainline until F2.1 finishes a fair shared-shell verifier.",
                "decision": "continue",
                "next_validation": "Keep F1 as the verified mainline while F2.1 is trained and then compared under the same shared shell.",
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
                "current_stage": "prototype_trained",
                "latest_action": "Completed the first bounded structured latent deep-factor prototype training run.",
                "latest_result": (
                    f"F2.1 prototype Top{topk}: annualized_return={float(topk_metrics.get('annualized_return', 0.0)):.2%}, "
                    f"max_drawdown={abs(float(topk_metrics.get('max_drawdown', 0.0))):.2%}, "
                    f"sharpe={float(topk_metrics.get('sharpe_ratio', 0.0)):.4f}."
                ),
                "decision": "continue",
                "next_validation": "Run f2_verify against control and F1 under one shared shell.",
                "owner": "main",
                "subagents_assigned": [],
                "artifact_refs": list(artifact_refs),
                "blocked_by": [],
                "kill_criteria": "If F2.1 cannot improve F1's tradeoff under the same shared shell, it should not remain the next challenger.",
                "track": "secondary",
            }
        )
    return updated


def _sync_success_memory(
    *,
    project: str,
    topk: int,
    topk_metrics: dict[str, Any],
    experiment_id: str,
    report_path: Path,
    repo_root: Path | None = None,
) -> None:
    _, state = load_machine_state(project, repo_root=repo_root)
    max_drawdown = float(topk_metrics.get("max_drawdown", 0.0) or 0.0)
    blocker = (
        f"F2.1 prototype Top{topk} max_drawdown {max_drawdown:.2%} remains above 30.00%."
        if abs(max_drawdown) > 0.30
        else "none"
    )
    state.update(
        {
            "current_phase": "F2.1 bounded challenger",
            "current_task": "Train and inspect the first bounded structured latent deep-factor challenger while keeping F1 as the mainline.",
            "current_blocker": blocker,
            "current_capability_boundary": "F2.1 now runs end-to-end as a bounded challenger only; it is not promotion evidence and it does not replace F1.",
            "next_priority_action": "Run f2_verify to compare control, F1, and F2.1 under one shared shell before any broader model search.",
            "last_verified_capability": "F2.1 prototype ran end-to-end on the latest core pool and wrote structured feature, latent, score, rank, and experiment artifacts.",
            "last_failed_capability": "none" if blocker == "none" else blocker,
            "current_strategy_focus": ["f1_elasticnet_v1", "f2_structured_latent_factor_v1"],
            "current_strategy_summary": "F2.1 prototype trained successfully; the next gate is one bounded shared-shell verifier versus F1 and control.",
            "next_build_target": "f2_structured_latent_factor_v1",
            "configured_subagent_gate_mode": "OFF",
            "effective_subagent_gate_mode": "OFF",
            "effective_subagent_gate_reason": "F2.1 implementation is a tightly coupled train-and-verify path, so serial execution is cheaper than splitting scouts.",
            "subagent_gate_mode": "OFF",
            "subagent_continue_reason": "F2.1 stayed in OFF mode because this round was a tightly coupled serial implementation.",
            "f2_train_report_path": str(report_path),
        }
    )
    artifact_refs = [str(report_path)]
    state["strategy_candidates"] = _refresh_strategy_candidates_train(
        state=state,
        topk=topk,
        topk_metrics=topk_metrics,
        artifact_refs=artifact_refs,
    )
    save_machine_state(project, state, repo_root=repo_root)

    durable_facts = _dedupe(
        list(state.get("durable_facts", []) or [])
        + [
            "F2.1 is a bounded structured latent deep-factor challenger implemented inside the current scikit-learn stack.",
            "F2.1 reuses the same core universe, label contract, and monthly retrain rhythm as F1.",
            "F2.1 writes a latent-factor audit artifact instead of keeping only final scores.",
        ]
    )
    negative_memory = _dedupe(
        list(state.get("negative_memory", []) or [])
        + [
            "Do not treat F2.1 prototype metrics as promotion evidence or profitability proof.",
            "Do not silently replace F1 with F2.1 before the shared-shell verifier completes.",
            "Do not widen F2.1 into heavy dependencies when the bounded scikit-learn prototype has not been verified yet.",
        ]
    )
    next_step_memory = _dedupe(
        [
            "Run f2_verify under the same core universe and shared shell before any broader model search.",
            "Keep F1 as the current mainline while F2.1 is only a bounded challenger.",
            *list(state.get("next_step_memory", []) or []),
        ]
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
                "hypothesis": "A bounded structured latent deep-factor model can improve F1's return/drawdown tradeoff on the same core universe without heavy dependencies.",
            },
            {
                "status": "pending",
                "hypothesis": "F2.1 should be judged only after one fair shared-shell comparison against control and F1.",
            },
            {
                "status": "pending",
                "hypothesis": "If F2.1 fails under the shared shell, the platform should reselect the next challenger instead of silently widening dependencies.",
            },
        ],
        repo_root=repo_root,
    )
    record_experiment_result(
        project,
        {
            "timestamp": _utc_now(),
            "experiment_id": experiment_id,
            "hypothesis": "Structured latent deep-factor bounded prototype",
            "config_hash": stable_hash({"topk": topk, "report_path": str(report_path)}),
            "result": "prototype_deep_factor_result",
            "blockers": [] if blocker == "none" else [blocker],
            "artifact_refs": artifact_refs,
        },
        repo_root=repo_root,
    )
    generate_handoff(project, repo_root=repo_root)


def _sync_failure_memory(
    *,
    project: str,
    experiment_id: str,
    root_cause: str,
    report_paths: list[str],
    repo_root: Path | None = None,
) -> None:
    _, state = load_machine_state(project, repo_root=repo_root)
    state.update(
        {
            "current_phase": "F2.1 bounded challenger",
            "current_task": "Repair the F2.1 bounded deep-factor contract before trusting it as the next challenger.",
            "current_blocker": root_cause,
            "current_capability_boundary": "F2.1 failed before the bounded challenger contract stabilized, so F1 remains the only trustworthy mainline.",
            "next_priority_action": "Fix the F2.1 feature, latent, or training contract and rerun f2_train.",
            "last_failed_capability": root_cause,
            "configured_subagent_gate_mode": "OFF",
            "effective_subagent_gate_mode": "OFF",
            "effective_subagent_gate_reason": "Keep F2.1 repair serial until its train contract is stable.",
            "current_strategy_focus": ["f1_elasticnet_v1", "f2_structured_latent_factor_v1"],
            "next_build_target": "f2_structured_latent_factor_v1",
        }
    )
    save_machine_state(project, state, repo_root=repo_root)
    update_hypothesis_queue(
        project,
        [
            {
                "status": "blocked",
                "hypothesis": "A bounded structured latent deep-factor model can improve F1's return/drawdown tradeoff on the same core universe without heavy dependencies.",
            },
            {
                "status": "pending",
                "hypothesis": "Repair the F2.1 train contract before any fair shared-shell verifier is attempted.",
            },
        ],
        repo_root=repo_root,
    )
    record_failure(
        project,
        {
            "timestamp": _utc_now(),
            "experiment_id": experiment_id,
            "summary": "F2.1 bounded prototype failed.",
            "root_cause": root_cause,
            "corrective_action": "Fix the feature, latent, or training contract before rerunning the bounded challenger.",
            "resolution_status": "not_fixed",
        },
        repo_root=repo_root,
        append_ledger=True,
        ledger_entry={
            "timestamp": _utc_now(),
            "experiment_id": experiment_id,
            "hypothesis": "Structured latent deep-factor bounded prototype",
            "result": "failed",
            "blockers": [root_cause],
            "artifact_refs": report_paths,
        },
        preserve_progress=True,
    )
    generate_handoff(project, repo_root=repo_root)


def run_f2_train(project: str, *, config_path: Path | None = None, repo_root: Path | None = None) -> dict[str, Any]:
    cfg, paths = load_config(project, config_path=config_path)
    if repo_root is not None:
        paths = resolve_project_paths(project, root=repo_root)
    paths.ensure_dirs()
    model_cfg = _deep_factor_model_config(cfg)

    core_snapshot = load_latest_core_pool_snapshot(
        project,
        repo_root=repo_root,
        build_if_missing=False,
        config_path=config_path,
    )
    if core_snapshot is None or not core_snapshot.codes:
        raise RuntimeError("F2 requires an existing core universe snapshot; it will not fall back to legacy universe_codes.txt.")

    universe_snapshot = build_universe_snapshot(
        codes=core_snapshot.codes,
        source_path=paths.pools_dir / "latest_core_pool.json",
    )
    dataset_report = {
        "coverage_ratio": 1.0,
        "symbols_with_validated_bars": len(core_snapshot.codes),
        "core_universe_snapshot_id": core_snapshot.snapshot_id,
        "source": "latest_core_pool_snapshot",
    }
    dataset_snapshot = build_dataset_snapshot(
        report=dataset_report,
        cfg=cfg,
        universe_snapshot=universe_snapshot,
    )
    contract_payload = build_f2_training_contract_payload(
        cfg=cfg,
        model_cfg=model_cfg,
        core_snapshot_id=core_snapshot.snapshot_id,
    )
    contract_hash = stable_hash(contract_payload)

    hypothesis = "A bounded structured latent deep-factor model can improve F1's return/drawdown tradeoff on the same core universe without heavy dependencies."
    experiment_id = f"{project}__factor_elasticnet_core__f2_structured_latent_factor_v1__{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
    experiment = new_experiment(
        project=project,
        experiment_id=experiment_id,
        hypothesis=hypothesis,
        mode="f2_train",
        plan_steps=["core_pool_snapshot", "structured_feature_panel", "label_panel", "latent_model_fit", "candidate_scoring", "topn_backtest"],
        success_criteria=[
            "F2.1 must write structured features, latent factors, scores, rank, backtest metrics, and a train report.",
            "The experiment record must carry explicit factor, feature, label, model, and regime objects.",
        ],
        universe_snapshot=universe_snapshot,
        dataset_snapshot=dataset_snapshot,
        opportunity_spec=_opportunity_spec(model_cfg, hypothesis),
        subagent_tasks=[],
        factor_candidates=_build_factor_candidates(model_cfg),
        feature_view=_feature_view(model_cfg, str(cfg.get("freq", "1d"))),
        label_spec=_label_spec(model_cfg),
        model_candidate=_model_candidate(model_cfg),
        regime_spec=_regime_spec(),
        branch_id="factor_elasticnet_core",
        strategy_candidate_id="f2_structured_latent_factor_v1",
        core_universe_snapshot_id=core_snapshot.snapshot_id,
    )
    experiment_path = write_experiment_record(experiment, repo_root=repo_root)

    try:
        close, volume = load_close_volume_panel(
            db_path=Path(str(cfg["db_path"])),
            freq=str(cfg["freq"]),
            codes=list(core_snapshot.codes),
            start=cfg.get("start_date"),
            end=cfg.get("end_date"),
        )
        benchmark_code = str(cfg.get("baselines", {}).get("benchmark_code", "000001")).zfill(6)
        benchmark_close = (
            close[benchmark_code].dropna().astype(float)
            if benchmark_code in close.columns and not close[benchmark_code].dropna().empty
            else _load_benchmark_close(
                db_path=Path(str(cfg["db_path"])),
                freq=str(cfg["freq"]),
                benchmark_code=benchmark_code,
                start=cfg.get("start_date"),
                end=cfg.get("end_date"),
            )
        )

        feature_frame = _build_feature_frame(close=close, volume=volume, model_cfg=model_cfg)
        label_frame = _build_label_frame(
            close=close,
            benchmark_close=benchmark_close,
            horizon=model_cfg.label_horizon_days,
        )
        calendar = close.index.sort_values()
        rebalance_dates = _rebalance_dates(calendar, int(cfg.get("rebalance_every", model_cfg.label_horizon_days)))
        candidate_scores_df, latent_frame, train_runs = _train_and_score(
            feature_frame=feature_frame,
            label_frame=label_frame,
            calendar=calendar,
            rebalance_dates=rebalance_dates,
            model_cfg=model_cfg,
        )

        topk = int(cfg.get("topk", 6))
        topn_max = int(cfg.get("topn_max", topk))
        rank_df = candidate_scores_df.loc[
            candidate_scores_df["rank"] <= topk,
            ["date", "code", "score", "rank"],
        ].copy()
        if rank_df.empty:
            raise RuntimeError("F2 rank dataframe is empty after scoring.")

        feature_path = paths.features_dir / "f2_structured_feature_panel_v1.parquet"
        label_path = paths.features_dir / "f2_next5d_excess_label_v1.parquet"
        latent_path = paths.features_dir / "f2_latent_factor_frame_v1.parquet"
        candidate_scores_path = paths.signals_dir / "f2_structured_latent_scores.parquet"
        rank_path = paths.signals_dir / f"f2_structured_latent_rank_top{topk}.parquet"
        f2_artifacts_dir = paths.artifacts_dir / "f2"
        f2_artifacts_dir.mkdir(parents=True, exist_ok=True)
        metrics_path = f2_artifacts_dir / "summary_metrics.csv"
        plot_path = f2_artifacts_dir / "topn_suite.png"
        report_path = f2_artifacts_dir / "F2_TRAIN_REPORT.json"

        feature_frame.to_parquet(feature_path, index=False)
        label_frame.to_parquet(label_path, index=False)
        latent_frame.to_parquet(latent_path, index=False)
        candidate_scores_df.to_parquet(candidate_scores_path, index=False)
        rank_df.to_parquet(rank_path, index=False)

        rank_codes = sorted(rank_df["code"].astype(str).str.zfill(6).unique().tolist())
        backtest_close, _ = load_close_volume_panel(
            db_path=Path(str(cfg["db_path"])),
            freq=str(cfg["freq"]),
            codes=rank_codes,
            start=rank_df["date"].min().strftime("%Y-%m-%d"),
            end=cfg.get("end_date"),
        )
        bt_cfg = BacktestConfig(
            cash=float(cfg["cash"]),
            commission=float(cfg["commission"]),
            stamp_duty=float(cfg["stamp_duty"]),
            slippage=float(cfg["slippage"]),
            risk_free_rate=float(cfg["risk_free_rate"]),
            risk_overlay=cfg.get("risk_overlay", {}),
            min_commission=cfg.get("min_commission"),
        )
        curves, metrics_df = run_topn_suite(
            close_panel=backtest_close.reindex(columns=rank_codes).astype(float),
            rank_df=rank_df,
            cfg=bt_cfg,
            topn_max=topn_max,
        )
        metrics_df.to_csv(metrics_path, index=False, encoding="utf-8-sig")
        _save_curve_plot(curves, plot_path, title=f"{project}: F2 structured latent TopN suite")
        topk_metrics = _topn_metrics(metrics_df, topk=topk)

        report = {
            "project": project,
            "generated_at": _utc_now(),
            "experiment_id": experiment_id,
            "profile": model_cfg.profile,
            "core_snapshot_id": core_snapshot.snapshot_id,
            "train_cfg_hash": contract_hash,
            "train_cfg_payload": contract_payload,
            "feature_names": list(model_cfg.feature_names),
            "label_target": "next_5d_excess_return",
            "model_name": "f2_structured_latent_factor_v1",
            "model_family": "mlp_structured_latent_factor",
            "universe_size": len(core_snapshot.codes),
            "latent_dim": model_cfg.latent_dim,
            "hidden_sizes": list(model_cfg.hidden_sizes),
            "train_run_count": len(train_runs),
            "score_date_count": int(candidate_scores_df["date"].nunique()),
            "topk": topk,
            "topn_max": topn_max,
            "topk_metrics": topk_metrics,
            "train_runs": train_runs,
            "artifact_paths": {
                "feature_path": str(feature_path),
                "label_path": str(label_path),
                "latent_path": str(latent_path),
                "candidate_scores_path": str(candidate_scores_path),
                "rank_path": str(rank_path),
                "metrics_path": str(metrics_path),
                "plot_path": str(plot_path),
                "experiment_record_path": str(experiment_path),
            },
        }
        report_path.write_text(
            json.dumps(to_jsonable(report), ensure_ascii=False, indent=2).rstrip() + "\n",
            encoding="utf-8",
        )

        primary_blockers: list[str] = []
        if abs(float(topk_metrics.get("max_drawdown", 0.0) or 0.0)) > float(
            ((cfg.get("research_validation", {}) or {}).get("max_drawdown_limit", 0.30))
        ):
            primary_blockers.append(
                f"prototype_max_drawdown {float(topk_metrics['max_drawdown']):.2%} exceeds 30.00%"
            )
        evaluation = EvaluationRecord(
            status="prototype_deep_factor_result",
            summary="F2.1 structured latent prototype completed; formal promotion was not evaluated in this run.",
            classification="prototype_deep_factor_result",
            primary_blockers=primary_blockers,
            promotion_decision={"evaluated": False, "reason": "prototype_only"},
            next_experiment_themes=[
                "Compare F2.1 against control and F1 before widening the deep-factor search space.",
                "Keep the bounded challenger inside the current scikit-learn stack until the fair verifier finishes.",
            ],
            adversarial_robustness={"status": "not_evaluated", "score": None},
            regime_transition_drawdown=None,
        )
        execution = {
            "executed_steps": list(experiment.plan_steps),
            "outputs": {
                "core_pool_snapshot": {"path": str(paths.pools_dir / "latest_core_pool.json")},
                "structured_feature_panel": {"path": str(feature_path)},
                "label_panel": {"path": str(label_path)},
                "latent_model_fit": {
                    "train_run_count": len(train_runs),
                    "latent_path": str(latent_path),
                    "train_cfg_hash": contract_hash,
                },
                "candidate_scoring": {"path": str(candidate_scores_path)},
                "topn_backtest": {"metrics_path": str(metrics_path), "plot_path": str(plot_path)},
            },
        }
        experiment = update_experiment(
            experiment,
            status="evaluated",
            execution=execution,
            evaluation=evaluation,
            artifact_refs=[
                str(feature_path),
                str(label_path),
                str(latent_path),
                str(candidate_scores_path),
                str(rank_path),
                str(metrics_path),
                str(plot_path),
                str(report_path),
            ],
        )
        experiment_path = write_experiment_record(experiment, repo_root=repo_root)
        update_run_manifest(
            project,
            {
                "f2": {
                    "profile": model_cfg.profile,
                    "core_snapshot_id": core_snapshot.snapshot_id,
                    "feature_path": str(feature_path),
                    "label_path": str(label_path),
                    "latent_path": str(latent_path),
                    "candidate_scores_path": str(candidate_scores_path),
                    "rank_path": str(rank_path),
                    "summary_metrics_path": str(metrics_path),
                    "plot_path": str(plot_path),
                    "experiment_record_path": str(experiment_path),
                    "topk_metrics": topk_metrics,
                }
            },
        )
        _sync_success_memory(
            project=project,
            topk=topk,
            topk_metrics=topk_metrics,
            experiment_id=experiment_id,
            report_path=report_path,
            repo_root=repo_root,
        )
        return {
            "experiment_id": experiment_id,
            "experiment_record_path": str(experiment_path),
            "feature_path": str(feature_path),
            "label_path": str(label_path),
            "latent_path": str(latent_path),
            "candidate_scores_path": str(candidate_scores_path),
            "rank_path": str(rank_path),
            "summary_metrics_path": str(metrics_path),
            "plot_path": str(plot_path),
            "report_path": str(report_path),
            "train_run_count": len(train_runs),
            "score_date_count": int(candidate_scores_df["date"].nunique()),
            "topk_metrics": topk_metrics,
            "classification": "prototype_deep_factor_result",
        }
    except Exception as exc:
        evaluation = EvaluationRecord(
            status="failed",
            summary=f"F2.1 structured latent prototype failed: {exc}",
            classification="prototype_deep_factor_failure",
            primary_blockers=[str(exc)],
            promotion_decision={"evaluated": False, "reason": "prototype_failed"},
            next_experiment_themes=["Fix the F2 feature, latent, or training contract before rerunning the prototype."],
            adversarial_robustness={"status": "not_evaluated", "score": None},
            regime_transition_drawdown=None,
        )
        experiment = update_experiment(
            experiment,
            status="failed",
            execution={"executed_steps": ["core_pool_snapshot"]},
            evaluation=evaluation,
        )
        experiment_path = write_experiment_record(experiment, repo_root=repo_root)
        _sync_failure_memory(
            project=project,
            experiment_id=experiment_id,
            root_cause=str(exc),
            report_paths=[str(experiment_path)],
            repo_root=repo_root,
        )
        raise
