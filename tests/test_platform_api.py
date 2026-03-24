from __future__ import annotations

import json
import subprocess
import sys
import time
import types
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from quant_mvp import cli as cli_module
from quant_mvp.platform.app import create_app
from quant_mvp.platform.jobs import StepExecutionResult
from quant_mvp.platform.readiness import DOCTOR_FILENAME, READINESS_FILENAME, project_doctor
from quant_mvp.platform.settings import load_platform_settings
from quant_mvp.project import resolve_project_paths


ROOT = Path(__file__).resolve().parents[1]


def _write_test_project_config(project: str, source_config: Path, overrides: dict | None = None) -> Path:
  payload = json.loads(source_config.read_text(encoding="utf-8"))
  if overrides:
      payload.update(overrides)

  paths = resolve_project_paths(project)
  paths.config_path.parent.mkdir(parents=True, exist_ok=True)
  paths.config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
  return paths.config_path


def _make_client(tmp_path: Path) -> TestClient:
  settings = load_platform_settings(
      repo_root=ROOT,
      overrides={
          "platform_db_path": str(tmp_path / "platform.db"),
          "mode": "local",
          "max_concurrent_jobs": 1,
      },
  )
  app = create_app(settings)
  return TestClient(app)


def _wait_for_terminal_status(client: TestClient, job_id: str, timeout_seconds: int = 60) -> dict:
  deadline = time.time() + timeout_seconds
  while time.time() < deadline:
      detail = client.get(f"/api/jobs/{job_id}")
      assert detail.status_code == 200
      payload = detail.json()
      if payload["status"] in {"succeeded", "failed", "cancelled"}:
          return payload
      time.sleep(0.5)
  raise AssertionError(f"job did not finish in time: {job_id}")


def _run_clean_step(project: str, config_path: Path) -> None:
  cmd = [sys.executable, "scripts/steps/12_clean_bars.py", "--project", project, "--config", str(config_path)]
  result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
  if result.returncode != 0:
      raise AssertionError(f"clean step failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")


def test_platform_project_config_roundtrip(synthetic_project, tmp_path: Path) -> None:
  ctx = synthetic_project
  config_path = _write_test_project_config(ctx["project"], ctx["config_path"])
  try:
      with _make_client(tmp_path) as client:
          projects = client.get("/api/projects")
          assert projects.status_code == 200
          names = {item["name"] for item in projects.json()}
          assert ctx["project"] in names

          response = client.get(f"/api/projects/{ctx['project']}/config")
          assert response.status_code == 200
          payload = response.json()
          assert payload["project"] == ctx["project"]
          assert payload["raw_config"]["cash"] == 1000000

          payload["raw_config"]["cash"] = 234567
          updated = client.put(f"/api/projects/{ctx['project']}/config", json=payload["raw_config"])
          assert updated.status_code == 200
          assert updated.json()["raw_config"]["cash"] == 234567

          saved = json.loads(config_path.read_text(encoding="utf-8"))
          assert saved["cash"] == 234567
  finally:
      if config_path.exists():
          config_path.unlink()


def test_platform_readiness_requires_explicit_db_path(synthetic_project, tmp_path: Path) -> None:
  ctx = synthetic_project
  config_path = _write_test_project_config(ctx["project"], ctx["config_path"], overrides={"db_path": None})
  try:
      with _make_client(tmp_path) as client:
          readiness = client.get(f"/api/projects/{ctx['project']}/readiness")
          assert readiness.status_code == 200
          payload = readiness.json()
          assert payload["ready"] is False
          assert payload["blocking_issue_details"][0]["code"] == "db_path_missing"
          assert "显式 db_path" in payload["blocking_issues"][0]

          readiness_path = ctx["paths"].meta_dir / READINESS_FILENAME
          assert readiness_path.exists()

          created = client.post(
              "/api/jobs",
              json={
                  "project": ctx["project"],
                  "pipeline": "backtest_only",
                  "execution_mode": "serial",
              },
          )
          assert created.status_code == 400
          assert "显式 db_path" in created.json()["detail"]
  finally:
      if config_path.exists():
          config_path.unlink()


