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
        [sys.executable, "-m", "quant_mvp", "memory_bootstrap", "--project", project],
        [sys.executable, "-m", "quant_mvp", "memory_sync", "--project", project, "--config", config],
        [
            sys.executable,
            "-m",
            "quant_mvp",
            "subagent_plan",
            "--project",
            project,
            "--task-summary",
            "Split fixture data and validation work into low-overlap packages",
            "--breadth",
            "3",
            "--independence",
            "0.9",
            "--file-overlap",
            "0.15",
            "--validation-load",
            "0.8",
            "--coordination-cost",
            "0.2",
            "--risk-isolation",
            "0.6",
            "--focus-tag",
            "data",
            "--focus-tag",
            "validation",
            "--activate",
        ],
        [sys.executable, "-m", "quant_mvp", "agent_cycle", "--project", project, "--config", config, "--dry-run"],
        [sys.executable, "-m", "quant_mvp", "promote_candidate", "--project", project, "--config", config],
        [sys.executable, "-m", "quant_mvp", "generate_handoff", "--project", project],
        [
            sys.executable,
            "-m",
            "quant_mvp",
            "verify_snapshot",
            "--project",
            project,
            "--passed-command",
            "python -m pytest tests -q",
            "--data-status",
            "synthetic validated bars available in fixture DB",
            "--engineering-boundary",
            "contract and tracked-memory automation work in tests",
            "--research-boundary",
            "synthetic fixture only; default-project real data still required",
        ],
    ]
    for cmd in commands:
        _run(cmd)

    artifacts = ctx["paths"].artifacts_dir
    meta = ctx["paths"].meta_dir
    memory = ctx["paths"].memory_dir
    signals = ctx["paths"].signals_dir
    docs = ROOT / "docs"

    expected_files = [
        signals / "rank_top3.parquet",
        meta / "run_manifest.json",
        meta / "DATA_QUALITY_REPORT.md",
        memory / "PROJECT_STATE.md",
        memory / "RESEARCH_MEMORY.md",
        memory / "EXECUTION_QUEUE.md",
        memory / "EXPERIMENT_LEDGER.jsonl",
        memory / "HANDOFF_NEXT_CHAT.md",
        memory / "MIGRATION_PROMPT_NEXT_CHAT.md",
        memory / "VERIFY_LAST.md",
        memory / "SESSION_STATE.json",
        memory / "SUBAGENT_REGISTRY.md",
        memory / "SUBAGENT_LEDGER.jsonl",
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
    assert (meta / "agent_cycles").exists()
    assert any((meta / "agent_cycles").iterdir())
    assert ctx["paths"].subagent_artifacts_dir.exists()
    assert any(ctx["paths"].subagent_artifacts_dir.iterdir())
    assert "研究进度" in (memory / "PROJECT_STATE.md").read_text(encoding="utf-8")
    assert "研究进度" in (memory / "RESEARCH_MEMORY.md").read_text(encoding="utf-8")
    assert "执行队列" in (memory / "EXECUTION_QUEUE.md").read_text(encoding="utf-8")
