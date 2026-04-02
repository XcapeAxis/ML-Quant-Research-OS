from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from quant_mvp.experiment_graph import read_experiment_record
from quant_mvp.f1_pipeline import run_f1_train
from quant_mvp.f2_pipeline import run_f2_train
from quant_mvp.f2_verify import _decision_from_metrics, run_f2_verify
from quant_mvp.pools import build_core_universe_snapshot


def _write_factor_and_deep_config(
    config_path,
    *,
    deep_profile: str = "f2_structured_latent_factor_v1",
    deep_training_window_days: int = 60,
) -> None:
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    payload["start_date"] = "2020-01-07"
    payload["topk"] = 3
    payload["topn_max"] = 3
    payload["stock_num"] = 3
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
    payload["deep_factor_model"] = {
        "profile": deep_profile,
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
        "training_window_days": deep_training_window_days,
        "min_train_days": 40,
        "winsorize_quantile": 0.01,
        "standardization": "cross_sectional_zscore",
    }
    config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_f2_verify_rejects_stale_f2_artifacts(limit_up_project) -> None:
    config_path = limit_up_project["config_path"]
    _write_factor_and_deep_config(config_path)

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
    run_f2_train(
        limit_up_project["project"],
        config_path=config_path,
        repo_root=limit_up_project["paths"].root,
    )

    _write_factor_and_deep_config(config_path, deep_profile="f2_structured_latent_factor_v1_stale")

    with pytest.raises(RuntimeError, match="rerun f2_train first"):
        run_f2_verify(
            limit_up_project["project"],
            config_path=config_path,
            repo_root=limit_up_project["paths"].root,
        )


def test_f2_verify_rejects_when_training_contract_changes(limit_up_project) -> None:
    config_path = limit_up_project["config_path"]
    _write_factor_and_deep_config(config_path, deep_training_window_days=60)

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
    run_f2_train(
        limit_up_project["project"],
        config_path=config_path,
        repo_root=limit_up_project["paths"].root,
    )

    _write_factor_and_deep_config(config_path, deep_training_window_days=80)

    with pytest.raises(RuntimeError, match="rerun f2_train first"):
        run_f2_verify(
            limit_up_project["project"],
            config_path=config_path,
            repo_root=limit_up_project["paths"].root,
        )


def test_f2_verify_rejects_when_latest_f2_train_failed(limit_up_project) -> None:
    config_path = limit_up_project["config_path"]
    _write_factor_and_deep_config(config_path)

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
    payload = run_f2_train(
        limit_up_project["project"],
        config_path=config_path,
        repo_root=limit_up_project["paths"].root,
    )

    experiment_path = Path(payload["experiment_record_path"])
    failed_payload = json.loads(experiment_path.read_text(encoding="utf-8"))
    failed_payload["experiment_id"] = failed_payload["experiment_id"] + "__failed"
    failed_payload["status"] = "failed"
    failed_payload["evaluation"] = {
        "status": "failed",
        "summary": "synthetic failed latest train",
        "classification": "prototype_deep_factor_failure",
        "primary_blockers": ["synthetic latest failure"],
        "promotion_decision": {"evaluated": False, "reason": "synthetic_test_failure"},
        "next_experiment_themes": ["rerun f2_train"],
        "adversarial_robustness": {"status": "not_evaluated", "score": None},
        "regime_transition_drawdown": None,
    }
    failed_experiment_path = experiment_path.with_name(failed_payload["experiment_id"] + ".json")
    failed_experiment_path.write_text(json.dumps(failed_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    with pytest.raises(RuntimeError, match="did not finish successfully"):
        run_f2_verify(
            limit_up_project["project"],
            config_path=config_path,
            repo_root=limit_up_project["paths"].root,
        )


def test_f2_verify_writes_verifier_artifacts_and_experiment_record(limit_up_project) -> None:
    config_path = limit_up_project["config_path"]
    _write_factor_and_deep_config(config_path)

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
    run_f2_train(
        limit_up_project["project"],
        config_path=config_path,
        repo_root=limit_up_project["paths"].root,
    )

    payload = run_f2_verify(
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

    assert experiment.mode == "f2_verify"
    assert experiment.branch_id == "factor_elasticnet_core"
    assert experiment.strategy_candidate_id == "f2_structured_latent_factor_v1"
    assert experiment.evaluation is not None
    assert experiment.backend_adapter is not None
    assert experiment.backend_adapter.adapter_id == "local_pipeline"
    assert experiment.backend_run is not None
    assert experiment.backend_run.status == "succeeded"
    assert experiment.decision_record is not None
    assert experiment.decision_record.decision == payload["decision"]
    assert experiment.evaluation.classification in {"verifier_pass", "verifier_mixed", "verifier_fail"}
    assert payload["decision"] in {"keep_f2_challenger", "promote_f2_next", "reject_f2_v1_and_retain_f1_mainline"}
    assert report["compare_shell"] == "topn_suite_no_stoploss_v1"
    assert {"control", "f1", "f2", "delta_vs_f1"} == set(metrics["series"].tolist())
    assert limit_up_project["paths"].experiment_ledger_path.read_text(encoding="utf-8").find(payload["experiment_id"]) >= 0


def test_f2_verify_rejects_invalid_rank_structure(limit_up_project) -> None:
    config_path = limit_up_project["config_path"]
    _write_factor_and_deep_config(config_path)

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
    train_payload = run_f2_train(
        limit_up_project["project"],
        config_path=config_path,
        repo_root=limit_up_project["paths"].root,
    )

    rank_path = Path(train_payload["rank_path"])
    rank_df = pd.read_parquet(rank_path)
    rank_df = pd.concat([rank_df, rank_df.iloc[[0]]], ignore_index=True)
    rank_df.to_parquet(rank_path, index=False)

    with pytest.raises(RuntimeError, match="duplicate"):
        run_f2_verify(
            limit_up_project["project"],
            config_path=config_path,
            repo_root=limit_up_project["paths"].root,
        )


def test_f2_verify_decision_rule_handles_pass_mixed_and_fail() -> None:
    passed = _decision_from_metrics(
        f1_metrics={"calmar_ratio": 0.5, "annualized_return": 0.20, "max_drawdown": -0.35, "sharpe_ratio": 0.90},
        f2_metrics={"calmar_ratio": 0.65, "annualized_return": 0.19, "max_drawdown": -0.31, "sharpe_ratio": 0.88},
    )
    mixed = _decision_from_metrics(
        f1_metrics={"calmar_ratio": 0.5, "annualized_return": 0.20, "max_drawdown": -0.35, "sharpe_ratio": 0.90},
        f2_metrics={"calmar_ratio": 0.55, "annualized_return": 0.19, "max_drawdown": -0.34, "sharpe_ratio": 0.80},
    )
    failed = _decision_from_metrics(
        f1_metrics={"calmar_ratio": 0.5, "annualized_return": 0.20, "max_drawdown": -0.35, "sharpe_ratio": 0.90},
        f2_metrics={"calmar_ratio": 0.40, "annualized_return": 0.14, "max_drawdown": -0.36, "sharpe_ratio": 0.70},
    )

    assert passed["decision"] == "promote_f2_next"
    assert passed["classification"] == "verifier_pass"
    assert mixed["decision"] == "keep_f2_challenger"
    assert mixed["classification"] == "verifier_mixed"
    assert failed["decision"] == "reject_f2_v1_and_retain_f1_mainline"
    assert failed["classification"] in {"verifier_fail", "verifier_mixed"}
