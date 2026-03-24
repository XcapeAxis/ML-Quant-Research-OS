from __future__ import annotations

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
