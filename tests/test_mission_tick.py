from __future__ import annotations

import json

from quant_mvp.memory.research_activity import read_strategy_action_log
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

    strategy_actions = read_strategy_action_log(limit_up_project["paths"].strategy_action_log_path, limit=20)
    research_actions = [item for item in strategy_actions if item["actor_type"] == "subagent"]
    assert research_actions
    assert any(item["strategy_id"] in {branch["branch_id"] for branch in payload["branches"]} for item in research_actions)
    assert all(item["strategy_id"] != "__none__" for item in research_actions)
    assert all(item["artifact_refs"] for item in research_actions)

    ledger_entries = [
        json.loads(line)
        for line in limit_up_project["paths"].subagent_ledger_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    research_events = [item for item in ledger_entries if item.get("subagent_type") == "research"]
    assert research_events
    assert all(item.get("strategy_id") for item in research_events if item.get("action") == "spawn_worker")
