from __future__ import annotations

import subprocess
import sys

import pandas as pd


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
