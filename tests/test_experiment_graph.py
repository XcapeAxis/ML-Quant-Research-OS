from __future__ import annotations

import json

from quant_mvp.experiment_graph import (
    build_dataset_snapshot,
    build_opportunity_spec,
    build_universe_snapshot,
    new_experiment,
    update_experiment,
    write_experiment_record,
)
from quant_mvp.strategy_diagnostics import build_strategy_failure_report


def test_snapshot_hashes_are_stable_for_same_inputs(synthetic_project) -> None:
    ctx = synthetic_project
    codes = ctx["universe_codes"]
    universe_a = build_universe_snapshot(codes=codes, source_path=ctx["paths"].universe_path)
    universe_b = build_universe_snapshot(codes=reversed(codes), source_path=ctx["paths"].universe_path)
    report = {
        "coverage_ratio": 1.0,
        "covered_symbols": len(codes),
        "universe_symbols": len(codes),
        "validated_rows": 100,
    }
    dataset_a = build_dataset_snapshot(report=report, cfg={"freq": "1d", "data_provider": {"provider": "akshare"}}, universe_snapshot=universe_a)
    dataset_b = build_dataset_snapshot(report=report, cfg={"freq": "1d", "data_provider": {"provider": "akshare"}}, universe_snapshot=universe_b)

    assert universe_a.hash == universe_b.hash
    assert dataset_a.hash == dataset_b.hash


def test_experiment_record_round_trip_writes_project_level_json(synthetic_project) -> None:
    ctx = synthetic_project
    universe = build_universe_snapshot(codes=ctx["universe_codes"], source_path=ctx["paths"].universe_path)
    dataset = build_dataset_snapshot(
        report={"coverage_ratio": 1.0, "covered_symbols": 6, "universe_symbols": 6, "validated_rows": 100},
        cfg={"freq": "1d", "data_provider": {"provider": "akshare"}, "strategy_mode": "limit_up_screening"},
        universe_snapshot=universe,
    )
    experiment = new_experiment(
        project=ctx["project"],
        experiment_id="demo-experiment",
        hypothesis="demo hypothesis",
        mode="dry_run",
        plan_steps=["research_audit"],
        success_criteria=["write artifacts"],
        universe_snapshot=universe,
        dataset_snapshot=dataset,
        opportunity_spec=build_opportunity_spec(cfg={"strategy_mode": "limit_up_screening"}, hypothesis="demo hypothesis"),
        subagent_tasks=[],
        mission_id="mission-demo",
        branch_id="branch-demo",
        core_universe_snapshot_id="core-123",
        branch_pool_snapshot_id="branch-pool-123",
        opportunity_generator_id="limit_up_reaccumulation",
        strategy_candidate_id="candidate-demo",
    )
    experiment = update_experiment(experiment, status="executed", execution={"executed_steps": ["research_audit"], "outputs": {}})
    path = write_experiment_record(experiment)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert path.parent == ctx["paths"].experiments_dir
    assert payload["experiment_id"] == "demo-experiment"
    assert payload["status"] == "executed"
    assert payload["dataset_snapshot"]["hash"] == dataset.hash
    assert payload["mission_id"] == "mission-demo"
    assert payload["branch_id"] == "branch-demo"
    assert payload["strategy_candidate_id"] == "candidate-demo"


def test_strategy_failure_report_prioritizes_drawdown_and_risk_themes() -> None:
    report = build_strategy_failure_report(
        project="demo",
        hypothesis="demo hypothesis",
        decision={
            "promotable": False,
            "reasons": ["Max drawdown 83.38% exceeds 30.00%.", "Leakage check failed."],
            "checks": {
                "research_readiness": {"ready": True, "stage": "ready"},
                "max_drawdown": 0.8338,
                "leakage_passed": False,
            },
        },
    )

    assert report["classification"] == "strategy_quality_failure"
    assert report["primary_blockers"][0].startswith("Max drawdown")
    assert any("drawdown" in item.lower() for item in report["next_experiment_themes"])
