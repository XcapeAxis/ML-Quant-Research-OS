from __future__ import annotations

from quant_mvp.memory.writeback import bootstrap_memory_files, generate_handoff, sync_project_state


def test_manifest_and_memory_writeback(limit_up_project) -> None:
    project = limit_up_project["project"]
    paths = limit_up_project["paths"]
    files = bootstrap_memory_files(project)
    state_path = sync_project_state(
        project,
        {
            "current_task": "Keep tracked memory and runtime artifacts separated.",
            "current_phase": "Memory migration",
            "current_blocker": "none",
            "current_capability_boundary": "Tracked memory writes are working in tests.",
            "next_priority_action": "Run handoff generation.",
            "last_verified_capability": "Tracked memory bootstrap created the required files.",
            "last_failed_capability": "none",
        },
    )
    handoff = generate_handoff(project)

    assert files["memory_dir"] == paths.memory_dir
    assert state_path == paths.project_state_path
    assert paths.project_state_path.exists()
    assert paths.handoff_path.exists()
    assert paths.migration_prompt_path.exists()
    assert paths.experiment_ledger_path.exists()
    assert paths.subagent_registry_path.exists()
    assert paths.subagent_ledger_path.exists()
    assert paths.meta_dir.joinpath("PROJECT_STATE.md").exists() is False
    assert handoff["handoff_next_chat"] == paths.handoff_path
