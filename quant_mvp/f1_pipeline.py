from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.linear_model import ElasticNet

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
from .factors import compute_factor_panel
from .manifest import update_run_manifest
from .memory.ledger import stable_hash, to_jsonable
from .memory.writeback import (
    generate_handoff,
    load_machine_state,
    record_experiment_result,
    record_failure,
    sync_project_state,
    sync_research_memory,
    update_hypothesis_queue,
)
from .pools import load_latest_core_pool_snapshot
from .project import resolve_project_paths


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class FactorModelConfig:
    profile: str
    feature_names: tuple[str, ...]
    label_horizon_days: int
    refit_frequency: str
    training_window_days: int
    min_train_days: int
    winsorize_quantile: float
    standardization: str
    alpha: float
    l1_ratio: float
    max_iter: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "feature_names": list(self.feature_names),
            "label_horizon_days": self.label_horizon_days,
            "refit_frequency": self.refit_frequency,
            "training_window_days": self.training_window_days,
            "min_train_days": self.min_train_days,
            "winsorize_quantile": self.winsorize_quantile,
            "standardization": self.standardization,
            "alpha": self.alpha,
            "l1_ratio": self.l1_ratio,
            "max_iter": self.max_iter,
        }


def _factor_model_config(cfg: dict[str, Any]) -> FactorModelConfig:
    raw = dict(cfg.get("factor_model", {}) or {})
    return FactorModelConfig(
        profile=str(raw.get("profile", "f1_elasticnet_v1")),
        feature_names=tuple(str(item).strip() for item in raw.get("feature_names", []) if str(item).strip()),
        label_horizon_days=int(raw.get("label_horizon_days", 5)),
        refit_frequency=str(raw.get("refit_frequency", "monthly")),
        training_window_days=int(raw.get("training_window_days", 756)),
        min_train_days=int(raw.get("min_train_days", 504)),
        winsorize_quantile=float(raw.get("winsorize_quantile", 0.01)),
        standardization=str(raw.get("standardization", "cross_sectional_zscore")),
        alpha=float(raw.get("alpha", 0.001)),
        l1_ratio=float(raw.get("l1_ratio", 0.2)),
        max_iter=int(raw.get("max_iter", 5000)),
    )


def _stack_panel(panel: pd.DataFrame, value_name: str) -> pd.Series:
    try:
        stacked = panel.stack(future_stack=True)
    except (TypeError, ValueError):
        stacked = panel.stack(dropna=False)
    stacked.name = value_name
    return stacked


def _cross_sectional_preprocess(panel: pd.DataFrame, *, winsorize_quantile: float) -> pd.DataFrame:
    lower = panel.quantile(winsorize_quantile, axis=1)
    upper = panel.quantile(1.0 - winsorize_quantile, axis=1)
    clipped = panel.clip(lower=lower, upper=upper, axis=0)
    mean = clipped.mean(axis=1)
    std = clipped.std(axis=1, ddof=0).replace(0.0, pd.NA)
    return clipped.sub(mean, axis=0).div(std, axis=0).astype(float)


def _rebalance_dates(calendar: pd.DatetimeIndex, every: int) -> list[pd.Timestamp]:
    if every <= 0:
        raise ValueError("rebalance_every must be positive")
    return [pd.Timestamp(item) for item in calendar[::every]]


def _monthly_retrain_dates(calendar: pd.DatetimeIndex) -> list[pd.Timestamp]:
    grouped = pd.Series(calendar, index=calendar).groupby([calendar.year, calendar.month]).head(1)
    return [pd.Timestamp(item) for item in grouped.tolist()]


def _topn_metrics(metrics_df: pd.DataFrame, *, topk: int) -> dict[str, Any]:
    if metrics_df.empty:
        return {}
    row = metrics_df.loc[metrics_df["topn"].astype(int) == int(topk)]
    if row.empty:
        return {}
    return {str(key): value for key, value in row.iloc[0].to_dict().items()}


def _save_curve_plot(curves: pd.DataFrame, out_path: Path, title: str) -> None:
    norm = curves / curves.iloc[0]
    plt.figure(figsize=(12, 6))
    for col in norm.columns:
        plt.plot(norm.index, norm[col], label=col)
    plt.title(title)
    plt.xlabel("Date")
    plt.ylabel("Equity (normalized)")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=200)
    plt.close()


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        output.append(text)
    return output


