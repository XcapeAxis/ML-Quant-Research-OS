from __future__ import annotations

import pandas as pd

from quant_mvp.config import load_config
from quant_mvp.research_core import build_limit_up_rank_artifacts, run_limit_up_backtest_artifacts
from quant_mvp.universe import load_universe_codes
from quant_mvp.validation.baselines import run_simple_baselines
from quant_mvp.validation.leakage import audit_strategy_leakage


def test_leakage_guards(limit_up_project) -> None:
    project = limit_up_project["project"]
    cfg, paths = load_config(project, config_path=limit_up_project["config_path"])
    universe = load_universe_codes(project)
    rank_artifacts = build_limit_up_rank_artifacts(cfg=cfg, paths=paths, universe_codes=universe)
    backtest_artifacts = run_limit_up_backtest_artifacts(
        cfg=cfg,
        paths=paths,
        rank_df=rank_artifacts.selection.rank_df,
        save="none",
        no_show=True,
    )

    report = audit_strategy_leakage(
        rank_df=rank_artifacts.selection.rank_df,
        close_panel=backtest_artifacts.close_panel,
        volume_panel=backtest_artifacts.volume_panel,
        cfg=cfg,
        universe_codes=universe,
    )
    assert report.passed

    bad_rank = rank_artifacts.selection.rank_df.copy()
    bad_rank.loc[bad_rank.index[0], "date"] = pd.Timestamp("2099-01-05")
    bad_report = audit_strategy_leakage(
        rank_df=bad_rank,
        close_panel=backtest_artifacts.close_panel,
        volume_panel=backtest_artifacts.volume_panel,
        cfg=cfg,
        universe_codes=universe,
    )
    assert not bad_report.passed
    assert any(item.check == "timestamp_alignment" for item in bad_report.issues)


def test_backtest_artifacts_load_benchmark_series_when_not_ranked(limit_up_project) -> None:
    project = limit_up_project["project"]
    cfg, paths = load_config(project, config_path=limit_up_project["config_path"])
    universe = load_universe_codes(project)
    rank_artifacts = build_limit_up_rank_artifacts(cfg=cfg, paths=paths, universe_codes=universe)
    benchmark_code = str(cfg.get("baselines", {}).get("benchmark_code", "000001")).zfill(6)

    rank_without_benchmark = rank_artifacts.selection.rank_df.loc[
        rank_artifacts.selection.rank_df["code"].astype(str).str.zfill(6) != benchmark_code
    ].copy()

    assert benchmark_code not in rank_without_benchmark["code"].astype(str).str.zfill(6).unique()

    backtest_artifacts = run_limit_up_backtest_artifacts(
        cfg=cfg,
        paths=paths,
        rank_df=rank_without_benchmark,
        save="none",
        no_show=True,
    )

    baselines = run_simple_baselines(
        close_panel=backtest_artifacts.close_panel,
        benchmark_code=benchmark_code,
        benchmark_series=backtest_artifacts.benchmark_series,
    )

    assert benchmark_code not in backtest_artifacts.close_panel.columns
    assert benchmark_code not in backtest_artifacts.volume_panel.columns
    assert not backtest_artifacts.benchmark_series.empty
    assert baselines["benchmark_available"] is True
