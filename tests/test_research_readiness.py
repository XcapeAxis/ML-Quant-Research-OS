from __future__ import annotations

from pathlib import Path

from quant_mvp.data.cleaning import clean_project_bars
from quant_mvp.db import delete_bars
from quant_mvp.pools import build_core_universe_snapshot
from quant_mvp.promotion import promote_candidate


def test_promote_candidate_is_blocked_by_readiness_on_partial_coverage(limit_up_project) -> None:
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
    core_snapshot, _ = build_core_universe_snapshot(
        project=ctx["project"],
        config_path=ctx["config_path"],
    )
    assert core_snapshot.codes

    partial_gap = ctx["universe_codes"][2:]
    delete_bars(Path(ctx["db_path"]), table_name="bars", freq="1d", codes=partial_gap)
    delete_bars(Path(ctx["db_path"]), table_name="bars_clean", freq="1d", codes=partial_gap)

    result = promote_candidate(ctx["project"], config_path=ctx["config_path"])
    decision = result["decision"]

    assert decision["promotable"] is False
    assert decision["checks"]["research_readiness"]["stage"] == "pilot"
    assert any("Coverage ratio" in reason for reason in decision["reasons"])
    assert result["strategy_failure_report_json"].endswith("STRATEGY_FAILURE_REPORT.json")
    assert result["strategy_failure_report_md"].endswith("STRATEGY_FAILURE_REPORT.md")
    assert result["research_universe_source"] == core_snapshot.snapshot_id
