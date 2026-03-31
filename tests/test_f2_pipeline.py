from __future__ import annotations

import json
import warnings

import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning
from sklearn.neural_network import MLPRegressor

from quant_mvp.experiment_graph import read_experiment_record
from quant_mvp.f2_pipeline import (
    _build_group_features,
    _latent_from_model,
    run_f2_train,
)
from quant_mvp.pools import build_core_universe_snapshot


def _write_f2_config(config_path) -> None:
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    payload["start_date"] = "2020-01-07"
    payload["topk"] = 3
    payload["topn_max"] = 3
    payload["stock_num"] = 3
    payload["deep_factor_model"] = {
        "profile": "f2_structured_latent_factor_v1",
        "base_feature_names": ["mom20", "rev5", "vol20", "range", "vol_surge", "ma_gap", "adv20", "amihud20"],
        "group_features": True,
        "latent_dim": 4,
        "hidden_sizes": [12, 4],
        "activation": "relu",
        "alpha": 0.0001,
        "learning_rate_init": 0.001,
        "max_iter": 300,
        "early_stopping": True,
        "validation_fraction": 0.1,
        "random_state": 42,
        "label_horizon_days": 5,
        "refit_frequency": "monthly",
        "training_window_days": 60,
        "min_train_days": 40,
        "winsorize_quantile": 0.01,
        "standardization": "cross_sectional_zscore",
    }
    config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_group_feature_blocks_are_means() -> None:
    frame = pd.DataFrame(
        {
            "mom20": [1.0, 2.0],
            "rev5": [3.0, 4.0],
            "ma_gap": [5.0, 6.0],
            "vol20": [7.0, 8.0],
            "range": [9.0, 10.0],
            "vol_surge": [11.0, 12.0],
            "adv20": [13.0, 14.0],
            "amihud20": [15.0, 16.0],
        }
    )

    grouped = _build_group_features(frame)

    assert grouped["momentum_block"].tolist() == [3.0, 4.0]
    assert grouped["risk_block"].tolist() == [8.0, 9.0]
    assert grouped["liquidity_block"].tolist() == [13.0, 14.0]


def test_latent_bottleneck_output_shape_and_prediction_contract() -> None:
    rng = np.random.default_rng(42)
    features = pd.DataFrame(rng.normal(size=(30, 11)))
    labels = pd.Series(rng.normal(size=30))
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=ConvergenceWarning)
        model = MLPRegressor(
            hidden_layer_sizes=(12, 4),
            activation="relu",
            solver="adam",
            alpha=0.0001,
            learning_rate_init=0.001,
            max_iter=300,
            early_stopping=False,
            random_state=42,
        )
        model.fit(features, labels)

    latent, scores = _latent_from_model(model, features)

    assert latent.shape == (30, 4)
    assert scores.shape == (30,)
    np.testing.assert_allclose(scores, model.predict(features), rtol=1e-6, atol=1e-6)


def test_f2_train_command_writes_artifacts_and_experiment_record(limit_up_project) -> None:
    config_path = limit_up_project["config_path"]
    _write_f2_config(config_path)

    build_core_universe_snapshot(
        project=limit_up_project["project"],
        config_path=config_path,
        repo_root=limit_up_project["paths"].root,
    )
    command_payload = run_f2_train(
        limit_up_project["project"],
        config_path=config_path,
        repo_root=limit_up_project["paths"].root,
    )

    experiment = read_experiment_record(
        limit_up_project["project"],
        command_payload["experiment_id"],
        repo_root=limit_up_project["paths"].root,
    )
    rank_df = pd.read_parquet(command_payload["rank_path"])
    latent_df = pd.read_parquet(command_payload["latent_path"])

    assert experiment.branch_id == "factor_elasticnet_core"
    assert experiment.strategy_candidate_id == "f2_structured_latent_factor_v1"
    assert experiment.feature_view is not None
    assert experiment.feature_view.name == "technical_liquidity_panel_v2_structured"
    assert experiment.model_candidate is not None
    assert experiment.model_candidate.name == "f2_structured_latent_factor_v1"
    assert experiment.model_candidate.family == "mlp_structured_latent_factor"
    assert experiment.model_candidate.update_frequency == "monthly"
    assert experiment.evaluation is not None
    assert experiment.evaluation.classification == "prototype_deep_factor_result"
    assert set(rank_df.columns) == {"date", "code", "score", "rank"}
    assert {"date", "code", "retrain_date", "latent_1", "latent_2", "latent_3", "latent_4"} <= set(latent_df.columns)
    assert command_payload["classification"] == "prototype_deep_factor_result"
    assert limit_up_project["paths"].experiment_ledger_path.read_text(encoding="utf-8").find(command_payload["experiment_id"]) >= 0