def _build_factor_candidates(model_cfg: FactorModelConfig) -> list[FactorCandidate]:
    family_map = {
        "mom20": "technical_momentum",
        "rev5": "technical_reversal",
        "vol20": "risk_volatility",
        "range": "risk_range",
        "vol_surge": "liquidity_activity",
        "ma_gap": "technical_trend",
        "adv20": "liquidity_turnover",
        "amihud20": "liquidity_impact",
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
    }
    candidates: list[FactorCandidate] = []
    for name in model_cfg.feature_names:
        payload = {"profile": model_cfg.profile, "feature": name}
        candidates.append(
            FactorCandidate(
                factor_id=f"factor-{stable_hash(payload)[:12]}",
                name=name,
                family=family_map.get(name, "factor"),
                description=description_map.get(name, "Explicit factor feature."),
                params={"profile": model_cfg.profile},
                source="f1_factor_model",
                status="prototype",
                tags=["stage_f1", "factor_model", model_cfg.profile],
            ),
        )
    return candidates


def _feature_view(model_cfg: FactorModelConfig, freq: str) -> FeatureView:
    payload = {
        "profile": model_cfg.profile,
        "feature_names": list(model_cfg.feature_names),
        "freq": freq,
    }
    return FeatureView(
        feature_view_id=f"feature-view-{stable_hash(payload)[:12]}",
        name="technical_liquidity_panel_v1",
        inputs=["daily_ohlcv", "core_pool_membership"],
        transforms=["cross_sectional_winsorize_0.01", "cross_sectional_zscore"],
        sampling=f"{freq} cross_sectional_panel",
        notes="F1 explicit technical + liquidity factor panel for the first ElasticNet MVP.",
    )


def _label_spec(model_cfg: FactorModelConfig) -> LabelSpec:
    payload = {"profile": model_cfg.profile, "target": "next_5d_excess_return", "horizon": model_cfg.label_horizon_days}
    return LabelSpec(
        label_spec_id=f"label-{stable_hash(payload)[:12]}",
        target_name="next_5d_excess_return",
        horizon=str(model_cfg.label_horizon_days),
        objective="cross_sectional_ranking",
        definition="Future 5-day stock return minus the configured benchmark's future 5-day return.",
        notes="F1 keeps the excess-return label explicit so later F2/R1 models share one contract.",
    )


def _model_candidate(model_cfg: FactorModelConfig) -> ModelCandidate:
    return ModelCandidate(
        model_id=f"model-{stable_hash(model_cfg.to_dict())[:12]}",
        name="f1_elasticnet_v1",
        family="elasticnet_cross_sectional",
        params={
            "alpha": model_cfg.alpha,
            "l1_ratio": model_cfg.l1_ratio,
            "max_iter": model_cfg.max_iter,
        },
        is_online_adaptive=False,
        update_frequency="monthly",
        training_mode="batch",
        notes="First controllable factor-model MVP; no online adaptation, no hyperparameter search.",
    )


def _regime_spec() -> RegimeSpec:
    return RegimeSpec(
        regime_id=f"regime-{stable_hash({'detector_name': 'static_baseline'})[:12]}",
        detector_name="static_baseline",
        transition_signal="not_enabled",
        regime_transition_latency=None,
        adaptive_policy="static",
        notes="R1 will later replace this with predictive-error and TTA-driven adaptation.",
    )


def _opportunity_spec(model_cfg: FactorModelConfig, hypothesis: str) -> OpportunitySpec:
    return OpportunitySpec(
        strategy_mode="factor_model",
        hypothesis=hypothesis,
        params={
            "profile": model_cfg.profile,
            "feature_names": list(model_cfg.feature_names),
            "label_horizon_days": model_cfg.label_horizon_days,
        },
    )


def _load_benchmark_close(
    *,
    db_path: Path,
    freq: str,
    benchmark_code: str,
    start: str | None,
    end: str | None,
) -> pd.Series:
    benchmark_close, _ = load_close_volume_panel(
        db_path=db_path,
        freq=freq,
        codes=[benchmark_code],
        start=start,
        end=end,
    )
    series = benchmark_close.get(str(benchmark_code).zfill(6))
    if series is None or series.dropna().empty:
        raise RuntimeError(f"Benchmark close series is unavailable for {benchmark_code}.")
    return series.dropna().astype(float)


