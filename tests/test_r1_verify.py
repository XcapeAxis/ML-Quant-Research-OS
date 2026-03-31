from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from quant_mvp.backtest_engine import BacktestConfig, run_topn_suite
from quant_mvp.experiment_graph import read_experiment_record
from quant_mvp.memory.writeback import load_machine_state
from quant_mvp.f1_pipeline import run_f1_train
from quant_mvp.pools import build_core_universe_snapshot
from quant_mvp.r1_pipeline import (
    RegimeControlConfig,
    _build_signal_frame,
    _build_state_timeline,
    run_r1_verify,
)


def _write_r1_config(
    config_path,
    *,
    factor_profile: str = "f1_elasticnet_v1",
    regime_profile: str = "r1_predictive_error_overlay_v1",
    caution_exposure: float = 0.5,
    defensive_exposure: float = 0.25,
) -> None:
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    payload["start_date"] = "2020-01-07"
    payload["topk"] = 3
    payload["topn_max"] = 3
    payload["stock_num"] = 3
    payload["factor_model"] = {
        "profile": factor_profile,
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
    payload["regime_control"] = {
        "profile": regime_profile,
        "ic_window_rebalances": 2,
        "shortfall_window_rebalances": 2,
        "min_history_rebalances": 2,
        "caution_ic_threshold": 0.10,
        "defensive_ic_threshold": -0.10,
        "caution_shortfall_threshold": 0.01,
        "defensive_shortfall_threshold": -0.01,
        "caution_exposure": caution_exposure,
        "defensive_exposure": defensive_exposure,
        "cooldown_rebalances": 2,
    }
    config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_run_topn_suite_exposure_scale_none_matches_default() -> None:
    dates = pd.date_range("2020-01-01", periods=6, freq="B")
    close_panel = pd.DataFrame(
        {
            "000001": [10.0, 10.1, 10.2, 10.1, 10.3, 10.4],
            "000002": [8.0, 8.1, 8.2, 8.3, 8.2, 8.4],
        },
        index=dates,
    )
    rank_df = pd.DataFrame(
        {
            "date": [dates[0], dates[0], dates[2], dates[2], dates[4], dates[4]],
            "code": ["000001", "000002", "000001", "000002", "000001", "000002"],
            "score": [2.0, 1.0, 2.1, 1.1, 2.2, 1.2],
            "rank": [1, 2, 1, 2, 1, 2],
        }
    )
    cfg = BacktestConfig(cash=1_000_000.0, commission=0.0001, stamp_duty=0.0005, slippage=0.001, risk_free_rate=0.03)

    curves_a, metrics_a = run_topn_suite(close_panel=close_panel, rank_df=rank_df, cfg=cfg, topn_max=2)
    curves_b, metrics_b = run_topn_suite(
        close_panel=close_panel,
        rank_df=rank_df,
        cfg=cfg,
        topn_max=2,
        exposure_scale_by_date=None,
    )

    pd.testing.assert_frame_equal(curves_a, curves_b)
    pd.testing.assert_frame_equal(metrics_a, metrics_b)


def test_r1_signal_frame_uses_lagged_realized_information_only() -> None:
    dates = pd.to_datetime(["2020-01-06", "2020-01-13", "2020-01-20"])
    candidate_scores = pd.DataFrame(
        {
            "date": [dates[0], dates[0], dates[1], dates[1], dates[2], dates[2]],
            "code": ["000001", "000002", "000001", "000002", "000001", "000002"],
            "score": [2.0, 1.0, 2.5, 0.5, 1.5, 0.3],
            "rank": [1, 2, 1, 2, 1, 2],
        }
    )
    label_frame = pd.DataFrame(
        {
            "date": [dates[0], dates[0], dates[1], dates[1], dates[2], dates[2]],
            "code": ["000001", "000002", "000001", "000002", "000001", "000002"],
            "next_5d_excess_return": [0.03, -0.02, -0.01, 0.01, 0.02, -0.03],
        }
    )
    f1_rank = candidate_scores.loc[candidate_scores["rank"] <= 2, ["date", "code", "score", "rank"]]
    regime_cfg = RegimeControlConfig(
        profile="r1",
        ic_window_rebalances=2,
        shortfall_window_rebalances=2,
        min_history_rebalances=2,
        caution_ic_threshold=0.0,
        defensive_ic_threshold=-0.03,
        caution_shortfall_threshold=-0.005,
        defensive_shortfall_threshold=-0.015,
        caution_exposure=0.5,
        defensive_exposure=0.25,
        cooldown_rebalances=2,
    )

    signal_frame = _build_signal_frame(
        candidate_scores=candidate_scores,
        label_frame=label_frame,
        f1_shared_rank=f1_rank,
        regime_cfg=regime_cfg,
        topk=2,
    )

    assert pd.isna(signal_frame.loc[0, "lagged_ic"])
    assert pd.isna(signal_frame.loc[0, "lagged_topk_excess_return"])
    assert signal_frame.loc[1, "lagged_topk_excess_return"] == pytest.approx(signal_frame.loc[0, "topk_excess_return"])


def test_r1_state_timeline_respects_cooldown_and_single_step_recovery() -> None:
    dates = pd.to_datetime(["2020-01-06", "2020-01-13", "2020-01-20", "2020-01-27", "2020-02-03"])
    signal_frame = pd.DataFrame(
        {
            "date": dates,
            "ic": [None, None, None, None, None],
            "lagged_ic": [None, -0.20, 0.10, 0.10, 0.10],
            "ewma_ic": [None, -0.20, 0.10, 0.10, 0.10],
            "topk_excess_return": [0.0, -0.02, 0.02, 0.02, 0.02],
            "lagged_topk_excess_return": [None, -0.02, 0.02, 0.02, 0.02],
            "ewma_topk_excess_return": [None, -0.02, 0.02, 0.02, 0.02],
            "lagged_history_count": [0, 2, 3, 4, 5],
        }
    )
    regime_cfg = RegimeControlConfig(
        profile="r1",
        ic_window_rebalances=2,
        shortfall_window_rebalances=2,
        min_history_rebalances=2,
        caution_ic_threshold=0.0,
        defensive_ic_threshold=-0.10,
        caution_shortfall_threshold=-0.005,
        defensive_shortfall_threshold=-0.015,
        caution_exposure=0.5,
        defensive_exposure=0.25,
        cooldown_rebalances=2,
    )

    timeline = _build_state_timeline(signal_frame, regime_cfg)

    assert list(timeline["state"]) == ["normal", "defensive", "defensive", "caution", "caution"]


def test_r1_verify_rejects_stale_f1_artifacts(limit_up_project) -> None:
    config_path = limit_up_project["config_path"]
    _write_r1_config(config_path)

    build_core_universe_snapshot(
        project=limit_up_project["project"],
        config_path=config_path,
        repo_root=limit_up_project["paths"].root,
    )
    run_f1_train(
        limit_up_project["project"],
        config_path=config_path,
        repo_root=limit_up_project["paths"].root,
    )

    _write_r1_config(config_path, factor_profile="f1_elasticnet_v1_stale")

    with pytest.raises(RuntimeError, match="rerun f1_train first"):
        run_r1_verify(
            limit_up_project["project"],
            config_path=config_path,
            repo_root=limit_up_project["paths"].root,
        )


def test_r1_verify_writes_artifacts_and_experiment_record(limit_up_project) -> None:
    config_path = limit_up_project["config_path"]
    _write_r1_config(config_path)

    build_core_universe_snapshot(
        project=limit_up_project["project"],
        config_path=config_path,
        repo_root=limit_up_project["paths"].root,
    )
    run_f1_train(
        limit_up_project["project"],
        config_path=config_path,
        repo_root=limit_up_project["paths"].root,
    )

    payload = run_r1_verify(
        limit_up_project["project"],
        config_path=config_path,
        repo_root=limit_up_project["paths"].root,
    )

    experiment = read_experiment_record(
        limit_up_project["project"],
        payload["experiment_id"],
        repo_root=limit_up_project["paths"].root,
    )
    report = json.loads(Path(payload["report_json_path"]).read_text(encoding="utf-8"))
    metrics = pd.read_csv(payload["metrics_path"])

    assert experiment.mode == "r1_verify"
    assert experiment.strategy_candidate_id == "r1_predictive_error_overlay_v1"
    assert experiment.regime_spec is not None
    assert experiment.regime_spec.detector_name == "r1_predictive_error_overlay_v1"
    assert experiment.evaluation is not None
    assert experiment.evaluation.classification in {"verifier_pass", "verifier_mixed", "verifier_fail"}
    assert report["compare_shell"] == "topn_suite_no_stoploss_v1"
    assert {"control", "f1", "f1_plus_r1", "delta_vs_f1"} == set(metrics["series"].tolist())
    assert limit_up_project["paths"].experiment_ledger_path.read_text(encoding="utf-8").find(payload["experiment_id"]) >= 0


def test_r1_verify_supports_v2_profile_and_updates_focus(limit_up_project) -> None:
    config_path = limit_up_project["config_path"]
    _write_r1_config(
        config_path,
        regime_profile="r1_predictive_error_overlay_v2",
        caution_exposure=0.75,
        defensive_exposure=0.5,
    )

    build_core_universe_snapshot(
        project=limit_up_project["project"],
        config_path=config_path,
        repo_root=limit_up_project["paths"].root,
    )
    run_f1_train(
        limit_up_project["project"],
        config_path=config_path,
        repo_root=limit_up_project["paths"].root,
    )

    payload = run_r1_verify(
        limit_up_project["project"],
        config_path=config_path,
        repo_root=limit_up_project["paths"].root,
    )

    experiment = read_experiment_record(
        limit_up_project["project"],
        payload["experiment_id"],
        repo_root=limit_up_project["paths"].root,
    )
    _, state = load_machine_state(limit_up_project["project"], repo_root=limit_up_project["paths"].root)

    assert experiment.strategy_candidate_id == "r1_predictive_error_overlay_v2"
    assert experiment.regime_spec is not None
    assert experiment.regime_spec.detector_name == "r1_predictive_error_overlay_v2"
    assert "r1_predictive_error_overlay_v2" in payload["report_json_path"]
    assert state["next_build_target"] == "f2_structured_latent_factor_v1"
    assert "f2_structured_latent_factor_v1" in state["current_strategy_focus"]