def test_platform_readiness_reports_valid_external_db(synthetic_project, tmp_path: Path) -> None:
  ctx = synthetic_project
  config_path = _write_test_project_config(
      ctx["project"],
      ctx["config_path"],
      overrides={"start_date": "2020-01-01", "end_date": "2020-06-15"},
  )
  _run_clean_step(ctx["project"], config_path)
  try:
      with _make_client(tmp_path) as client:
          readiness = client.get(f"/api/projects/{ctx['project']}/readiness?pipeline=backtest_only")
          assert readiness.status_code == 200
          payload = readiness.json()
          assert payload["ready"] is True
          assert payload["db_status"]["ready"] is True
          assert payload["db_status"]["explicit_configured"] is True
          assert payload["db_status"]["raw_rows"] > 0
          assert payload["db_status"]["file_size_bytes"] > 0
          assert payload["db_status"]["modified_at"] is not None
          assert payload["db_status"]["window_coverage"]["enabled"] is True
          assert payload["decision_trace"]
          assert payload["blocking_issue_details"] == []
          assert payload["network_status"]["checks"] == []

          readiness_path = ctx["paths"].meta_dir / READINESS_FILENAME
          assert readiness_path.exists()
          persisted = json.loads(readiness_path.read_text(encoding="utf-8"))
          assert persisted["db_status"]["window_coverage"]["enabled"] is True
  finally:
      if config_path.exists():
          config_path.unlink()


def test_project_doctor_persists_full_diagnostics(synthetic_project, tmp_path: Path, monkeypatch) -> None:
  ctx = synthetic_project
  config_path = _write_test_project_config(
      ctx["project"],
      ctx["config_path"],
      overrides={"start_date": "2020-01-01", "end_date": "2020-06-15"},
  )
  _run_clean_step(ctx["project"], config_path)

  def fake_network_diagnostics(_settings, upstream_keys=None):
      return {
          "proxy_url": "http://proxy.internal:8080",
          "ca_bundle_path": "C:/certs/internal.pem",
          "connect_timeout_seconds": 5,
          "read_timeout_seconds": 15,
          "using_proxy": True,
          "using_custom_ca": True,
          "ca_bundle_exists": True,
          "blocking_issues": [],
          "blocking_issue_details": [],
          "warnings": [],
          "checks": [
              {
                  "key": "eastmoney",
                  "label": "东方财富历史行情",
                  "url": "https://push2his.eastmoney.com/api/qt/stock/kline/get",
                  "reachable": True,
                  "http_status": 200,
                  "latency_ms": 23.5,
                  "error_code": None,
                  "error_summary": None,
                  "suggestion": None,
              }
          ],
      }

  monkeypatch.setattr("quant_mvp.platform.readiness.run_network_diagnostics", fake_network_diagnostics)
  settings = load_platform_settings(
      repo_root=ROOT,
      overrides={
          "platform_db_path": str(tmp_path / "platform.db"),
          "mode": "local",
          "max_concurrent_jobs": 1,
      },
  )

  try:
      payload = project_doctor(
          settings=settings,
          project=ctx["project"],
          pipeline="backtest_only",
          config_path_override=config_path,
      )
      assert payload["ready"] is True
      assert payload["network_status"]["checks"][0]["latency_ms"] == 23.5
      assert payload["decision_trace"]

      doctor_path = ctx["paths"].meta_dir / DOCTOR_FILENAME
      assert doctor_path.exists()
      persisted = json.loads(doctor_path.read_text(encoding="utf-8"))
      assert persisted["network_status"]["checks"][0]["key"] == "eastmoney"
  finally:
      if config_path.exists():
          config_path.unlink()


