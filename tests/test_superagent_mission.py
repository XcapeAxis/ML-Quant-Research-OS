from __future__ import annotations

import json
from pathlib import Path

from quant_mvp.agent.memory import load_memory_context
from quant_mvp.superagent import mission_tick


def test_mission_tick_writes_dual_pool_and_branch_ledgers(limit_up_project) -> None:
    payload = mission_tick(
        project=limit_up_project["project"],
        dry_run=True,
        max_branches=3,
        config_path=limit_up_project["config_path"],
    )
    paths = limit_up_project["paths"]

    assert payload["mission_id"].startswith("mission-")
    assert Path(payload["mission_state_path"]).exists()
    assert Path(payload["branch_ledger_path"]).exists()
    assert Path(payload["evidence_ledger_path"]).exists()
    assert Path(payload["portfolio_status_path"]).exists()
    assert Path(payload["core_pool_snapshot_path"]).exists()
    assert payload["branches"]
    assert payload["proposals"]

    mission = json.loads(paths.mission_state_path.read_text(encoding="utf-8"))
    assert mission["mission_id"] == payload["mission_id"]
    assert mission["core_universe_snapshot_id"] == payload["core_pool_snapshot_id"]

    branch_lines = [line for line in paths.branch_ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    evidence_lines = [line for line in paths.evidence_ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(branch_lines) >= 1
    assert len(evidence_lines) >= 1

    latest_bundle = payload["evidence_records"][0]
    tasks_by_role = {item["role"]: item for item in latest_bundle["worker_tasks"]}
    assert tasks_by_role["scout"]["state"] == "verified"
    assert tasks_by_role["scout"]["subagent_id"]
    assert tasks_by_role["scout"]["artifact_refs"]
    assert tasks_by_role["scout"]["started_at"]
    assert tasks_by_role["scout"]["finished_at"]
    assert tasks_by_role["implementer"]["state"] == "verified"
    assert tasks_by_role["implementer"]["subagent_id"]
    assert tasks_by_role["implementer"]["artifact_refs"]
    assert tasks_by_role["implementer"]["started_at"]
    assert tasks_by_role["implementer"]["finished_at"]
    assert tasks_by_role["verifier"]["state"] == "queued"

    session = json.loads(paths.session_state_path.read_text(encoding="utf-8"))
    worker_subagents = [item for item in session["subagents"] if item.get("worker_task_id")]
    assert worker_subagents
    assert any(item["role"] == "scout" and item["status"] == "retired" for item in worker_subagents)
    assert any(item["role"] == "implementer" and item["status"] == "retired" for item in worker_subagents)
    ledger_text = paths.subagent_ledger_path.read_text(encoding="utf-8")
    assert '"action": "spawn_worker"' in ledger_text
    assert '"action": "retire"' in ledger_text

    context = load_memory_context(limit_up_project["project"])
    assert "[mission_state]" in context
    assert payload["mission_id"] in context
