from __future__ import annotations

import json

from quant_mvp.agent.subagent_controller import reconcile_loop_subagents, register_worker_subagent
from quant_mvp.memory.writeback import bootstrap_memory_files, generate_handoff, load_machine_state
from quant_mvp.memory.strategy_visibility import REQUIRED_CANDIDATE_FIELDS


def test_strategy_board_and_seed_candidate_are_written(limit_up_project) -> None:
    project = limit_up_project["project"]
    paths = limit_up_project["paths"]

    bootstrap_memory_files(project)
    generate_handoff(project)
    _, state = load_machine_state(project)

    assert paths.strategy_board_path.exists()
    assert paths.strategy_candidates_dir.exists()
    assert paths.strategy_action_log_path.exists()
    assert paths.research_activity_path.exists()
    assert paths.idea_backlog_path.exists()
    assert state["strategy_candidates"]

    board = paths.strategy_board_path.read_text(encoding="utf-8")
    assert "Primary track" in board
    assert "Secondary track" in board
    assert "Blocked" in board
    assert "Rejected / Killed" in board
    assert "Promoted" in board
    assert "strategy_action_log" in board
    assert "idea_backlog" in board

    candidate = state["strategy_candidates"][0]
    for field in REQUIRED_CANDIDATE_FIELDS:
        assert field in candidate

    card_path = paths.strategy_candidates_dir / f"{candidate['strategy_id']}.md"
    assert card_path.exists()
    card = card_path.read_text(encoding="utf-8")
    for field in REQUIRED_CANDIDATE_FIELDS:
        assert f"- {field}:" in card

    handoff = paths.handoff_path.read_text(encoding="utf-8")
    migration = paths.migration_prompt_path.read_text(encoding="utf-8")
    assert candidate["strategy_id"] in handoff
    assert "primary_strategies" in migration


def test_strategy_subagents_are_bound_and_infra_subagents_are_not(limit_up_project) -> None:
    project = limit_up_project["project"]
    paths = limit_up_project["paths"]
    bootstrap_memory_files(project)

    register_worker_subagent(
        project=project,
        role="scout",
        summary="baseline_limit_up candidate evidence refresh",
        mission_id="mission-test",
        branch_id="baseline_limit_up",
        candidate_id="candidate::baseline_limit_up",
        worker_task_id="baseline-limit-up-scout",
        expected_artifacts=["artifact"],
        allowed_paths=["tests"],
    )
    reconcile_loop_subagents(
        project=project,
        desired_roles=["data_steward"],
        should_expand=True,
        summary="recover prerequisite daily-bar visibility",
    )

    _, state = load_machine_state(project)
    records = list(state["subagents"])
    research = next(item for item in records if item.get("subagent_type") == "research")
    infrastructure = next(item for item in records if item.get("subagent_type") == "infrastructure")

    assert research["strategy_id"] == "baseline_limit_up"
    assert infrastructure.get("strategy_id") in {None, ""}
    assert infrastructure.get("blocker_scope")

    registry = paths.subagent_registry_path.read_text(encoding="utf-8")
    assert "configured gate:" in registry
    assert "effective gate this run:" in registry
    assert "策略研究型" in registry
    assert "基础设施型" in registry
    assert "strategy_id: baseline_limit_up" in registry
    assert "服务 blocker / 前提:" in registry
    assert "这不是直接研究策略:" in registry

    ledger_entries = [
        json.loads(line)
        for line in paths.subagent_ledger_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    research_events = [item for item in ledger_entries if item.get("subagent_type") == "research"]
    infra_events = [item for item in ledger_entries if item.get("subagent_type") == "infrastructure"]

    assert any(item.get("strategy_id") == "baseline_limit_up" for item in research_events)
    assert all(not item.get("strategy_id") for item in infra_events if item.get("action") != "plan")
