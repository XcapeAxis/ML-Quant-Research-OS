from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        raise AssertionError(f"Command failed: {' '.join(cmd)}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")


def test_smoke_project_pipeline(limit_up_project) -> None:
    ctx = limit_up_project
    project = ctx["project"]
    config = str(ctx["config_path"])

    commands = [
        [sys.executable, "scripts/steps/12_clean_bars.py", "--project", project, "--config", config, "--full-refresh"],
        [sys.executable, "scripts/run_limit_up_screening.py", "--project", project, "--config", config, "--no-show", "--save", "auto"],
        [sys.executable, "-m", "quant_mvp", "data_validate", "--project", project, "--config", config, "--full-refresh"],
        [sys.executable, "-m", "quant_mvp", "research_audit", "--project", project, "--config", config],
        [sys.executable, "-m", "quant_mvp", "agent_bootstrap", "--project", project],
        [sys.executable, "-m", "quant_mvp", "agent_cycle", "--project", project, "--config", config, "--dry-run"],
        [sys.executable, "-m", "quant_mvp", "promote_candidate", "--project", project, "--config", config],
    ]
    for cmd in commands:
        _run(cmd)

    artifacts = ctx["paths"].artifacts_dir
    meta = ctx["paths"].meta_dir
    signals = ctx["paths"].signals_dir
    docs = ROOT / "docs"

    expected_files = [
        signals / "rank_top3.parquet",
        meta / "run_manifest.json",
        meta / "DATA_QUALITY_REPORT.md",
        meta / "PROJECT_STATE.md",
        meta / "EXPERIMENT_LEDGER.jsonl",
        artifacts / "summary_metrics.csv",
        artifacts / "equity_curve.png",
        artifacts / "promotion_gate.json",
        docs / "SYSTEM_AUDIT.md",
        docs / "FAILURE_MODES.md",
        docs / "DECISION_LOG.md",
    ]
    for path in expected_files:
        assert path.exists(), f"missing file: {path}"
        if path.suffix != ".jsonl":
            assert path.stat().st_size > 0, f"empty file: {path}"