def _build_feature_frame(
    *,
    close: pd.DataFrame,
    volume: pd.DataFrame,
    model_cfg: FactorModelConfig,
) -> pd.DataFrame:
    processed: dict[str, pd.DataFrame] = {}
    for name in model_cfg.feature_names:
        panel = compute_factor_panel(name, close=close, volume=volume)
        processed[name] = _cross_sectional_preprocess(panel, winsorize_quantile=model_cfg.winsorize_quantile)
    feature_frame = pd.concat([_stack_panel(panel, name) for name, panel in processed.items()], axis=1).reset_index()
    feature_frame.columns = ["date", "code", *model_cfg.feature_names]
    feature_frame["date"] = pd.to_datetime(feature_frame["date"])
    feature_frame["code"] = feature_frame["code"].astype(str).str.zfill(6)
    feature_frame = feature_frame.dropna(subset=list(model_cfg.feature_names), how="all").sort_values(["date", "code"])
    return feature_frame.reset_index(drop=True)


def _build_label_frame(
    *,
    close: pd.DataFrame,
    benchmark_close: pd.Series,
    horizon: int,
) -> pd.DataFrame:
    stock_forward = close.shift(-horizon).div(close) - 1.0
    benchmark_forward = benchmark_close.shift(-horizon).div(benchmark_close) - 1.0
    label_panel = stock_forward.sub(benchmark_forward, axis=0)
    label_frame = _stack_panel(label_panel, "next_5d_excess_return").reset_index()
    label_frame.columns = ["date", "code", "next_5d_excess_return"]
    label_frame["date"] = pd.to_datetime(label_frame["date"])
    label_frame["code"] = label_frame["code"].astype(str).str.zfill(6)
    return label_frame.sort_values(["date", "code"]).reset_index(drop=True)


