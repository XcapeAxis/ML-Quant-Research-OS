from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from quant_mvp.experiment_graph import read_experiment_record
from quant_mvp.f1_pipeline import run_f1_train
from quant_mvp.f1_verify import _decision_from_metrics, run_f1_verify
from quant_mvp.pools import build_core_universe_snapshot


def _write_factor_model_config(config_path, *, profile: str = "f1_elasticnet_v1") -> None:
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    payload["start_date"] = "2020-01-07"
    payload["topk"] = 3
    payload["topn_max"] = 3
    payload["stock_num"] = 3
    payload["factor_model"] = {
        "profile": profile,
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


def test_f1_verify_rejects_stale_f1_artifacts(limit_up_project) -> None:
    config_path = limit_up_project["config_path"]
    _write_factor_model_config(config_path)

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

    _write_factor_model_config(config_path, profile="f1_elasticnet_v1_stale")

    with pytest.raises(RuntimeError, match="rerun f1_train first"):
        run_f1_verify(
            limit_up_project["project"],
            config_path=config_path,
            repo_root=limit_up_project["paths"].root,
        )


def test_f1_verify_writes_verifier_artifacts_and_experiment_record(limit_up_project) -> None:
    config_path = limit_up_project["config_path"]
    _write_factor_model_config(config_path)

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

    payload = run_f1_verify(
        limit_up_project["project"],
        config_path=config_path,
        repo_root=limit_up_project["paths"].root,
    )

    experiment = read_experiment_record(
        limit_up_project["project"],
        payload["experiment_id"],
        repo_root=limit_up_project["paths"].root,
    )
    report = json.loads(Path(payload["verifier_json_path"]).read_text(encoding="utf-8"))
    control_rank = pd.read_parquet(payload["control_rank_path"])

    assert experiment.mode == "f1_verify"
    assert experiment.branch_id == "factor_elasticnet_core"
    assert experiment.strategy_candidate_id == "f1_elasticnet_v1"
    assert experiment.evaluation is not None
    assert experiment.evaluation.classification in {"verifier_pass", "verifier_mixed", "verifier_fail"}
    assert payload["decision"] in {"keep_f1_mainline", "keep_f1_local_and_do_one_more_bounded_risk_variant"}
    assert set(control_rank.columns) == {"date", "code", "score", "rank"}
    assert report["compare_shell"] == "topn_suite_no_stoploss_v1"
    assert limit_up_project["paths"].experiment_ledger_path.read_text(encoding="utf-8").find(payload["experiment_id"]) >= 0


def test_f1_verify_decision_rule_handles_pass_mixed_and_fail() -> None:
    passed = _decision_from_metrics(
        f1_metrics={"max_drawdown": -0.30, "annualized_return": 0.20, "sharpe_ratio": 1.0},
        control_metrics={"max_drawdown": -0.36, "annualized_return": 0.19, "sharpe_ratio": 0.8},
    )
    mixed = _decision_from_metrics(
        f1_metrics={"max_drawdown": -0.31, "annualized_return": 0.20, "sharpe_ratio": 0.7},
        control_metrics={"max_drawdown": -0.37, "annualized_return": 0.19, "sharpe_ratio": 0.9},
    )
    failed = _decision_from_metrics(
        f1_metrics={"max_drawdown": -0.42, "annualized_return": 0.10, "sharpe_ratio": 0.3},
        control_metrics={"max_drawdown": -0.35, "annualized_return": 0.14, "sharpe_ratio": 0.6},
    )

    assert passed["classification"] == "verifier_pass"
    assert passed["next_action"] == "reopen_light_scouting_for_f2_r1"
    assert mixed["classification"] == "verifier_mixed"
    assert mixed["decision"] == "keep_f1_mainline"
    assert failed["classification"] == "verifier_fail"
    assert failed["decision"] == "keep_f1_local_and_do_one_more_bounded_risk_variant"
