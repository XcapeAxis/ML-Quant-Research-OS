from __future__ import annotations

from quant_mvp.data.cleaning import clean_project_bars
from quant_mvp.db import delete_bars

from quant_mvp.agent.runner import run_agent_cycle


def test_agent_cycle_dry_run(limit_up_project) -> None:
    clean_project_bars(
        project=limit_up_project["project"],
        db_path=limit_up_project["db_path"],
        freq="1d",
        codes=limit_up_project["universe_codes"],
        meta_dir=limit_up_project["paths"].meta_dir,
        data_quality_cfg={"enabled": True},
        full_refresh=True,
    )
    payload = run_agent_cycle(
        project=limit_up_project["project"],
        dry_run=True,
        config_path=limit_up_project["config_path"],
    )
    paths = limit_up_project["paths"]

    assert payload["metadata"]["dry_run"] is True
    assert paths.experiment_ledger_path.exists()
    assert paths.hypothesis_queue_path.exists()
    assert paths.project_state_path.exists()
    assert paths.runtime_cycles_dir.exists()
    assert payload["evaluation"]["promotion_decision"]["checks"]["baselines_status"] == "pass"
    assert payload["evaluation"]["promotion_decision"]["baselines"]["benchmark_available"] is True


def test_agent_cycle_dry_run_blocks_on_research_readiness_before_strategy_metrics(limit_up_project) -> None:
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
    delete_bars(ctx["db_path"], table_name="bars", freq="1d", codes=ctx["universe_codes"][2:])
    delete_bars(ctx["db_path"], table_name="bars_clean", freq="1d", codes=ctx["universe_codes"][2:])

    payload = run_agent_cycle(
        project=ctx["project"],
        dry_run=True,
        config_path=ctx["config_path"],
    )

    decision = payload["evaluation"]["promotion_decision"]
    assert decision["promotable"] is False
    assert any("Coverage ratio" in reason for reason in decision["reasons"])
    assert decision["checks"]["research_readiness"]["ready"] is False
    assert decision["checks"]["research_readiness"]["stage"] == "pilot"
