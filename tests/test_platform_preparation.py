from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from quant_mvp.config import load_config
from quant_mvp.data_quality import clean_table_ready
from quant_mvp.platform.preparation import (
    PREPARATION_STATUS_FILENAME,
    determine_preparation_decision,
    ensure_project_universe,
    prepare_project_data,
)


ROOT = Path(__file__).resolve().parents[1]


def _write_project_config(project: str, source_config: Path, overrides: dict | None = None) -> Path:
  payload = json.loads(source_config.read_text(encoding="utf-8"))
  if overrides:
      payload.update(overrides)

  config_path = ROOT / "configs" / "projects" / f"{project}.json"
  config_path.parent.mkdir(parents=True, exist_ok=True)
  config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
  return config_path


def _run_clean_step(project: str, config_path: Path) -> None:
  cmd = [sys.executable, "scripts/steps/12_clean_bars.py", "--project", project, "--config", str(config_path)]
  result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
  if result.returncode != 0:
      raise AssertionError(f"clean step failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")


def test_ensure_project_universe_runs_symbols_step_when_missing(synthetic_project) -> None:
  ctx = synthetic_project
  paths = ctx["paths"]
  config_path = _write_project_config(ctx["project"], ctx["config_path"])
  if paths.universe_path.exists():
      paths.universe_path.unlink()

  calls: list[tuple[str, tuple[str, ...]]] = []
  logs: list[str] = []

  def runner(script_rel: str, extra_args: tuple[str, ...]) -> int:
      calls.append((script_rel, extra_args))
      paths.universe_path.write_text("000001\n000002\n000003\n", encoding="utf-8")
      return 0

  try:
      ensure_project_universe(
          project=ctx["project"],
          config_path=config_path,
          repo_root=ROOT,
          script_runner=runner,
          log=logs.append,
      )
      assert calls == [("scripts/steps/10_symbols.py", ())]
      assert paths.universe_path.exists()
      assert any("股票池缺失" in item for item in logs)
  finally:
      if config_path.exists():
          config_path.unlink()


def test_determine_preparation_decision_requires_universe(synthetic_project) -> None:
  ctx = synthetic_project
  paths = ctx["paths"]
  config_path = _write_project_config(
      ctx["project"],
      ctx["config_path"],
      overrides={"start_date": "2020-01-01", "end_date": "2020-06-15"},
  )
  if paths.universe_path.exists():
      paths.universe_path.unlink()

  try:
      decision = determine_preparation_decision(project=ctx["project"], config_path=config_path, repo_root=ROOT)
      assert decision.action == "build_universe"
      assert decision.decision_key == "build_universe"
      assert "股票池缺失" in decision.reason
      assert decision.trace[-1]["stage"] == "universe"
  finally:
      if config_path.exists():
          config_path.unlink()


def test_determine_preparation_decision_uses_incremental_when_end_date_missing(synthetic_project) -> None:
  ctx = synthetic_project
  config_path = _write_project_config(
      ctx["project"],
      ctx["config_path"],
      overrides={"start_date": "2020-01-01", "end_date": None},
  )

  try:
      decision = determine_preparation_decision(project=ctx["project"], config_path=config_path, repo_root=ROOT)
      assert decision.action == "incremental"
      assert decision.decision_key == "incremental"
      assert "增量更新" in decision.reason
      assert any(item["stage"] == "decision" for item in decision.trace)
  finally:
      if config_path.exists():
          config_path.unlink()


def test_determine_preparation_decision_rebuilds_clean_only_when_raw_is_ready(synthetic_project) -> None:
  ctx = synthetic_project
  config_path = _write_project_config(
      ctx["project"],
      ctx["config_path"],
      overrides={"start_date": "2020-01-01", "end_date": "2020-06-15"},
  )

  try:
      decision = determine_preparation_decision(project=ctx["project"], config_path=config_path, repo_root=ROOT)
      assert decision.action == "none"
      assert decision.decision_key == "clean_only"
      assert decision.rebuild_clean_only is True
      assert "清洗表缺失" in decision.reason
  finally:
      if config_path.exists():
          config_path.unlink()


