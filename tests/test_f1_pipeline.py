from __future__ import annotations

import json

import pandas as pd

from quant_mvp.experiment_graph import read_experiment_record
from quant_mvp.f1_pipeline import (
    FactorModelConfig,
    _build_label_frame,
    _monthly_retrain_dates,
    _train_and_score,
    run_f1_train,
)
from quant_mvp.factors import compute_factor_panel
from quant_mvp.pools import build_core_universe_snapshot


def test_adv20_and_amihud20_factor_panels() -> None:
    dates = pd.date_range("2020-01-01", periods=25, freq="B")
    close = pd.DataFrame(
        {
            "000001": [10.0 + idx for idx in range(len(dates))],
        },
        index=dates,
    )
    volume = pd.DataFrame(
        {
            "000001": [100.0 + idx for idx in range(len(dates))],
        },
        index=dates,
    )

    adv20 = compute_factor_panel("adv20", close=close, volume=volume)
    amihud20 = compute_factor_panel("amihud20", close=close, volume=volume)

    expected_adv = ((close["000001"] * volume["000001"]).iloc[5:25]).mean()
    ret1 = close["000001"].pct_change(fill_method=None)
    expected_amihud = (ret1.abs() / (close["000001"] * volume["000001"])).iloc[5:25].mean()

    assert round(float(adv20.iloc[-1, 0]), 10) == round(float(expected_adv), 10)
    assert round(float(amihud20.iloc[-1, 0]), 10) == round(float(expected_amihud), 10)


def test_label_uses_future_horizon_without_short_leakage() -> None:
    dates = pd.date_range("2020-01-01", periods=8, freq="B")
    close = pd.DataFrame(
        {
            "000001": [10.0, 10.5, 11.0, 10.0, 10.2, 10.8, 11.2, 11.5],
        },
        index=dates,
    )
    benchmark = pd.Series([100.0, 101.0, 101.5, 100.0, 100.5, 101.0, 102.0, 103.0], index=dates)

    label = _build_label_frame(close=close, benchmark_close=benchmark, horizon=2)
    row = label.loc[(label["date"] == dates[0]) & (label["code"] == "000001")].iloc[0]
    expected = (11.0 / 10.0 - 1.0) - (101.5 / 100.0 - 1.0)

    assert round(float(row["next_5d_excess_return"]), 10) == round(float(expected), 10)


def test_monthly_refit_schedule_trains_only_on_past_samples() -> None:
    calendar = pd.date_range("2020-01-01", periods=80, freq="B")
    model_cfg = FactorModelConfig(
        profile="test",
        feature_names=("mom20", "adv20"),
        label_horizon_days=5,
        refit_frequency="monthly",
        training_window_days=40,
        min_train_days=10,
        winsorize_quantile=0.01,
        standardization="cross_sectional_zscore",
        alpha=0.001,
        l1_ratio=0.2,
        max_iter=1000,
    )
    rows = []
    for dt in calendar:
        for idx, code in enumerate(["000001", "000002", "000003"], start=1):
            rows.append(
                {
                    "date": dt,
                    "code": code,
                    "mom20": float(idx),
                    "adv20": float(idx) * 2.0,
                },
            )
    feature_frame = pd.DataFrame(rows)
    label_frame = feature_frame.loc[:, ["date", "code"]].copy()
    label_frame["next_5d_excess_return"] = feature_frame["mom20"] * 0.1

    scores, train_runs = _train_and_score(
        feature_frame=feature_frame,
        label_frame=label_frame,
        calendar=calendar,
        rebalance_dates=list(calendar[::5]),
        model_cfg=model_cfg,
    )

    assert train_runs
    first_run = train_runs[0]
    assert pd.Timestamp(first_run["train_end_date"]) < pd.Timestamp(first_run["retrain_date"])
    assert not scores.empty
    assert list(_monthly_retrain_dates(calendar)[:2]) == [pd.Timestamp("2020-01-01"), pd.Timestamp("2020-02-03")]


def test_f1_train_command_writes_artifacts_and_experiment_record(limit_up_project) -> None:
    config_path = limit_up_project["config_path"]
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    payload["topk"] = 2
    payload["topn_max"] = 2
    payload["factor_model"] = {
        "profile": "f1_elasticnet_v1",
        "feature_names": ["mom20", "rev5", "vol20", "range", "vol_surge", "ma_gap", "adv20", "amihud20"],
        "label_horizon_days": 5,
        "refit_frequency": "monthly",
        "training_window_days": 60,
        "min_train_days": 40,
        "winsorize_quantile": 0.01,
        "standardization": "cross_sectional_zscore",
        "alpha": 0.001,
        "l1_ratio": 0.2,
        "max_iter": 1000,
    }
    config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    build_core_universe_snapshot(
        project=limit_up_project["project"],
        config_path=config_path,
        repo_root=limit_up_project["paths"].root,
    )
    command_payload = run_f1_train(
        limit_up_project["project"],
        config_path=config_path,
        repo_root=limit_up_project["paths"].root,
    )

    experiment = read_experiment_record(
        limit_up_project["project"],
        command_payload["experiment_id"],
    )
    rank_df = pd.read_parquet(command_payload["rank_path"])

    assert experiment.branch_id == "factor_elasticnet_core"
    assert experiment.strategy_candidate_id == "f1_elasticnet_v1"
    assert experiment.feature_view is not None
    assert experiment.feature_view.name == "technical_liquidity_panel_v1"
    assert experiment.label_spec is not None
    assert experiment.label_spec.target_name == "next_5d_excess_return"
    assert experiment.model_candidate is not None
    assert experiment.model_candidate.name == "f1_elasticnet_v1"
    assert experiment.model_candidate.update_frequency == "monthly"
    assert experiment.evaluation is not None
    assert experiment.evaluation.classification == "prototype_factor_model_result"
    assert experiment.evaluation.adversarial_robustness["status"] == "not_evaluated"
    assert set(rank_df.columns) == {"date", "code", "score", "rank"}
    assert rank_df["rank"].min() == 1
    assert command_payload["classification"] == "prototype_factor_model_result"
    assert limit_up_project["paths"].experiment_ledger_path.read_text(encoding="utf-8").find(command_payload["experiment_id"]) >= 0