def test_platform_doctor_route_can_be_stubbed(synthetic_project, tmp_path: Path, monkeypatch) -> None:
  ctx = synthetic_project
  config_path = _write_test_project_config(ctx["project"], ctx["config_path"])
  sample_payload = {
      "project": ctx["project"],
      "pipeline": "backtest_only",
      "ready": False,
      "config": {"path": str(config_path), "exists": True},
      "config_path": str(config_path),
      "universe_exists": True,
      "universe_path": str(ctx["paths"].universe_path),
      "db_status": {
          "configured_path": None,
          "explicit_configured": False,
          "path_is_absolute": False,
          "exists": False,
          "sqlite_openable": False,
          "tables": [],
          "raw_table": "bars_raw",
          "clean_table": "bars_clean",
          "raw_rows": 0,
          "clean_rows": 0,
          "raw_codes": 0,
          "clean_codes": 0,
          "raw_date_range": {"min": None, "max": None},
          "clean_date_range": {"min": None, "max": None},
          "file_size_bytes": None,
          "modified_at": None,
          "window_coverage": {"enabled": False, "reason": "db_unavailable"},
          "ready": False,
          "issues": ["缺少显式 db_path"],
      },
      "network_status": {
          "proxy_url": None,
          "ca_bundle_path": None,
          "connect_timeout_seconds": 5,
          "read_timeout_seconds": 15,
          "using_proxy": False,
          "using_custom_ca": False,
          "ca_bundle_exists": True,
          "blocking_issues": [],
          "blocking_issue_details": [],
          "warnings": [],
          "checks": [],
      },
      "preparation": {
          "action": None,
          "decision_key": None,
          "reason": None,
          "rebuild_clean_only": False,
      },
      "decision_trace": [{"stage": "inputs", "message": "已载入项目配置。", "detail": {}}],
      "required_upstreams": [],
      "warning_details": [],
      "blocking_issue_details": [
          {
              "code": "db_path_missing",
              "message": "缺少显式 db_path",
              "suggestion": "请填写外部 market.db 绝对路径。",
              "detail": {},
          }
      ],
      "blocking_issues": ["缺少显式 db_path"],
      "warnings": [],
  }
  monkeypatch.setattr("quant_mvp.platform.app.project_doctor", lambda **_: sample_payload)

  try:
      with _make_client(tmp_path) as client:
          response = client.get(f"/api/projects/{ctx['project']}/doctor?pipeline=backtest_only")
          assert response.status_code == 200
          payload = response.json()
          assert payload["blocking_issue_details"][0]["code"] == "db_path_missing"
          assert payload["decision_trace"][0]["stage"] == "inputs"
  finally:
      if config_path.exists():
          config_path.unlink()


def test_platform_full_analysis_job_creates_snapshot(synthetic_project, tmp_path: Path) -> None:
  ctx = synthetic_project
  config_path = _write_test_project_config(
      ctx["project"],
      ctx["config_path"],
      overrides={
          "start_date": "2020-01-01",
          "end_date": "2020-06-15",
      },
  )
  _run_clean_step(ctx["project"], config_path)
  try:
      with _make_client(tmp_path) as client:
          created = client.post(
              "/api/jobs",
              json={
                  "project": ctx["project"],
                  "pipeline": "full_analysis_pack",
                  "execution_mode": "serial",
              },
          )
          assert created.status_code == 200
          job_id = created.json()["id"]

          detail_payload = _wait_for_terminal_status(client, job_id)
          assert detail_payload["status"] == "succeeded"
          assert [step["step_key"] for step in detail_payload["steps"][:2]] == ["build_universe", "prepare_data"]

          runs = client.get(f"/api/projects/{ctx['project']}/runs")
          assert runs.status_code == 200
          run_payload = runs.json()
          assert any(item["run_id"] == job_id for item in run_payload)

          detail = client.get(f"/api/projects/{ctx['project']}/runs/{job_id}")
          assert detail.status_code == 200
          run_detail = detail.json()
          assert run_detail["metrics_rows"]
          assert Path(run_detail["config_snapshot_path"]).exists()

          events = client.get(f"/api/jobs/{job_id}/events")
          assert events.status_code == 200
          assert "event: complete" in events.text
  finally:
      if config_path.exists():
          config_path.unlink()