def _train_and_score(
    *,
    feature_frame: pd.DataFrame,
    label_frame: pd.DataFrame,
    calendar: pd.DatetimeIndex,
    rebalance_dates: list[pd.Timestamp],
    model_cfg: FactorModelConfig,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    joined = feature_frame.merge(label_frame, on=["date", "code"], how="left")
    date_positions = {pd.Timestamp(item): idx for idx, item in enumerate(calendar)}
    joined["date_pos"] = joined["date"].map(date_positions)
    joined = joined.dropna(subset=["date_pos"]).copy()
    joined["date_pos"] = joined["date_pos"].astype(int)

    retrain_dates = _monthly_retrain_dates(calendar)
    all_scores: list[pd.DataFrame] = []
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

        model = ElasticNet(
            alpha=model_cfg.alpha,
            l1_ratio=model_cfg.l1_ratio,
            max_iter=model_cfg.max_iter,
            fit_intercept=True,
        )
        model.fit(train_df.loc[:, list(model_cfg.feature_names)], train_df["next_5d_excess_return"])

        score_df = feature_frame.loc[feature_frame["date"].isin(score_dates)].dropna(subset=list(model_cfg.feature_names)).copy()
        if score_df.empty:
            continue
        score_df["score"] = model.predict(score_df.loc[:, list(model_cfg.feature_names)])
        score_df["retrain_date"] = pd.Timestamp(retrain_date)
        all_scores.append(score_df.loc[:, ["date", "code", "score", "retrain_date"]])
        train_runs.append(
            {
                "retrain_date": pd.Timestamp(retrain_date).strftime("%Y-%m-%d"),
                "train_start_date": calendar[train_start_pos].strftime("%Y-%m-%d"),
                "train_end_date": calendar[train_end_exclusive - 1].strftime("%Y-%m-%d"),
                "train_row_count": int(len(train_df)),
                "score_date_count": int(len(score_dates)),
            },
        )

    if not all_scores:
        raise RuntimeError("F1 produced no scored rebalance dates; check training window, label horizon, or feature coverage.")

    candidate_scores = pd.concat(all_scores, ignore_index=True).sort_values(["date", "score", "code"], ascending=[True, False, True])
    candidate_scores["date"] = pd.to_datetime(candidate_scores["date"])
    candidate_scores["code"] = candidate_scores["code"].astype(str).str.zfill(6)
    candidate_scores["rank"] = candidate_scores.groupby("date").cumcount() + 1
    return candidate_scores.reset_index(drop=True), train_runs


def _refresh_memory_after_success(
    *,
    project: str,
    topk_metrics: dict[str, Any],
    topk: int,
    experiment_id: str,
    report_path: Path,
    repo_root: Path | None = None,
) -> None:
    _, state = load_machine_state(project, repo_root=repo_root)
    max_drawdown = float(topk_metrics.get("max_drawdown", 0.0) or 0.0)
    drawdown_magnitude = abs(max_drawdown)
    drawdown_limit = 0.30
    blocker = (
        f"F1 prototype top{topk} max_drawdown {max_drawdown:.2%} remains above {drawdown_limit:.2%}."
        if drawdown_magnitude > drawdown_limit
        else "none"
    )
    sync_project_state(
        project,
        {
            "current_phase": "F1 factor model MVP",
            "current_task": "Run and inspect the first ElasticNet cross-sectional factor model prototype.",
            "current_blocker": blocker,
            "current_capability_boundary": "F1 now runs end-to-end on the latest core pool, but it is still a prototype factor-model result rather than a promotion-grade strategy claim.",
            "next_priority_action": "Compare F1 topk metrics against the control branch, then decide whether to run one bounded verifier or reopen LIGHT scouting for F2/R1.",
            "last_verified_capability": "F1 ElasticNet prototype ran end-to-end on the latest core pool and wrote formal experiment artifacts.",
            "last_failed_capability": "none" if blocker == "none" else blocker,
        },
        repo_root=repo_root,
    )
    durable_facts = _dedupe(
        list(state.get("durable_facts", []) or [])
        + [
            "F1 ElasticNet prototype now runs only on the latest core pool snapshot and does not fall back to legacy universe files.",
            "F1 uses eight technical and liquidity features plus a next_5d_excess_return label.",
            "F1 remains a prototype result and is not wired into promote_candidate yet.",
        ],
    )
    negative_memory = _dedupe(
        list(state.get("negative_memory", []) or [])
        + [
            "Do not mix F1 prototype metrics into baseline_limit_up or other legacy control branches.",
            "Do not treat F1 prototype metrics as profitability proof or promotion evidence.",
            "Do not reopen F2/R1 scouting before F1 is reproducible and interpretable.",
        ],
    )
    next_step_memory = _dedupe(
        [
            "Review the F1 prototype report and decide whether one bounded verifier is justified.",
            "If F1 is reproducible, rerun Subagent Gate before opening F2/R1 frontier scouting.",
            *list(state.get("next_step_memory", []) or []),
        ],
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
                "hypothesis": "Regularized ElasticNet on technical + liquidity features can produce a reproducible 5-day excess-return rank on the core mainboard universe.",
            },
            {
                "status": "pending",
                "hypothesis": "Only after the F1 prototype is reproducible should the system reopen F2 deep-factor and R1 regime-control scouting.",
            },
            {
                "status": "pending",
                "hypothesis": "A bounded verifier should compare F1 against the control branch before any broader search is reopened.",
            },
        ],
        repo_root=repo_root,
    )
    record_experiment_result(
        project,
        {
            "timestamp": _utc_now(),
            "experiment_id": experiment_id,
            "hypothesis": "Regularized ElasticNet technical+liquidity factor prototype",
            "config_hash": stable_hash({"topk": topk, "report_path": str(report_path)}),
            "result": "prototype_factor_model_result",
            "blockers": [] if blocker == "none" else [blocker],
            "artifact_refs": [str(report_path)],
        },
        repo_root=repo_root,
    )
    generate_handoff(project, repo_root=repo_root)


def _refresh_memory_after_failure(
    *,
    project: str,
    experiment_id: str,
    root_cause: str,
    report_paths: list[str],
    repo_root: Path | None = None,
) -> None:
    sync_project_state(
        project,
        {
            "current_phase": "F1 factor model MVP",
            "current_task": "Repair the F1 factor-model contract before reopening deeper model work.",
            "current_blocker": root_cause,
            "current_capability_boundary": "F1 is not yet reproducible enough to support F2 or R1 expansion.",
            "next_priority_action": "Fix the F1 feature/label/training contract and rerun the prototype before reopening frontier research.",
            "last_verified_capability": "none",
            "last_failed_capability": root_cause,
        },
        repo_root=repo_root,
    )
    update_hypothesis_queue(
        project,
        [
            {
                "status": "blocked",
                "hypothesis": "Regularized ElasticNet on technical + liquidity features can produce a reproducible 5-day excess-return rank on the core mainboard universe.",
            },
            {
                "status": "pending",
                "hypothesis": "F2 and R1 scouting must wait until the F1 factor-model contract is fixed.",
            },
        ],
        repo_root=repo_root,
    )
    record_failure(
        project,
        {
            "timestamp": _utc_now(),
            "experiment_id": experiment_id,
            "summary": "F1 ElasticNet prototype failed.",
            "root_cause": root_cause,
            "corrective_action": "Fix the feature/label/training contract before rerunning the prototype.",
            "resolution_status": "not_fixed",
        },
        repo_root=repo_root,
        append_ledger=True,
        ledger_entry={
            "timestamp": _utc_now(),
            "experiment_id": experiment_id,
            "hypothesis": "Regularized ElasticNet technical+liquidity factor prototype",
            "result": "failed",
            "blockers": [root_cause],
            "artifact_refs": report_paths,
        },
    )
    generate_handoff(project, repo_root=repo_root)


