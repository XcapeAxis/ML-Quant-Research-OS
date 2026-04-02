from __future__ import annotations

import json

from quant_mvp.backend_adapters import (
    build_decision_record,
    build_failure_record,
    build_flow_bridge_adapter,
    build_local_backend_run,
)
from quant_mvp.experiment_graph import (
    build_dataset_snapshot,
    build_factor_candidates,
    build_feature_view,
    build_label_spec,
    build_model_candidate,
    build_opportunity_spec,
    build_regime_spec,
    build_universe_snapshot,
    new_experiment,
    read_experiment_record,
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
        factor_candidates=build_factor_candidates(
            cfg={"strategy_mode": "limit_up_screening", "top_pct_limit_up": 0.5, "limit_days_window": 60},
            branch_id="branch-demo",
            strategy_params={"variant": "baseline"},
        ),
        feature_view=build_feature_view(
            cfg={"strategy_mode": "limit_up_screening", "freq": "1d"},
            branch_id="branch-demo",
            branch_pool_snapshot_id="branch-pool-123",
        ),
        label_spec=build_label_spec(cfg={"rebalance_every": 5, "freq": "1d"}),
        model_candidate=build_model_candidate(
            cfg={"strategy_mode": "limit_up_screening"},
            branch_id="branch-demo",
            strategy_params={"variant": "baseline"},
        ),
        regime_spec=build_regime_spec(cfg={"freq": "1d"}, branch_id="branch-demo"),
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
    assert payload["factor_candidates"][0]["family"] == "event_seed"
    assert payload["feature_view"]["name"] == "legacy_event_panel_v1"
    assert payload["label_spec"]["target_name"] == "next_rebalance_excess_return"
    assert payload["model_candidate"]["is_online_adaptive"] is False
    assert payload["regime_spec"]["regime_transition_latency"] is None


def test_experiment_record_round_trip_preserves_backend_and_decision_objects(synthetic_project) -> None:
    ctx = synthetic_project
    universe = build_universe_snapshot(codes=ctx["universe_codes"], source_path=ctx["paths"].universe_path)
    dataset = build_dataset_snapshot(
        report={"coverage_ratio": 1.0, "covered_symbols": 6, "universe_symbols": 6, "validated_rows": 100},
        cfg={"freq": "1d", "data_provider": {"provider": "akshare"}, "strategy_mode": "limit_up_screening"},
        universe_snapshot=universe,
    )
    experiment = new_experiment(
        project=ctx["project"],
        experiment_id="backend-experiment",
        hypothesis="backend metadata should round-trip",
        mode="adapter_smoke",
        plan_steps=["submit_run"],
        success_criteria=["preserve backend and decision metadata"],
        universe_snapshot=universe,
        dataset_snapshot=dataset,
        opportunity_spec=build_opportunity_spec(cfg={"strategy_mode": "limit_up_screening"}, hypothesis="backend metadata should round-trip"),
        subagent_tasks=[],
        backend_adapter=build_flow_bridge_adapter(),
        backend_run=build_local_backend_run(
            workflow_template_id="adapter_smoke",
            status="running",
            parameter_overrides={"topk": 3},
            lineage_metadata={"source_experiment_id": "parent-experiment"},
        ),
    )
    experiment = update_experiment(
        experiment,
        status="failed",
        execution={"executed_steps": ["submit_run"]},
        decision_record=build_decision_record(
            decision="retry",
            summary="bridge import needs one more attempt",
            reasons=["synthetic bridge timeout"],
            next_action="retry after transport wiring",
        ),
        failure_record=build_failure_record(
            summary="bridge run failed",
            root_cause="adapter timeout while polling status",
            corrective_action="repair bridge transport",
        ),
    )

    path = write_experiment_record(experiment)
    payload = json.loads(path.read_text(encoding="utf-8"))
    round_trip = read_experiment_record(ctx["project"], "backend-experiment", repo_root=ctx["paths"].root)

    assert payload["backend_adapter"]["adapter_id"] == "flow_bridge"
    assert payload["backend_adapter"]["provider"] == "pandaai.quantflow"
    assert payload["backend_run"]["workflow_template_id"] == "adapter_smoke"
    assert payload["decision_record"]["decision"] == "retry"
    assert payload["failure_record"]["failure_class"] == "adapter_failure"
    assert round_trip.backend_adapter is not None
    assert round_trip.backend_adapter.adapter_name == "Flow Bridge"
    assert round_trip.backend_run is not None
    assert round_trip.backend_run.lineage_metadata["source_experiment_id"] == "parent-experiment"
    assert round_trip.decision_record is not None
    assert round_trip.decision_record.next_action == "retry after transport wiring"
    assert round_trip.failure_record is not None
    assert round_trip.failure_record.corrective_action == "repair bridge transport"


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
    assert report["key_evidence"]["adversarial_robustness"] is None
    assert report["key_evidence"]["regime_transition_drawdown"] is None
