from __future__ import annotations

from quant_mvp.agent.subagent_controller import plan_subagents
from quant_mvp.agent.subagent_models import SubagentTaskProfile
from quant_mvp.memory.writeback import bootstrap_memory_files, record_agent_cycle


def test_runtime_artifacts_do_not_overwrite_tracked_memory(limit_up_project) -> None:
    project = limit_up_project["project"]
    paths = limit_up_project["paths"]
    bootstrap_memory_files(project)
    record_paths = record_agent_cycle(
        project,
        {
            "cycle_id": "demo",
            "timestamp": "2026-03-25T10:00:00+00:00",
            "plan": {"primary_hypothesis": "demo hypothesis"},
            "evaluation": {
                "passed": False,
                "promotion_decision": {"reasons": ["blocked"], "checks": {}},
            },
            "metadata": {"config_hash": "abc123"},
        },
    )

    assert record_paths["cycle_path"].is_file()
    assert record_paths["cycle_path"].parent == paths.runtime_cycles_dir
    assert paths.experiment_ledger_path.exists()
    assert paths.project_state_path.exists()
    assert not paths.memory_dir.joinpath("demo.json").exists()


def test_subagent_runtime_artifacts_stay_out_of_tracked_memory(limit_up_project) -> None:
    project = limit_up_project["project"]
    paths = limit_up_project["paths"]
    bootstrap_memory_files(project)
    result = plan_subagents(
        project=project,
        profile=SubagentTaskProfile(
            task_summary="Split future data and validation work once fixture data is ready",
            breadth=3,
            independence=0.9,
            file_overlap=0.15,
            validation_load=0.8,
            coordination_cost=0.2,
            risk_isolation=0.6,
            focus_tags=["data", "validation"],
        ),
        gate_mode="AUTO",
        activate=True,
    )

    assert result["created_ids"]
    for subagent_id in result["created_ids"]:
        assert paths.subagent_artifacts_dir.joinpath(subagent_id).is_dir()
    assert paths.subagent_registry_path.exists()
    assert not paths.memory_dir.joinpath("subagents", result["created_ids"][0]).exists()