def run_f1_train(project: str, *, config_path: Path | None = None, repo_root: Path | None = None) -> dict[str, Any]:
    cfg, paths = load_config(project, config_path=config_path)
    if repo_root is not None:
        paths = resolve_project_paths(project, root=repo_root)
    paths.ensure_dirs()
    model_cfg = _factor_model_config(cfg)
    if not model_cfg.feature_names:
        raise ValueError("factor_model.feature_names cannot be empty")

    core_snapshot = load_latest_core_pool_snapshot(
        project,
        repo_root=repo_root,
        build_if_missing=False,
        config_path=config_path,
    )
    if core_snapshot is None or not core_snapshot.codes:
        raise RuntimeError("F1 requires an existing core universe snapshot; it will not fall back to legacy universe_codes.txt.")

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

    hypothesis = "Technical and liquidity factors can produce a reproducible 5-day excess-return rank on the core mainboard universe."
    experiment_id = f"{project}__factor_elasticnet_core__{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
    experiment = new_experiment(
        project=project,
        experiment_id=experiment_id,
        hypothesis=hypothesis,
        mode="f1_train",
        plan_steps=["core_pool_snapshot", "feature_panel", "label_panel", "elasticnet_fit", "candidate_scoring", "topn_backtest"],
        success_criteria=[
            "The F1 command must write factor features, labels, scores, rank, backtest metrics, and a report.",
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
        strategy_candidate_id="f1_elasticnet_v1",
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
        label_frame = _build_label_frame(close=close, benchmark_close=benchmark_close, horizon=model_cfg.label_horizon_days)
        calendar = close.index.sort_values()
        rebalance_dates = _rebalance_dates(calendar, int(cfg.get("rebalance_every", model_cfg.label_horizon_days)))
        candidate_scores_df, train_runs = _train_and_score(
            feature_frame=feature_frame,
            label_frame=label_frame,
            calendar=calendar,
            rebalance_dates=rebalance_dates,
            model_cfg=model_cfg,
        )

        topk = int(cfg.get("topk", 6))
        topn_max = int(cfg.get("topn_max", topk))
        rank_df = candidate_scores_df.loc[candidate_scores_df["rank"] <= topk, ["date", "code", "score", "rank"]].copy()
        if rank_df.empty:
            raise RuntimeError("F1 rank dataframe is empty after scoring.")

        feature_path = paths.features_dir / "f1_technical_liquidity_panel_v1.parquet"
        label_path = paths.features_dir / "f1_next5d_excess_label_v1.parquet"
        candidate_scores_path = paths.signals_dir / "f1_elasticnet_candidate_scores.parquet"
        rank_path = paths.signals_dir / f"f1_elasticnet_rank_top{topk}.parquet"
        f1_artifacts_dir = paths.artifacts_dir / "f1"
        f1_artifacts_dir.mkdir(parents=True, exist_ok=True)
        metrics_path = f1_artifacts_dir / "summary_metrics.csv"
        plot_path = f1_artifacts_dir / "topn_suite.png"
        report_path = f1_artifacts_dir / "f1_train_report.json"

        feature_frame.to_parquet(feature_path, index=False)
        label_frame.to_parquet(label_path, index=False)
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
        )
        curves, metrics_df = run_topn_suite(
            close_panel=backtest_close.reindex(columns=rank_codes).astype(float),
            rank_df=rank_df,
            cfg=bt_cfg,
            topn_max=topn_max,
        )
        metrics_df.to_csv(metrics_path, index=False, encoding="utf-8-sig")
        _save_curve_plot(curves, plot_path, title=f"{project}: F1 ElasticNet TopN suite")
        topk_metrics = _topn_metrics(metrics_df, topk=topk)

        report = {
            "project": project,
            "generated_at": _utc_now(),
            "profile": model_cfg.profile,
            "core_snapshot_id": core_snapshot.snapshot_id,
            "feature_names": list(model_cfg.feature_names),
            "label_target": "next_5d_excess_return",
            "model_name": "f1_elasticnet_v1",
            "model_family": "elasticnet_cross_sectional",
            "universe_size": len(core_snapshot.codes),
            "train_run_count": len(train_runs),
            "score_date_count": int(candidate_scores_df["date"].nunique()),
            "topk": topk,
            "topn_max": topn_max,
            "topk_metrics": topk_metrics,
            "train_runs": train_runs,
            "artifact_paths": {
                "feature_path": str(feature_path),
                "label_path": str(label_path),
                "candidate_scores_path": str(candidate_scores_path),
                "rank_path": str(rank_path),
                "metrics_path": str(metrics_path),
                "plot_path": str(plot_path),
                "experiment_record_path": str(experiment_path),
            },
        }
        report_path.write_text(json.dumps(to_jsonable(report), ensure_ascii=False, indent=2).rstrip() + "\n", encoding="utf-8")

        max_drawdown_limit = float(((cfg.get("research_validation", {}) or {}).get("max_drawdown_limit", 0.30)))
        primary_blockers: list[str] = []
        if topk_metrics and abs(float(topk_metrics.get("max_drawdown", 0.0) or 0.0)) > max_drawdown_limit:
            primary_blockers.append(
                f"prototype_max_drawdown {float(topk_metrics['max_drawdown']):.2%} exceeds {max_drawdown_limit:.2%}"
            )

        evaluation = EvaluationRecord(
            status="prototype_factor_model_result",
            summary="F1 ElasticNet prototype completed; formal promotion was not evaluated in this run.",
            classification="prototype_factor_model_result",
            primary_blockers=primary_blockers,
            promotion_decision={"evaluated": False, "reason": "prototype_only"},
            next_experiment_themes=[
                "Compare the F1 prototype against the control branch before opening a broader search.",
                "If the prototype is reproducible, rerun Subagent Gate before F2/R1 scouting.",
            ],
            adversarial_robustness={"status": "not_evaluated", "score": None},
            regime_transition_drawdown=None,
        )
        execution = {
            "executed_steps": list(experiment.plan_steps),
            "outputs": {
                "core_pool_snapshot": {"path": str(paths.pools_dir / "latest_core_pool.json")},
                "feature_panel": {"path": str(feature_path)},
                "label_panel": {"path": str(label_path)},
                "elasticnet_fit": {"train_run_count": len(train_runs)},
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
                "f1": {
                    "profile": model_cfg.profile,
                    "core_snapshot_id": core_snapshot.snapshot_id,
                    "feature_path": str(feature_path),
                    "label_path": str(label_path),
                    "candidate_scores_path": str(candidate_scores_path),
                    "rank_path": str(rank_path),
                    "summary_metrics_path": str(metrics_path),
                    "plot_path": str(plot_path),
                    "experiment_record_path": str(experiment_path),
                    "topk_metrics": topk_metrics,
                },
            },
        )
        _refresh_memory_after_success(
            project=project,
            topk_metrics=topk_metrics,
            topk=topk,
            experiment_id=experiment_id,
            report_path=report_path,
            repo_root=repo_root,
        )
        return {
            "experiment_id": experiment_id,
            "experiment_record_path": str(experiment_path),
            "feature_path": str(feature_path),
            "label_path": str(label_path),
            "candidate_scores_path": str(candidate_scores_path),
            "rank_path": str(rank_path),
            "summary_metrics_path": str(metrics_path),
            "plot_path": str(plot_path),
            "report_path": str(report_path),
            "train_run_count": len(train_runs),
            "score_date_count": int(candidate_scores_df["date"].nunique()),
            "topk_metrics": topk_metrics,
            "classification": "prototype_factor_model_result",
        }
    except Exception as exc:
        evaluation = EvaluationRecord(
            status="failed",
            summary=f"F1 ElasticNet prototype failed: {exc}",
            classification="prototype_factor_model_failure",
            primary_blockers=[str(exc)],
            promotion_decision={"evaluated": False, "reason": "prototype_failed"},
            next_experiment_themes=["Fix the F1 feature, label, or training contract before rerunning the prototype."],
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
        _refresh_memory_after_failure(
            project=project,
            experiment_id=experiment_id,
            root_cause=str(exc),
            report_paths=[str(experiment_path)],
            repo_root=repo_root,
        )
        raise
