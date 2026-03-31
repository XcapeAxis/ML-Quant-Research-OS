from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd

from quant_mvp.config import load_config
from quant_mvp.pools import load_latest_branch_pool_snapshot
from quant_mvp.research_core import resolve_limit_up_config
from quant_mvp.selection import filter_top_limit_up
from quant_mvp.selection import build_limit_up_screening_rank


def _run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise AssertionError(f"command failed: {' '.join(cmd)}\nstdout={result.stdout}\nstderr={result.stderr}")


def test_run_limit_up_screening_consistency(limit_up_project) -> None:
    project = limit_up_project["project"]
    config = str(limit_up_project["config_path"])
    paths = limit_up_project["paths"]

    _run([sys.executable, "scripts/steps/12_clean_bars.py", "--project", project, "--config", config, "--full-refresh"])
    _run([sys.executable, "scripts/steps/20_build_rank.py", "--project", project, "--config", config])
    _run([sys.executable, "scripts/steps/30_bt_rebalance.py", "--project", project, "--config", config, "--no-show", "--save", "auto"])

    modular_rank = pd.read_parquet(paths.signals_dir / "rank_top3.parquet")
    modular_metrics = pd.read_csv(paths.artifacts_dir / "summary_metrics.csv")

    _run([sys.executable, "scripts/run_limit_up_screening.py", "--project", project, "--config", config, "--no-show", "--save", "auto"])

    standalone_rank = pd.read_parquet(paths.signals_dir / "rank_top3.parquet")
    standalone_metrics = pd.read_csv(paths.artifacts_dir / "summary_metrics.csv")

    pd.testing.assert_frame_equal(
        modular_rank.sort_values(["date", "rank", "code"]).reset_index(drop=True),
        standalone_rank.sort_values(["date", "rank", "code"]).reset_index(drop=True),
    )
    pd.testing.assert_frame_equal(modular_metrics, standalone_metrics)


def test_filter_top_limit_up_keeps_minimum_branch_floor() -> None:
    codes = [f"{idx:06d}" for idx in range(1, 43)]
    counts = pd.Series({code: 10 - (idx % 10) for idx, code in enumerate(codes)})

    screened = filter_top_limit_up(codes, counts, top_pct=0.1, min_keep=6)

    assert len(screened) == 6
    assert all(counts[code] > 0 for code in screened)
    assert counts[screened[0]] >= counts[screened[-1]]


def test_current_project_baseline_branch_pool_produces_rank() -> None:
    cfg, _ = load_config("as_share_research_v1")
    branch = load_latest_branch_pool_snapshot("as_share_research_v1", branch_id="baseline_limit_up")
    assert branch is not None

    result = build_limit_up_screening_rank(
        db_path=Path(str(cfg["db_path"])),
        freq=str(cfg["freq"]),
        universe_codes=branch.codes,
        cfg=resolve_limit_up_config(cfg),
        start_date=cfg.get("start_date"),
        end_date=cfg.get("end_date"),
    )

    assert not result.rank_df.empty
    assert result.rank_df["code"].nunique() >= int(cfg["stock_num"])


def test_current_project_risk_branch_pool_still_produces_rank() -> None:
    cfg, _ = load_config("as_share_research_v1")
    branch = load_latest_branch_pool_snapshot("as_share_research_v1", branch_id="risk_constrained_limit_up")
    assert branch is not None

    branch_cfg = resolve_limit_up_config(cfg)
    branch_cfg.stock_num = 4
    result = build_limit_up_screening_rank(
        db_path=Path(str(cfg["db_path"])),
        freq=str(cfg["freq"]),
        universe_codes=branch.codes,
        cfg=branch_cfg,
        start_date=cfg.get("start_date"),
        end_date=cfg.get("end_date"),
    )

    assert not result.rank_df.empty
    assert result.rank_df["code"].nunique() >= 4
