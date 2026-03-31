from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

import quant_mvp.excel_export as excel_export_module
from quant_mvp.excel_export import FEED_VERSION, WORKSHEET_NAMES, run_excel_export
from quant_mvp.memory.writeback import bootstrap_memory_files, load_machine_state, record_experiment_result, save_machine_state


def _seed_console_state(project: str, *, repo_root: Path) -> None:
    bootstrap_memory_files(project, repo_root=repo_root)
    paths, state = load_machine_state(project, repo_root=repo_root)
    report_path = paths.artifacts_dir / "f1" / "F1_BOUNDED_VERIFIER.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text('{"decision": "keep_f1_mainline"}\n', encoding="utf-8")

    state.update(
        {
            "project": project,
            "current_phase": "Excel console MVP",
            "current_task": "Freeze web, export feed, and review the workbook.",
            "current_blocker": "Need an internal console that is simpler than the local web UI.",
            "next_priority_action": "Generate the Excel console feed and workbook.",
            "last_verified_capability": "F1 verifier completed and produced a bounded report.",
            "canonical_universe_id": "cn_a_mainboard_all_v1",
            "effective_subagent_gate_mode": "OFF",
            "readiness": {"ready": True, "stage": "validation-ready"},
            "current_primary_strategy_ids": ["f1_elasticnet_v1"],
            "current_secondary_strategy_ids": ["f2_structured_latent_factor_v1", "baseline_limit_up"],
            "current_blocked_strategy_ids": ["risk_constrained_limit_up"],
            "strategy_candidates": [
                {
                    "strategy_id": "f1_elasticnet_v1",
                    "name": "F1 ElasticNet",
                    "track": "primary",
                    "current_stage": "validation",
                    "decision": "continue",
                    "latest_result": "Top6 shared shell is still above the drawdown line.",
                    "next_validation": "Run one more bounded challenger.",
                    "artifact_refs": [str(report_path)],
                },
                {
                    "strategy_id": "baseline_limit_up",
                    "name": "Baseline Control",
                    "track": "secondary",
                    "current_stage": "control",
                    "decision": "continue",
                    "latest_result": "Kept only as a control harness.",
                    "next_validation": "Use the same shared shell for comparisons.",
                    "artifact_refs": [str(report_path)],
                },
            ],
        }
    )
    save_machine_state(project, state, repo_root=repo_root)
    record_experiment_result(
        project,
        {
            "timestamp": "2026-03-31T10:38:56+00:00",
            "experiment_id": f"{project}__factor_elasticnet_core__f2_verify__20260331T103833Z",
            "hypothesis": "F2.1 should improve F1's tradeoff on the same shared shell.",
            "result": "verifier_mixed",
            "artifact_refs": [str(report_path)],
            "blockers": ["drawdown still above threshold"],
        },
        repo_root=repo_root,
    )


def test_excel_export_generates_feed_and_workbook(synthetic_project) -> None:
    project = synthetic_project["project"]
    repo_root = synthetic_project["paths"].root
    _seed_console_state(project, repo_root=repo_root)

    def fake_convert(source_xlsx: Path, target_xlsm: Path) -> None:
        shutil.copyfile(source_xlsx, target_xlsm)

    original_convert = excel_export_module._convert_xlsx_to_xlsm
    excel_export_module._convert_xlsx_to_xlsm = fake_convert
    try:
        result = run_excel_export(project, repo_root=repo_root, probe_vba=False)
    finally:
        excel_export_module._convert_xlsx_to_xlsm = original_convert

    manifest_path = Path(result["manifest_path"])
    workbook_path = Path(result["workbook_path"])
    assert manifest_path.exists()
    assert workbook_path.exists()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["project"] == project
    assert manifest["feed_version"] == FEED_VERSION
    assert manifest["workbook_mode"] == "launcher_links_fallback"
    assert manifest["macro_injection_status"] == "probe_skipped"

    overview = pd.read_csv(Path(result["feed_files"]["overview"]))
    strategies = pd.read_csv(Path(result["feed_files"]["strategies"]))
    strategy_metrics = pd.read_csv(Path(result["feed_files"]["strategy_metrics"]))
    experiments = pd.read_csv(Path(result["feed_files"]["experiments"]))
    experiment_summary = pd.read_csv(Path(result["feed_files"]["experiment_summary"]))
    runs = pd.read_csv(Path(result["feed_files"]["runs"]))
    artifacts = pd.read_csv(Path(result["feed_files"]["artifacts"]))

    assert list(overview.columns) == ["section", "key", "value", "display_order"]
    assert list(strategies.columns) == [
        "strategy_id",
        "name",
        "track",
        "current_stage",
        "decision",
        "latest_result",
        "next_validation",
        "artifact_ref",
    ]
    assert list(strategy_metrics.columns) == [
        "strategy_id",
        "name",
        "track",
        "decision",
        "classification",
        "annualized_return",
        "max_drawdown",
        "sharpe_ratio",
        "calmar_ratio",
        "turnover",
        "win_rate",
        "artifact_ref",
    ]
    assert list(experiments.columns) == [
        "experiment_id",
        "timestamp",
        "mode",
        "strategy_candidate_id",
        "classification",
        "summary",
        "report_path",
    ]
    assert list(experiment_summary.columns) == ["classification", "count"]
    assert list(runs.columns) == ["run_id", "kind", "status", "started_at", "finished_at", "summary", "artifact_path"]
    assert list(artifacts.columns) == ["artifact_type", "name", "path", "notes"]
    assert set(strategies["strategy_id"]) == {"f1_elasticnet_v1", "baseline_limit_up"}

    workbook = load_workbook(workbook_path)
    assert tuple(workbook.sheetnames) == WORKSHEET_NAMES
    control = workbook["Control"]
    assert control["A1"].value == "Research Console"
    assert control["I12"].value == "Refresh Feed Pack"
    assert control["A17"].value == "Mainline vs challenger snapshot"
    assert control.freeze_panes == "A11"
    assert Path(result["action_scripts"]["refresh_data_pack"]).exists()
    assert Path(result["action_scripts"]["open_latest_console"]).exists()


def test_excel_export_is_repeatable(synthetic_project) -> None:
    project = synthetic_project["project"]
    repo_root = synthetic_project["paths"].root
    _seed_console_state(project, repo_root=repo_root)

    def fake_convert(source_xlsx: Path, target_xlsm: Path) -> None:
        shutil.copyfile(source_xlsx, target_xlsm)

    original_convert = excel_export_module._convert_xlsx_to_xlsm
    excel_export_module._convert_xlsx_to_xlsm = fake_convert
    try:
        first = run_excel_export(project, repo_root=repo_root, probe_vba=False)
        second = run_excel_export(project, repo_root=repo_root, probe_vba=False)
    finally:
        excel_export_module._convert_xlsx_to_xlsm = original_convert

    assert Path(first["feed_files"]["overview"]).read_text(encoding="utf-8-sig") == Path(
        second["feed_files"]["overview"]
    ).read_text(encoding="utf-8-sig")
    assert Path(second["workbook_path"]).exists()
