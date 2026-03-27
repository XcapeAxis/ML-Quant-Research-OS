from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from quant_mvp.coverage_recovery import (
    CoverageStageDecision,
    _update_session_state,
    _update_supporting_memory,
    assess_coverage_stage,
    build_coverage_recovery_frame,
    decide_baseline_status,
    render_coverage_recovery_checkpoint,
    select_incremental_backfill_codes,
)
from quant_mvp.data.cleaning import clean_project_bars
from quant_mvp.data.validate_flow import run_data_validate_flow
from quant_mvp.db import delete_bars


def test_st_is_only_a_label_and_not_removed_from_backfill_candidates(synthetic_project) -> None:
    ctx = synthetic_project
    security_master = pd.DataFrame(
        [
            {
                "code": "000001",
                "security_name": "平安银行",
                "exchange": "SZSE",
                "board": "mainboard",
                "is_st": False,
                "listing_date": "2000-01-01",
            },
            {
                "code": "000002",
                "security_name": "*ST样本",
                "exchange": "SSE",
                "board": "mainboard",
                "is_st": True,
                "listing_date": "2001-01-01",
            },
            {
                "code": "000003",
                "security_name": "新股样本",
                "exchange": "SSE",
                "board": "mainboard",
                "is_st": False,
                "listing_date": "2021-01-15",
            },
        ]
    )
    security_master.to_csv(ctx["paths"].meta_dir / "security_master.csv", index=False, encoding="utf-8")
    delete_bars(ctx["db_path"], table_name="bars", freq="1d", codes=["000002", "000003"])
    delete_bars(ctx["db_path"], table_name="bars_clean", freq="1d", codes=["000002", "000003"])

    frame = build_coverage_recovery_frame(
        project=ctx["project"],
        cfg={"freq": "1d", "end_date": "2020-12-31"},
        db_path=ctx["db_path"],
        meta_dir=ctx["paths"].meta_dir,
        universe_codes=ctx["universe_codes"],
    )

    st_row = frame.loc[frame["code"] == "000002"].iloc[0]
    post_cutoff_row = frame.loc[frame["code"] == "000003"].iloc[0]

    assert bool(st_row["is_st"]) is True
    assert bool(st_row["backfill_candidate"]) is True
    assert bool(post_cutoff_row["structural_no_bars"]) is True
    assert "000002" in select_incremental_backfill_codes(frame)
    assert "000003" not in select_incremental_backfill_codes(frame)


def test_assess_coverage_stage_stays_validation_ready_until_manual_promotion() -> None:
    pilot_summary = {
        "coverage_ratio": 0.80,
        "eligible_coverage_ratio": 0.92,
        "sse_coverage_ratio": 0.78,
        "szse_coverage_ratio": 0.82,
        "st_coverage_ratio": 0.79,
        "non_st_coverage_ratio": 0.80,
        "structural_no_bars_symbols": 20,
        "pipeline_location_counts": {"validated_covered": 100, "time_range_structural": 20},
    }
    pilot_stage = assess_coverage_stage(summary=pilot_summary, baseline_rerun_completed=False)
    assert pilot_stage.stage == "pilot"
    assert pilot_stage.baseline_reassessment_allowed is False

    validation_summary = {
        "coverage_ratio": 0.90,
        "eligible_coverage_ratio": 0.97,
        "sse_coverage_ratio": 0.88,
        "szse_coverage_ratio": 0.92,
        "st_coverage_ratio": 0.87,
        "non_st_coverage_ratio": 0.90,
        "structural_no_bars_symbols": 20,
        "pipeline_location_counts": {"validated_covered": 100, "time_range_structural": 20},
    }
    validation_stage = assess_coverage_stage(summary=validation_summary, baseline_rerun_completed=False)
    assert validation_stage.stage == "validation-ready"
    assert validation_stage.legacy_restore_allowed is False
    assert decide_baseline_status(stage=validation_stage.stage, baseline_rerun_completed=False) == "baseline_reset_pending"

    promoted_candidate_summary = {
        **validation_summary,
        "coverage_ratio": 0.97,
        "eligible_coverage_ratio": 0.99,
        "sse_coverage_ratio": 0.96,
        "szse_coverage_ratio": 0.98,
    }
    promoted_candidate_stage = assess_coverage_stage(summary=promoted_candidate_summary, baseline_rerun_completed=True)
    assert promoted_candidate_stage.stage == "validation-ready"
    assert promoted_candidate_stage.legacy_restore_allowed is False
    assert decide_baseline_status(stage=promoted_candidate_stage.stage, baseline_rerun_completed=True) == "baseline_validation_ready"


