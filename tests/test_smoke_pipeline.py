from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        raise AssertionError(f"Command failed: {' '.join(cmd)}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")


def test_smoke_project_pipeline(synthetic_project) -> None:
    ctx = synthetic_project
    project = ctx["project"]
    config = str(ctx["config_path"])

    commands = [
        [sys.executable, "scripts/steps/20_build_rank.py", "--project", project, "--config", config],
        [
            sys.executable,
            "scripts/steps/30_bt_rebalance.py",
            "--project",
            project,
            "--config",
            config,
            "--no-show",
            "--save",
            "auto",
        ],
        [sys.executable, "scripts/audit_db.py", "--project", project, "--config", config],
        [sys.executable, "scripts/steps/31_bt_baselines.py", "--project", project, "--config", config],
        [sys.executable, "scripts/steps/32_cost_sweep.py", "--project", project, "--config", config],
        [sys.executable, "scripts/steps/33_walk_forward.py", "--project", project, "--config", config],
        [sys.executable, "scripts/steps/40_make_report.py", "--project", project, "--config", config],
    ]
    for cmd in commands:
        _run(cmd)

    artifacts = ctx["paths"].artifacts_dir
    meta = ctx["paths"].meta_dir
    signals = ctx["paths"].signals_dir

    expected_files = [
        signals / "rank_top5.parquet",
        meta / "run_manifest.json",
        artifacts / "summary_metrics.csv",
        artifacts / "topn_1_5.png",
        artifacts / "report.md",
    ]
    for path in expected_files:
        assert path.exists(), f"missing file: {path}"
        assert path.stat().st_size > 0, f"empty file: {path}"
