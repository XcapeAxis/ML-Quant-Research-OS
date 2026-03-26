from __future__ import annotations

from quant_mvp.pools import explain_pool_membership, load_latest_branch_pool_snapshot, load_latest_core_pool_snapshot
from quant_mvp.superagent import mission_status, mission_tick


def test_mission_tick_generates_dual_pool_artifacts(limit_up_project) -> None:
    payload = mission_tick(
        project=limit_up_project["project"],
        dry_run=True,
        config_path=limit_up_project["config_path"],
        max_branches=3,
    )

    assert payload["mission_id"]
    assert payload["core_universe_snapshot_id"]
    assert payload["core_universe_size"] > 0
    assert len(payload["branches"]) == 3
    assert payload["worker_task_count"] == 9

    state = mission_status(project=limit_up_project["project"])
    assert state["mission_state"]["mission_id"] == payload["mission_id"]

    core_snapshot = load_latest_core_pool_snapshot(limit_up_project["project"])
    branch_snapshot = load_latest_branch_pool_snapshot(limit_up_project["project"], branch_id="baseline_limit_up")
    assert core_snapshot is not None
    assert branch_snapshot is not None

    explanation = explain_pool_membership(
        project=limit_up_project["project"],
        code=limit_up_project["universe_codes"][0],
        kind="core",
    )
    assert explanation.kind == "core"
    assert explanation.snapshot_id == core_snapshot.snapshot_id