def test_render_checkpoint_contains_required_sections_and_chinese() -> None:
    text = render_coverage_recovery_checkpoint(
        {
            "system_line": "coverage 已提升",
            "strategy_line": "baseline 仍未恢复 active truth",
            "evidence_lines": ["关键命令结果"],
            "research_progress_rows": [
                {"dimension": "数据输入", "status": "validation-ready", "score": 3, "evidence": "coverage=90%"}
            ],
            "coverage_status_rows": [{"item": "Current readiness stage", "result": "validation-ready"}],
            "missingness_rows": [{"dimension": "沪 / 深主板", "observation": "差异已收敛", "conclusion": "非随机缺失已拆清"}],
            "strategy_action_rows": [
                {
                    "strategy": "baseline_limit_up",
                    "actor": "main",
                    "action": "最小重建",
                    "result": "baseline_validation_ready",
                    "decision_delta": "不恢复 legacy",
                }
            ],
            "next_recommendation": "继续重试 provider failure",
            "configured_gate": "AUTO",
            "effective_gate": "OFF",
        }
    )

    assert "Coverage status" in text
    assert "Missingness audit" in text
    assert "系统推进" in text
    assert "策略推进" in text


def test_memory_writeback_generates_reports_and_preserves_canonical_universe(synthetic_project) -> None:
    ctx = synthetic_project
    pre_summary = {
        "covered_symbols": 1,
        "universe_symbols": 3,
        "coverage_ratio": 1 / 3,
        "registry_present_symbols": 1,
    }
    post_summary = {
        "covered_symbols": 3,
        "universe_symbols": 3,
        "coverage_ratio": 1.0,
        "eligible_covered_symbols": 3,
        "eligible_universe_symbols": 3,
        "eligible_coverage_ratio": 1.0,
        "structural_no_bars_symbols": 0,
        "candidate_success_symbols": 2,
        "candidate_attempted_symbols": 2,
        "candidate_success_rate": 1.0,
        "st_total": 1,
        "st_covered": 1,
        "sse_total": 2,
        "szse_total": 1,
        "pipeline_location_counts": {"validated_covered": 3},
    }
    stage = CoverageStageDecision(
        stage="pilot",
        bias_explained=False,
        baseline_reassessment_allowed=False,
        legacy_restore_allowed=False,
        reasons=["coverage still too low"],
        thresholds={},
    )

    memory_paths = _update_supporting_memory(
        paths=ctx["paths"],
        pre_summary=pre_summary,
        post_summary=post_summary,
        stage_decision=stage,
        baseline_status="baseline_reset_pending",
        passed_commands=["python -m quant_mvp data_validate --project as_share_research_v1"],
        failed_commands=[],
    )
    session_path = _update_session_state(
        paths=ctx["paths"],
        generated_at="2026-03-27T04:00:00Z",
        pre_summary=pre_summary,
        post_summary=post_summary,
        stage_decision=stage,
        baseline_status="baseline_reset_pending",
        passed_commands=["python -m quant_mvp data_validate --project as_share_research_v1"],
        failed_commands=[],
    )

    assert Path(memory_paths["coverage_gap_report"]).exists()
    assert Path(memory_paths["missingness_bias_audit"]).exists()
    assert Path(memory_paths["backfill_plan"]).exists()

    session = json.loads(Path(session_path).read_text(encoding="utf-8"))
    assert session["canonical_universe_id"] == "cn_a_mainboard_all_v1"
    assert session["baseline_status"] == "baseline_reset_pending"
    assert session["readiness"]["stage"] == "pilot"

    board = Path(memory_paths["strategy_board"]).read_text(encoding="utf-8")
    assert "baseline_reset_pending" in board


def test_data_validate_can_refresh_artifacts_without_rebuilding_clean_table(synthetic_project) -> None:
    ctx = synthetic_project
    pd.DataFrame(
        [
            {
                "code": code,
                "security_name": f"样本{idx}",
                "exchange": "SZSE",
                "board": "mainboard",
                "is_st": False,
                "listing_date": "2000-01-01",
            }
            for idx, code in enumerate(ctx["universe_codes"], start=1)
        ]
    ).to_csv(ctx["paths"].meta_dir / "security_master.csv", index=False, encoding="utf-8")

    clean_project_bars(
        project=ctx["project"],
        db_path=ctx["db_path"],
        freq="1d",
        codes=ctx["universe_codes"],
        meta_dir=ctx["paths"].meta_dir,
        data_quality_cfg={"enabled": True},
        full_refresh=False,
    )

    result = run_data_validate_flow(
        project=ctx["project"],
        config_path=ctx["config_path"],
        full_refresh=False,
        skip_clean=True,
    )

    assert result["clean_stats"]["skipped_clean_rebuild"] is True
    assert result["report"]["covered_symbols"] == len(ctx["universe_codes"])
