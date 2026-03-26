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
    assert paths.strategy_board_path.exists()
    assert paths.strategy_candidates_dir.exists()
    assert paths.strategy_action_log_path.exists()
    assert paths.research_activity_path.exists()
    assert paths.idea_backlog_path.exists()
    assert paths.research_progress_path.exists()
    assert paths.experiment_ledger_path.exists()
    assert paths.subagent_registry_path.exists()
    assert paths.subagent_ledger_path.exists()
    assert paths.execution_queue_path.exists()
    assert paths.meta_dir.joinpath("PROJECT_STATE.md").exists() is False
    assert handoff["handoff_next_chat"] == paths.handoff_path
    assert "# 项目状态" in paths.project_state_path.read_text(encoding="utf-8")
    assert "当前主线策略" in paths.project_state_path.read_text(encoding="utf-8")
    assert "## 研究进度" in paths.project_state_path.read_text(encoding="utf-8")
    assert "# 研究记忆" in paths.research_memory_path.read_text(encoding="utf-8")
    assert "仍成立的策略假设" in paths.research_memory_path.read_text(encoding="utf-8")
    assert "## 研究进度" in paths.research_memory_path.read_text(encoding="utf-8")
    assert "# 最近验证快照" in paths.verify_last_path.read_text(encoding="utf-8")
    assert "当前主线策略" in paths.verify_last_path.read_text(encoding="utf-8")
    assert "## 研究进度" in paths.verify_last_path.read_text(encoding="utf-8")
    assert "# 执行队列" in paths.execution_queue_path.read_text(encoding="utf-8")
    assert "# 策略研究看板" in paths.strategy_board_path.read_text(encoding="utf-8")
