from __future__ import annotations

import json

from quant_mvp.agent.subagent_controller import archive_subagent, block_subagent, merge_subagent, plan_subagents, retire_subagent, sync_subagent_memory
from quant_mvp.agent.subagent_models import SubagentTaskProfile
from quant_mvp.memory.writeback import bootstrap_memory_files, load_machine_state


def test_subagent_lifecycle_and_append_only_ledger(limit_up_project) -> None:
    project = limit_up_project["project"]
    paths = limit_up_project["paths"]
    bootstrap_memory_files(project)

    plan_result = plan_subagents(
        project=project,
        profile=SubagentTaskProfile(
            task_summary="Split fixture data and validation work with low overlap",
            breadth=3,
            independence=0.85,
            file_overlap=0.1,
            validation_load=0.8,
            coordination_cost=0.2,
            risk_isolation=0.5,
            focus_tags=["data", "validation", "merge"],
        ),
        gate_mode="AUTO",
        activate=True,
    )
    created = plan_result["created_ids"]
    assert len(created) >= 2

    before = paths.subagent_ledger_path.read_text(encoding="utf-8").splitlines()
    block_subagent(project, subagent_id=created[0], summary="Waiting on a merge decision before closeout.")
    retire_subagent(project, subagent_id=created[0], summary="Work package was integrated into the main line.")
    merge_subagent(project, subagent_id=created[1], into_subagent_id=created[0], summary="Merge overlapping validation work.")
    archive_subagent(project, subagent_id=created[0], summary="Retired subagent can now be archived.")
    after = paths.subagent_ledger_path.read_text(encoding="utf-8").splitlines()

    assert len(after) >= len(before) + 4
    assert after[: len(before)] == before

    _, state = load_machine_state(project)
    statuses = {item["subagent_id"]: item["status"] for item in state["subagents"]}
    assert statuses[created[0]] == "archived"
    assert statuses[created[1]] == "merged"


def test_subagent_sync_updates_session_state_and_registry(limit_up_project) -> None:
    project = limit_up_project["project"]
    paths = limit_up_project["paths"]
    bootstrap_memory_files(project)
    plan_subagents(
        project=project,
        profile=SubagentTaskProfile(
            task_summary="Prepare future data and validation split",
            breadth=3,
            independence=0.9,
            file_overlap=0.15,
            validation_load=0.8,
            coordination_cost=0.25,
            risk_isolation=0.5,
            focus_tags=["data", "validation"],
        ),
        gate_mode="AUTO",
        activate=True,
    )

    sync_payload = sync_subagent_memory(project)
    session = json.loads(paths.session_state_path.read_text(encoding="utf-8"))
    handoff = paths.handoff_path.read_text(encoding="utf-8")
    migration = paths.migration_prompt_path.read_text(encoding="utf-8")

    assert sync_payload["gate_mode"] == "AUTO"
    assert session["subagent_gate_mode"] == "AUTO"
    assert session["subagents"]
    assert "## Subagent Status" in handoff
    assert "## Subagent Status" in migration
    assert paths.subagent_registry_path.exists()