def test_determine_preparation_decision_skips_when_clean_is_ready(synthetic_project) -> None:
  ctx = synthetic_project
  config_path = _write_project_config(
      ctx["project"],
      ctx["config_path"],
      overrides={"start_date": "2020-01-01", "end_date": "2020-06-15"},
  )
  _run_clean_step(ctx["project"], config_path)

  try:
      decision = determine_preparation_decision(project=ctx["project"], config_path=config_path, repo_root=ROOT)
      assert decision.action == "none"
      assert decision.decision_key == "skip"
      assert decision.rebuild_clean_only is False
      assert "覆盖充足" in decision.reason
  finally:
      if config_path.exists():
          config_path.unlink()


def test_prepare_project_data_rebuilds_clean_without_update(synthetic_project) -> None:
  ctx = synthetic_project
  config_path = _write_project_config(
      ctx["project"],
      ctx["config_path"],
      overrides={"start_date": "2020-01-01", "end_date": "2020-06-15"},
  )
  logs: list[str] = []
  calls: list[tuple[str, tuple[str, ...]]] = []

  def runner(script_rel: str, extra_args: tuple[str, ...]) -> int:
      calls.append((script_rel, extra_args))
      if script_rel == "scripts/audit_db.py":
          summary_path = ctx["paths"].meta_dir / "db_coverage_summary.json"
          summary_path.write_text(json.dumps({"clean_coverage_ratio": 1.0}, ensure_ascii=False), encoding="utf-8")
          return 0
      return 0

  try:
      decision = prepare_project_data(
          project=ctx["project"],
          config_path=config_path,
          repo_root=ROOT,
          script_runner=runner,
          log=logs.append,
      )

      cfg, _ = load_config(ctx["project"], config_path=config_path)
      clean_table = str(cfg.get("data_quality", {}).get("clean_table", "bars_clean"))
      status_path = ctx["paths"].meta_dir / PREPARATION_STATUS_FILENAME
      assert decision.action == "none"
      assert decision.decision_key == "clean_only"
      assert decision.rebuild_clean_only is True
      assert calls == [("scripts/audit_db.py", ("--data-mode", "clean"))]
      assert clean_table_ready(ctx["db_path"], freq="1d", clean_table=clean_table)
      assert any("正在执行数据清洗" in item for item in logs)
      assert status_path.exists()
      persisted = json.loads(status_path.read_text(encoding="utf-8"))
      assert persisted["status"] == "succeeded"
      assert persisted["decision"] == "clean_only"
      assert persisted["decision_trace"]
  finally:
      if config_path.exists():
          config_path.unlink()


def test_prepare_project_data_fails_fast_when_update_fails(synthetic_project) -> None:
  ctx = synthetic_project
  config_path = _write_project_config(
      ctx["project"],
      ctx["config_path"],
      overrides={"start_date": "2020-01-01", "end_date": None},
  )
  calls: list[tuple[str, tuple[str, ...]]] = []

  def runner(script_rel: str, extra_args: tuple[str, ...]) -> int:
      calls.append((script_rel, extra_args))
      if script_rel == "scripts/steps/11_update_bars.py":
          return 1
      return 0

  try:
      with pytest.raises(RuntimeError, match="自动补数失败"):
          prepare_project_data(
              project=ctx["project"],
              config_path=config_path,
              repo_root=ROOT,
              script_runner=runner,
              log=lambda _: None,
          )
      assert calls == [("scripts/steps/11_update_bars.py", ("--mode", "incremental"))]

      status_path = ctx["paths"].meta_dir / PREPARATION_STATUS_FILENAME
      assert status_path.exists()
      persisted = json.loads(status_path.read_text(encoding="utf-8"))
      assert persisted["status"] == "failed"
      assert persisted["decision"] == "incremental"
      assert "自动补数失败" in persisted["error_message"]
  finally:
      if config_path.exists():
          config_path.unlink()
