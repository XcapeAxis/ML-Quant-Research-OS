from __future__ import annotations

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
    assert state["strategy_candidates"]
    board = paths.strategy_board_path.read_text(encoding="utf-8")
    assert "## 1. 主线策略（Primary track）" in board
    assert "## 2. 次级策略（Secondary track）" in board
    assert "## 3. Blocked 策略" in board
    assert "## 4. Rejected / Killed 策略" in board
    assert "## 5. Promoted 策略" in board
    assert "## 6. 当前研究总判断" in board
    assert "当前研究主线" in board

    candidate = state["strategy_candidates"][0]
    for field in REQUIRED_CANDIDATE_FIELDS:
        assert field in candidate

    card_path = paths.strategy_candidates_dir / f"{candidate['strategy_id']}.md"
    assert card_path.exists()
    card = card_path.read_text(encoding="utf-8")
    for field in REQUIRED_CANDIDATE_FIELDS:
        assert f"- {field}:" in card or f"- {field}：" in card

    handoff = paths.handoff_path.read_text(encoding="utf-8")
    migration = paths.migration_prompt_path.read_text(encoding="utf-8")
    assert "当前主线策略" in handoff
    assert "primary_strategies" in migration


def test_strategy_subagents_are_bound_and_infra_subagents_are_not(limit_up_project) -> None:
    project = limit_up_project["project"]
    paths = limit_up_project["paths"]
    bootstrap_memory_files(project)

    register_worker_subagent(
        project=project,
        role="scout",
        summary="为 baseline_limit_up 补一轮候选与证据整理。",
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
        summary="恢复研究所需日频 bars 与输入前提。",
    )

    _, state = load_machine_state(project)
    records = list(state["subagents"])
    research = next(item for item in records if item.get("subagent_type") == "research")
    infrastructure = next(item for item in records if item.get("subagent_type") == "infrastructure")

    assert research["strategy_id"] == "baseline_limit_up"
    assert infrastructure.get("strategy_id") in {None, ""}
    assert infrastructure.get("blocker_scope")

    registry = paths.subagent_registry_path.read_text(encoding="utf-8")
    assert "类型: 策略研究型" in registry
    assert "strategy_id: baseline_limit_up" in registry
    assert "类型: 基础设施型" in registry
    assert "服务 blocker / 前提" in registry