def test_platform_job_failure_surfaces_chinese_prepare_data_message(synthetic_project, tmp_path: Path, monkeypatch) -> None:
  ctx = synthetic_project
  config_path = _write_test_project_config(
      ctx["project"],
      ctx["config_path"],
      overrides={"start_date": "2020-01-01", "end_date": "2020-06-15"},
  )
  try:
      with _make_client(tmp_path) as client:
          manager = client.app.state.job_manager

          def fake_run_step(self, job_id: str, step, log_handle, config_path: Path, project: str):
              del job_id, log_handle, config_path, project
              if step.step_key == "build_universe":
                  return StepExecutionResult(exit_code=0)
              if step.step_key == "prepare_data":
                  return StepExecutionResult(
                      exit_code=1,
                      error_message="目标回测区间数据缺失，自动补数失败，请检查网络、代理或数据源。",
                  )
              return StepExecutionResult(exit_code=0)

          monkeypatch.setattr(manager, "_run_step", types.MethodType(fake_run_step, manager))

          created = client.post(
              "/api/jobs",
              json={
                  "project": ctx["project"],
                  "pipeline": "signal_build",
                  "execution_mode": "serial",
              },
          )
          assert created.status_code == 200
          job_id = created.json()["id"]

          detail_payload = _wait_for_terminal_status(client, job_id)
          assert detail_payload["status"] == "failed"
          assert "自动补数失败" in detail_payload["error_message"]
          assert [step["step_key"] for step in detail_payload["steps"]] == ["build_universe", "prepare_data", "rank"]
          assert detail_payload["steps"][1]["error_message"] == "目标回测区间数据缺失，自动补数失败，请检查网络、代理或数据源。"
          assert detail_payload["steps"][2]["status"] == "skipped"

          events = client.get(f"/api/jobs/{job_id}/events")
          assert events.status_code == 200
          assert "自动补数失败" in events.text
  finally:
      if config_path.exists():
          config_path.unlink()


def test_platform_network_diagnostics_route_can_be_stubbed(tmp_path: Path, monkeypatch) -> None:
  def fake_network_diagnostics(_settings):
      return {
          "proxy_url": "http://proxy.internal:8080",
          "ca_bundle_path": "C:/certs/internal.pem",
          "connect_timeout_seconds": 5,
          "read_timeout_seconds": 15,
          "using_proxy": True,
          "using_custom_ca": True,
          "ca_bundle_exists": True,
          "blocking_issues": [],
          "blocking_issue_details": [],
          "warnings": [],
          "checks": [
              {
                  "key": "eastmoney",
                  "label": "东方财富历史行情",
                  "url": "https://push2his.eastmoney.com/api/qt/stock/kline/get",
                  "reachable": True,
                  "http_status": 200,
                  "latency_ms": 18.0,
                  "error_code": None,
                  "error_summary": None,
                  "suggestion": None,
              }
          ],
      }

  monkeypatch.setattr("quant_mvp.platform.app.run_network_diagnostics", fake_network_diagnostics)
  with _make_client(tmp_path) as client:
      response = client.get("/api/platform/network/diagnostics")
      assert response.status_code == 200
      payload = response.json()
      assert payload["using_proxy"] is True
      assert payload["checks"][0]["key"] == "eastmoney"
      assert payload["checks"][0]["latency_ms"] == 18.0


def test_cli_doctor_exits_nonzero_when_blocking_issues_exist(monkeypatch, capsys) -> None:
  monkeypatch.setattr(cli_module, "load_platform_settings", lambda repo_root=None: object())
  monkeypatch.setattr(
      cli_module,
      "project_doctor",
      lambda **_: {
          "project": "demo",
          "blocking_issue_details": [{"code": "db_path_missing", "message": "缺少显式 db_path", "suggestion": None, "detail": {}}],
          "blocking_issues": ["缺少显式 db_path"],
      },
  )
  monkeypatch.setattr(sys, "argv", ["quant_mvp", "doctor", "--project", "demo"])

  with pytest.raises(SystemExit) as exc:
      cli_module.main()

  assert exc.value.code == 1
  payload = json.loads(capsys.readouterr().out)
  assert payload["project"] == "demo"
  assert payload["blocking_issue_details"][0]["code"] == "db_path_missing"
