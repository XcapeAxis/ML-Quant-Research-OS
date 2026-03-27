from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from quant_mvp.config import load_config
from quant_mvp.data.cleaning import clean_project_bars
from quant_mvp.data.coverage_gap import (
    ANOMALOUS_STATE,
    COVERED_VALIDATED,
    MISSING_RAW_NEVER_ATTEMPTED,
    MISSING_RAW_TRANSIENT_FAILURE,
    VALIDATION_REJECTION,
    build_coverage_gap_ledger,
    save_bars_attempt_status,
)
from quant_mvp.db import delete_bars


ROOT = Path(__file__).resolve().parents[1]


def test_coverage_gap_ledger_classifies_symbol_states(limit_up_project) -> None:
    ctx = limit_up_project
    clean_project_bars(
        project=ctx["project"],
        db_path=ctx["db_path"],
        freq="1d",
        codes=ctx["universe_codes"],
        meta_dir=ctx["paths"].meta_dir,
        data_quality_cfg={"enabled": True},
        full_refresh=True,
    )
    codes = ctx["universe_codes"]
    delete_bars(ctx["db_path"], table_name="bars_clean", freq="1d", codes=[codes[1]])
    delete_bars(ctx["db_path"], table_name="bars", freq="1d", codes=[codes[2], codes[3], codes[4]])
    delete_bars(ctx["db_path"], table_name="bars_clean", freq="1d", codes=[codes[2], codes[3], codes[4]])
    save_bars_attempt_status(
        ctx["paths"].meta_dir,
        {
            codes[2]: {
                "status": "failed",
                "last_error": "proxy timeout",
                "attempt_count": 1,
            },
            codes[4]: {
                "status": "empty_response",
                "last_error": "",
                "attempt_count": 1,
            },
        },
    )

    cfg, _ = load_config(ctx["project"], config_path=ctx["config_path"])
    cfg["coverage_gap_policy"] = {
        "required_end_date": None,
        "eligibility_min_bars": 40,
        "auto_refreeze": True,
    }
    ledger = build_coverage_gap_ledger(
        project=ctx["project"],
        db_path=ctx["db_path"],
        freq="1d",
        universe_codes=ctx["universe_codes"],
        cfg=cfg,
        meta_dir=ctx["paths"].meta_dir,
        data_quality_cfg={"source_table": "bars", "clean_table": "bars_clean"},
    )

    by_symbol = {item.symbol: item for item in ledger.entries}
    assert by_symbol[codes[0]].classification == COVERED_VALIDATED
    assert by_symbol[codes[1]].classification == VALIDATION_REJECTION
    assert by_symbol[codes[2]].classification == MISSING_RAW_TRANSIENT_FAILURE
    assert by_symbol[codes[3]].classification == MISSING_RAW_NEVER_ATTEMPTED
    assert by_symbol[codes[4]].classification == ANOMALOUS_STATE


def test_coverage_gap_decision_prefers_expand_only_when_transient_recovery_can_clear_readiness(synthetic_project) -> None:
    ctx = synthetic_project
    clean_project_bars(
        project=ctx["project"],
        db_path=ctx["db_path"],
        freq="1d",
        codes=ctx["universe_codes"],
        meta_dir=ctx["paths"].meta_dir,
        data_quality_cfg={"enabled": True},
        full_refresh=True,
    )
    delete_bars(ctx["db_path"], table_name="bars", freq="1d", codes=ctx["universe_codes"][1:])
    delete_bars(ctx["db_path"], table_name="bars_clean", freq="1d", codes=ctx["universe_codes"][1:])
    save_bars_attempt_status(
        ctx["paths"].meta_dir,
        {
            ctx["universe_codes"][1]: {"status": "failed", "last_error": "timeout", "attempt_count": 1},
            ctx["universe_codes"][2]: {"status": "failed", "last_error": "proxy", "attempt_count": 1},
        },
    )
    cfg, _ = load_config(ctx["project"], config_path=ctx["config_path"])
    cfg["coverage_gap_policy"] = {"required_end_date": None, "eligibility_min_bars": 20}
    ledger = build_coverage_gap_ledger(
        project=ctx["project"],
        db_path=ctx["db_path"],
        freq="1d",
        universe_codes=ctx["universe_codes"],
        cfg=cfg,
        meta_dir=ctx["paths"].meta_dir,
        data_quality_cfg={"source_table": "bars", "clean_table": "bars_clean"},
    )
    assert ledger.decision.decision == "expand_bars"


def test_data_validate_auto_refreezes_to_validated_subset(limit_up_project) -> None:
    ctx = limit_up_project
    trailing_gap = ctx["universe_codes"][2:]
    delete_bars(ctx["db_path"], table_name="bars", freq="1d", codes=trailing_gap)
    delete_bars(ctx["db_path"], table_name="bars_clean", freq="1d", codes=trailing_gap)

    config_payload = json.loads(ctx["config_path"].read_text(encoding="utf-8"))
    config_payload["coverage_gap_policy"] = {
        "required_end_date": None,
        "eligibility_min_bars": 40,
        "auto_refreeze": True,
    }
    ctx["config_path"].write_text(json.dumps(config_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "quant_mvp",
            "data_validate",
            "--project",
            ctx["project"],
            "--config",
            str(ctx["config_path"]),
            "--full-refresh",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AssertionError(f"data_validate failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
    payload = json.loads(result.stdout)

    assert payload["coverage_gap_ledger"]["decision"]["decision"] == "refreeze"
    assert payload["refreeze_result"]["applied"] is True
    assert payload["research_readiness"]["ready"] is True

    current_universe = [line.strip() for line in ctx["paths"].universe_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(current_universe) == 2

    updated_config = json.loads(ctx["config_path"].read_text(encoding="utf-8"))
    assert updated_config["universe_size_target"] == 2

    manifest = json.loads((ctx["paths"].meta_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["coverage_gap_decision"]["decision"] == "refreeze"
    assert manifest["coverage_gap_decision"]["new_universe_size"] == 2

    project_state_text = ctx["paths"].project_state_path.read_text(encoding="utf-8")
    assert "stage0a" in project_state_text
    assert "refreeze" in project_state_text

    session_state = json.loads(ctx["paths"].session_state_path.read_text(encoding="utf-8"))
    assert session_state["stage0a_decision"]["new_universe_size"] == 2


def test_fixed_canonical_universe_does_not_auto_refreeze_even_when_coverage_is_short(synthetic_project) -> None:
    ctx = synthetic_project
    trailing_gap = ctx["universe_codes"][1:]
    delete_bars(ctx["db_path"], table_name="bars", freq="1d", codes=trailing_gap)
    delete_bars(ctx["db_path"], table_name="bars_clean", freq="1d", codes=trailing_gap)

    cfg, _ = load_config(ctx["project"], config_path=ctx["config_path"])
    cfg["coverage_gap_policy"] = {
        "required_end_date": None,
        "eligibility_min_bars": 20,
        "auto_refreeze": False,
        "allow_universe_shrink": False,
        "decision_style": "canonical_universe_fixed",
    }
    ledger = build_coverage_gap_ledger(
        project=ctx["project"],
        db_path=ctx["db_path"],
        freq="1d",
        universe_codes=ctx["universe_codes"],
        cfg=cfg,
        meta_dir=ctx["paths"].meta_dir,
        data_quality_cfg={"source_table": "bars", "clean_table": "bars_clean"},
    )

    assert ledger.decision.decision == "expand_bars_to_canonical_universe"
    assert ledger.decision.auto_refreeze_enabled is False
    assert "must not auto-shrink" in ledger.decision.decision_reason
