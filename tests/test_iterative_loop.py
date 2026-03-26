from __future__ import annotations

import json

import pytest

import quant_mvp.agent.iterative_loop as loop_module
from quant_mvp.agent.iterative_loop import LoopAction, LoopConfig, RepoTruth, VerificationResult, render_iterative_checkpoint, run_iterative_loop
from quant_mvp.agent.subagent_controller import register_worker_subagent
from quant_mvp.memory.writeback import load_machine_state, save_machine_state


def _truth(
    *,
    blocker: str,
    blocker_key: str,
    direction: str,
    next_action: str = "next action",
    data_ready: bool | None = None,
    worktree_safe: bool = True,
    context_clear: bool = True,
    failure_scope_score: int = 1,
    state_snapshot: dict | None = None,
) -> RepoTruth:
    return RepoTruth(
        current_task="bounded automation loop",
        current_phase="loop test",
        current_blocker=blocker,
        blocker_key=blocker_key,
        direction=direction,
        context_clear=context_clear,
        worktree_safe=worktree_safe,
        risk_level="low",
        data_ready=data_ready,
        next_priority_action=next_action,
        current_capability_boundary="test boundary",
        last_verified_capability="test verified",
        last_failed_capability="test failed",
        failure_scope_score=failure_scope_score,
        sources=["test"],
        state_snapshot=state_snapshot or {},
    )


class _SequenceDriver:
    def __init__(
        self,
        *,
        truths: list[tuple[RepoTruth, RepoTruth]],
        verifications: list[VerificationResult],
        action_name: str = "agent_cycle_dry_run",
        action_names: list[str] | None = None,
    ):
        self.truths = truths
        self.verifications = verifications
        self.action_name = action_name
        self.action_names = list(action_names or [])
        self.iteration = 0
        self.scan_index = 0

    def rescan(self, *, project: str, repo_root=None, config_path=None) -> RepoTruth:
        del project, repo_root, config_path
        pair = self.truths[min(self.scan_index // 2, len(self.truths) - 1)]
        truth = pair[0] if self.scan_index % 2 == 0 else pair[1]
        self.scan_index += 1
        return truth

    def choose_action(self, *, truth: RepoTruth, history: list[dict], config: LoopConfig) -> LoopAction | None:
        del config
        name = self.action_name
        if self.action_names:
            name = self.action_names[min(len(history), len(self.action_names) - 1)]
        return LoopAction(
            name=name,
            rationale=f"test action for {truth.blocker_key}",
            expected_outcome="test outcome",
        )

    def execute(self, *, project: str, action: LoopAction, repo_root=None, config_path=None) -> dict:
        del project, repo_root, config_path
        self.iteration += 1
        return {"artifact": f"{action.name}-{self.iteration}.json"}

    def verify(self, *, action: LoopAction, before: RepoTruth, after: RepoTruth, execution: dict, history: list[dict], config: LoopConfig) -> VerificationResult:
        del action, before, after, execution, config
        return self.verifications[len(history)]


def test_iterative_run_stops_at_target_iterations_and_writes_summary(limit_up_project) -> None:
    driver = _SequenceDriver(
        truths=[
            (
                _truth(blocker="data gap", blocker_key="data_inputs", direction="input_recovery", data_ready=False),
                _truth(blocker="data gap shrinking", blocker_key="data_inputs", direction="input_recovery", data_ready=False),
            ),
            (
                _truth(blocker="data gap shrinking", blocker_key="data_inputs", direction="input_recovery", data_ready=False),
                _truth(blocker="diagnostics ready", blocker_key="none", direction="verification", data_ready=True),
            ),
            (
                _truth(blocker="drawdown", blocker_key="max_drawdown", direction="strategy_diagnostics", data_ready=True),
                _truth(blocker="drawdown clarified", blocker_key="max_drawdown", direction="strategy_diagnostics", data_ready=True),
            ),
        ],
        verifications=[
            VerificationResult(classification="blocker_clarified", summary="iteration 1", verified_progress=False, new_information=True, allow_extra_iteration=True, next_recommendation="validate again"),
            VerificationResult(classification="direction_corrected", summary="iteration 2", verified_progress=True, new_information=True, direction_changed=True, allow_extra_iteration=True, next_recommendation="run diagnostics"),
            VerificationResult(classification="verified_progress", summary="iteration 3", verified_progress=True, new_information=True, allow_extra_iteration=False, next_recommendation="stop after target"),
        ],
    )

    result = run_iterative_loop(
        project=limit_up_project["project"],
        target_iterations=3,
        max_iterations=5,
        driver=driver,
    )

    session = json.loads(limit_up_project["paths"].session_state_path.read_text(encoding="utf-8"))
    handoff = limit_up_project["paths"].handoff_path.read_text(encoding="utf-8")
    migration = limit_up_project["paths"].migration_prompt_path.read_text(encoding="utf-8")

    assert result["iteration_count"] == 3
    assert result["stop_reason"] == "target_iterations_reached"
    assert session["iterative_loop"]["iteration_count"] == 3
    assert session["iterative_loop"]["stop_reason"] == "target_iterations_reached"
    assert session["iterative_loop"]["workflow_mode"] == "campaign"
    assert session["iterative_loop"]["direction_change"] is True
    assert session["execution_queue"]
    assert "## 最近一次高阶迭代" in handoff
    assert "## 研究进度" in handoff
    assert "## 最近一次高阶迭代" in migration
    assert "## 研究进度" in migration
    assert limit_up_project["paths"].execution_queue_path.exists()
    assert "执行队列" in limit_up_project["paths"].execution_queue_path.read_text(encoding="utf-8")


def test_iterative_run_stops_after_two_iterations_without_effective_progress(limit_up_project) -> None:
    driver = _SequenceDriver(
        truths=[
            (
                _truth(blocker="drawdown", blocker_key="max_drawdown", direction="strategy_diagnostics", data_ready=True),
                _truth(blocker="drawdown", blocker_key="max_drawdown", direction="strategy_diagnostics", data_ready=True),
            ),
            (
                _truth(blocker="drawdown", blocker_key="max_drawdown", direction="strategy_diagnostics", data_ready=True),
                _truth(blocker="drawdown", blocker_key="max_drawdown", direction="strategy_diagnostics", data_ready=True),
            ),
        ],
        verifications=[
            VerificationResult(classification="no_meaningful_progress", summary="stalled", verified_progress=False, new_information=False, next_recommendation="stop"),
            VerificationResult(classification="no_meaningful_progress", summary="still stalled", verified_progress=False, new_information=False, next_recommendation="stop"),
        ],
    )

    result = run_iterative_loop(project=limit_up_project["project"], driver=driver, target_iterations=4, max_iterations=4)

    assert result["iteration_count"] == 2
    assert result["stop_reason"] == "no_effective_progress_twice"
    assert result["postmortem_required"] is True


def test_iterative_run_stops_when_failure_scope_expands(limit_up_project) -> None:
    driver = _SequenceDriver(
        truths=[
            (
                _truth(blocker="baseline issue", blocker_key="baseline_integrity", direction="strategy_diagnostics", data_ready=True, failure_scope_score=1),
                _truth(blocker="baseline plus leakage", blocker_key="leakage", direction="strategy_diagnostics", data_ready=True, failure_scope_score=3),
            ),
        ],
        verifications=[
            VerificationResult(classification="direction_corrected", summary="scope expanded", verified_progress=False, new_information=True, failure_scope_expanded=True, next_recommendation="stop"),
        ],
    )

    result = run_iterative_loop(project=limit_up_project["project"], driver=driver)
    _, state = load_machine_state(limit_up_project["project"])

    assert result["stop_reason"] == "verification_failed_scope_expanded"
    assert state["research_progress"]["this_run_delta"] == "regressed"


def test_iterative_run_stops_when_clarify_only_iterations_are_overused(limit_up_project) -> None:
    driver = _SequenceDriver(
        truths=[
            (
                _truth(blocker="data gap", blocker_key="data_inputs", direction="input_recovery", data_ready=False),
                _truth(blocker="data gap narrowed", blocker_key="data_inputs", direction="input_recovery", data_ready=False),
            ),
            (
                _truth(blocker="data gap narrowed", blocker_key="data_inputs", direction="input_recovery", data_ready=False),
                _truth(blocker="data gap still narrowed", blocker_key="data_inputs", direction="input_recovery", data_ready=False),
            ),
        ],
        verifications=[
            VerificationResult(classification="blocker_clarified", summary="first clarification", verified_progress=False, new_information=True, next_recommendation="recover inputs"),
            VerificationResult(classification="blocker_clarified", summary="second clarification", verified_progress=False, new_information=True, next_recommendation="recover inputs"),
        ],
        action_name="data_validate",
    )

    result = run_iterative_loop(
        project=limit_up_project["project"],
        driver=driver,
        target_iterations=4,
        max_iterations=4,
        clarify_only_limit=1,
    )

    assert result["iteration_count"] == 2
    assert result["clarify_only_iterations"] == 2
    assert result["substantive_action_count"] == 0
    assert result["stop_reason"] == "clarify_only_limit_reached"


def test_iterative_run_escalates_repeated_blocker(limit_up_project) -> None:
    project = limit_up_project["project"]
    _, state = load_machine_state(project)
    for item in state["execution_queue"]:
        item["selected_count"] = 1
        item["last_iteration"] = 1
        item["current_status"] = "advanced"
    save_machine_state(project, state)

    stagnant_before = _truth(blocker="drawdown", blocker_key="max_drawdown", direction="strategy_diagnostics", data_ready=True)
    stagnant_after = _truth(blocker="drawdown clarified", blocker_key="max_drawdown", direction="strategy_diagnostics", data_ready=True)
    driver = _SequenceDriver(
        truths=[(stagnant_before, stagnant_after), (stagnant_before, stagnant_after), (stagnant_before, stagnant_after)],
        verifications=[
            VerificationResult(classification="blocker_clarified", summary="first", verified_progress=False, new_information=True, next_recommendation="root-cause"),
            VerificationResult(classification="blocker_clarified", summary="second", verified_progress=False, new_information=True, next_recommendation="root-cause"),
            VerificationResult(classification="blocker_clarified", summary="third", verified_progress=False, new_information=True, next_recommendation="stop honestly"),
        ],
    )

    result = run_iterative_loop(
        project=project,
        target_iterations=5,
        max_iterations=5,
        clarify_only_limit=3,
        driver=driver,
    )
    session = json.loads(limit_up_project["paths"].session_state_path.read_text(encoding="utf-8"))

    assert result["stop_reason"] == "low_roi_repeated_blocker"
    assert result["blocker_escalation"] is True
    assert session["iterative_loop"]["blocker_escalation"] is True


def test_iterative_run_requests_root_cause_on_second_blocker_occurrence(limit_up_project) -> None:
    project = limit_up_project["project"]
    _, state = load_machine_state(project)
    blocker_history = {
        "max_drawdown": {
            "count": 1,
            "last_seen": "2026-03-25T00:00:00+00:00",
            "last_stop_reason": "no_verified_progress",
            "escalated": False,
        },
    }
    state["iterative_loop"]["blocker_history"] = blocker_history
    save_machine_state(project, state)

    driver = _SequenceDriver(
        truths=[
            (
                _truth(
                    blocker="drawdown",
                    blocker_key="max_drawdown",
                    direction="strategy_diagnostics",
                    data_ready=True,
                    state_snapshot={"iterative_loop": {"blocker_history": blocker_history}},
                ),
                _truth(
                    blocker="drawdown narrowed",
                    blocker_key="max_drawdown",
                    direction="strategy_diagnostics",
                    data_ready=True,
                    state_snapshot={"iterative_loop": {"blocker_history": blocker_history}},
                ),
            ),
        ],
        verifications=[
            VerificationResult(classification="blocker_clarified", summary="second sighting", verified_progress=False, new_information=True, next_recommendation="run diagnostics"),
        ],
    )

    result = run_iterative_loop(project=project, target_iterations=1, max_iterations=1, driver=driver)
    session = json.loads(limit_up_project["paths"].session_state_path.read_text(encoding="utf-8"))

    assert result["blocker_repeat_count"] == 2
    assert result["historical_blocker_count"] == 1
    assert "root-cause diagnosis" in result["next_recommendation"]
    assert session["iterative_loop"]["blocker_repeat_count"] == 2


def test_iterative_run_escalates_repeated_blocker_across_runs(limit_up_project) -> None:
    project = limit_up_project["project"]
    _, state = load_machine_state(project)
    blocker_history = {
        "max_drawdown": {
            "count": 2,
            "last_seen": "2026-03-25T00:00:00+00:00",
            "last_stop_reason": "no_verified_progress",
            "escalated": False,
        },
    }
    state["iterative_loop"]["blocker_history"] = blocker_history
    for item in state["execution_queue"]:
        item["selected_count"] = 1
        item["last_iteration"] = 1
        item["current_status"] = "advanced"
    save_machine_state(project, state)

    driver = _SequenceDriver(
        truths=[
            (
                _truth(
                    blocker="drawdown",
                    blocker_key="max_drawdown",
                    direction="strategy_diagnostics",
                    data_ready=True,
                    state_snapshot={"iterative_loop": {"blocker_history": blocker_history}},
                ),
                _truth(
                    blocker="drawdown unchanged",
                    blocker_key="max_drawdown",
                    direction="strategy_diagnostics",
                    data_ready=True,
                    state_snapshot={"iterative_loop": {"blocker_history": blocker_history}},
                ),
            ),
        ],
        verifications=[
            VerificationResult(classification="blocker_clarified", summary="third sighting", verified_progress=False, new_information=True, next_recommendation="run diagnostics"),
        ],
    )

    result = run_iterative_loop(project=project, driver=driver, target_iterations=1, max_iterations=1, clarify_only_limit=3)
    session = json.loads(limit_up_project["paths"].session_state_path.read_text(encoding="utf-8"))

    assert result["stop_reason"] == "low_roi_repeated_blocker"
    assert result["blocker_repeat_count"] == 3
    assert result["blocker_escalation"] is True
    assert "Escalated blocker" in result["next_recommendation"]
    assert session["iterative_loop"]["blocker_escalation"] is True


def test_repeated_blocker_uses_untried_followups_before_low_roi_stop(limit_up_project) -> None:
    project = limit_up_project["project"]
    _, state = load_machine_state(project)
    state["iterative_loop"]["blocker_history"] = {
        "max_drawdown": {
            "count": 4,
            "last_seen": "2026-03-25T00:00:00+00:00",
            "last_stop_reason": "low_roi_repeated_blocker",
            "escalated": True,
        },
    }
    for item in state["execution_queue"]:
        if item["task_id"] == "recover_daily_bars":
            item["current_status"] = "done"
            item["selected_count"] = 1
        elif item["task_id"] == "refresh_promotion_boundary":
            item["current_status"] = "advanced"
            item["selected_count"] = 1
            item["last_iteration"] = 1
            item["last_classification"] = "blocker_clarified"
        else:
            item["current_status"] = "queued"
            item["selected_count"] = 0
            item["last_iteration"] = 0
            item["last_classification"] = ""
    save_machine_state(project, state)

    repeated_snapshot = {"iterative_loop": {"blocker_history": state["iterative_loop"]["blocker_history"]}}
    driver = _SequenceDriver(
        truths=[
            (
                _truth(
                    blocker="drawdown",
                    blocker_key="max_drawdown",
                    direction="strategy_diagnostics",
                    data_ready=True,
                    state_snapshot=repeated_snapshot,
                ),
                _truth(
                    blocker="drawdown narrowed",
                    blocker_key="max_drawdown",
                    direction="strategy_diagnostics",
                    data_ready=True,
                    state_snapshot=repeated_snapshot,
                ),
            ),
            (
                _truth(
                    blocker="drawdown narrowed",
                    blocker_key="max_drawdown",
                    direction="strategy_diagnostics",
                    data_ready=True,
                    state_snapshot=repeated_snapshot,
                ),
                _truth(
                    blocker="drawdown still narrowed",
                    blocker_key="max_drawdown",
                    direction="strategy_diagnostics",
                    data_ready=True,
                    state_snapshot=repeated_snapshot,
                ),
            ),
        ],
        verifications=[
            VerificationResult(classification="blocker_clarified", summary="audit clarified", verified_progress=False, new_information=True, next_recommendation="inspect audit"),
            VerificationResult(classification="blocker_clarified", summary="dry run clarified", verified_progress=False, new_information=True, next_recommendation="stop honestly"),
        ],
        action_names=["research_audit", "agent_cycle_dry_run"],
    )

    result = run_iterative_loop(
        project=project,
        target_iterations=4,
        max_iterations=4,
        clarify_only_limit=3,
        driver=driver,
    )
    _, refreshed = load_machine_state(project)
    queue = {item["task_id"]: item for item in refreshed["execution_queue"]}

    assert result["iteration_count"] == 2
    assert result["stop_reason"] == "low_roi_repeated_blocker"
    assert queue["refresh_research_audit"]["selected_count"] == 1
    assert queue["dry_run_agent_cycle"]["selected_count"] == 1
    assert "刷新 repo truth 与审计基线" in result["completed"]


def test_repeated_blocker_queue_prefers_untried_followup(limit_up_project) -> None:
    truth = _truth(
        blocker="drawdown",
        blocker_key="max_drawdown",
        direction="strategy_diagnostics",
        data_ready=True,
        state_snapshot={
            "iterative_loop": {
                "blocker_history": {
                    "max_drawdown": {
                        "count": 4,
                    },
                },
            },
        },
    )
    queue = loop_module._merge_execution_queue(
        [
            {
                "task_id": "refresh_promotion_boundary",
                "current_status": "advanced",
                "selected_count": 1,
                "last_iteration": 1,
                "last_classification": "blocker_clarified",
            },
            {
                "task_id": "recover_daily_bars",
                "current_status": "done",
                "selected_count": 1,
                "last_iteration": 1,
                "last_classification": "verified_progress",
            },
        ]
    )
    queue = loop_module._sync_queue_with_truth(queue, truth)

    picked = loop_module._pick_queue_task(queue=queue, truth=truth, history=[])

    assert picked is not None
    assert picked["task_id"] == "refresh_research_audit"


def test_iterative_checkpoint_stays_lightweight() -> None:
    checkpoint = render_iterative_checkpoint(
        {
            "completed": "refreshed readiness",
            "not_done": "drawdown remains unclear",
            "direction_change": False,
            "current_blocker": "drawdown remains unclear",
            "next_recommendation": "run dry-run cycle",
            "max_active_subagents": 0,
            "subagent_gate_mode": "AUTO",
            "subagent_reason": "Keeping the gate effectively OFF is correct while the task stays single-path.",
            "subagent_status": {
                "active_count": 0,
                "blocked_count": 0,
                "retired_count": 0,
                "merged_count": 0,
                "archived_count": 0,
                "gate_mode": "AUTO",
            },
            "research_progress": {
                "dimensions": [
                    {"dimension": "Data inputs", "status": "blocked", "score": 1, "evidence": "默认项目仍缺少可用 validated bars。"},
                    {"dimension": "Strategy integrity", "status": "partial", "score": 2, "evidence": "单一研究核心和契约护栏已存在。"},
                    {"dimension": "Validation stack", "status": "partial", "score": 2, "evidence": "审计与晋级框架已建立。"},
                    {"dimension": "Promotion readiness", "status": "blocked", "score": 1, "evidence": "研究输入仍不足以支撑晋级判断。"},
                    {"dimension": "Subagent effectiveness", "status": "partial", "score": 2, "evidence": "治理存在，但本轮保持有效 OFF。"},
                ],
                "overall_trajectory": "blocked",
                "this_run_delta": "unchanged",
                "current_blocker": "drawdown remains unclear",
                "next_milestone": "run dry-run cycle",
                "confidence": "medium",
            },
        },
    )

    assert checkpoint.splitlines()[0] == "Done"
    assert "Not done" in checkpoint
    assert "Research progress" in checkpoint
    assert "Next recommendation" in checkpoint
    assert "Subagent status" in checkpoint
    for dimension in [
        "Data inputs",
        "Strategy integrity",
        "Validation stack",
        "Promotion readiness",
        "Subagent effectiveness",
    ]:
        assert dimension in checkpoint
    table_lines = [line for line in checkpoint.splitlines() if line.startswith("| ") and "/4" in line]
    assert len(table_lines) == 5
    for line in table_lines:
        score = int(line.split("|")[3].strip().split("/")[0])
        assert 0 <= score <= 4
    assert len(checkpoint.splitlines()) <= 30


def test_iterative_run_records_research_progress_and_delta(limit_up_project) -> None:
    project = limit_up_project["project"]

    baseline_driver = _SequenceDriver(
        truths=[
            (
                _truth(blocker="data gap", blocker_key="data_inputs", direction="input_recovery", data_ready=False),
                _truth(blocker="data gap persists", blocker_key="data_inputs", direction="input_recovery", data_ready=False),
            ),
        ],
        verifications=[
            VerificationResult(classification="blocker_clarified", summary="baseline", verified_progress=False, new_information=True, next_recommendation="recover inputs"),
        ],
    )
    run_iterative_loop(project=project, target_iterations=1, max_iterations=1, driver=baseline_driver)
    _, first_state = load_machine_state(project)
    assert first_state["research_progress"]["this_run_delta"] == "improved"

    improved_driver = _SequenceDriver(
        truths=[
            (
                _truth(blocker="none", blocker_key="none", direction="verification", data_ready=True),
                _truth(blocker="none", blocker_key="none", direction="verification", data_ready=True),
            ),
        ],
        verifications=[
            VerificationResult(classification="verified_progress", summary="inputs recovered", verified_progress=True, new_information=True, next_recommendation="evaluate promotion"),
        ],
    )
    improved_result = run_iterative_loop(project=project, target_iterations=1, max_iterations=1, driver=improved_driver)
    _, improved_state = load_machine_state(project)

    assert improved_state["research_progress"]["this_run_delta"] == "improved"
    assert "Research progress" in improved_result["checkpoint"]
    for item in improved_state["research_progress"]["dimensions"]:
        assert 0 <= int(item["score"]) <= 4

    for path in [
        limit_up_project["paths"].project_state_path,
        limit_up_project["paths"].research_memory_path,
        limit_up_project["paths"].verify_last_path,
        limit_up_project["paths"].handoff_path,
        limit_up_project["paths"].migration_prompt_path,
    ]:
        text = path.read_text(encoding="utf-8")
        assert "研究进度" in text
        assert "总体轨迹" in text
        assert "下一里程碑" in text

    regressed_driver = _SequenceDriver(
        truths=[
            (
                _truth(blocker="data gap reopened", blocker_key="data_inputs", direction="input_recovery", data_ready=False),
                _truth(blocker="data gap reopened", blocker_key="data_inputs", direction="input_recovery", data_ready=False),
            ),
        ],
        verifications=[
            VerificationResult(classification="no_meaningful_progress", summary="coverage regressed", verified_progress=False, new_information=False, next_recommendation="repair inputs"),
        ],
    )
    run_iterative_loop(project=project, target_iterations=1, max_iterations=1, driver=regressed_driver)
    _, regressed_state = load_machine_state(project)
    assert regressed_state["research_progress"]["this_run_delta"] == "unchanged"


def test_iterative_run_persists_execution_queue_across_runs(limit_up_project) -> None:
    project = limit_up_project["project"]
    first_driver = _SequenceDriver(
        truths=[
            (
                _truth(blocker="data gap", blocker_key="data_inputs", direction="input_recovery", data_ready=False),
                _truth(blocker="data gap shrinking", blocker_key="data_inputs", direction="input_recovery", data_ready=False),
            ),
        ],
        verifications=[
            VerificationResult(classification="blocker_clarified", summary="queue advanced", verified_progress=False, new_information=True, next_recommendation="recover inputs"),
        ],
        action_name="data_validate",
    )
    run_iterative_loop(project=project, target_iterations=1, max_iterations=1, driver=first_driver)
    _, first_state = load_machine_state(project)
    selected_before = {
        item["task_id"]: item.get("selected_count", 0)
        for item in first_state["execution_queue"]
    }

    second_driver = _SequenceDriver(
        truths=[
            (
                _truth(blocker="none", blocker_key="none", direction="verification", data_ready=True),
                _truth(blocker="none", blocker_key="none", direction="verification", data_ready=True),
            ),
        ],
        verifications=[
            VerificationResult(classification="verified_progress", summary="promotion refreshed", verified_progress=True, new_information=True, next_recommendation="dry run"),
        ],
        action_name="promote_candidate",
    )
    run_iterative_loop(project=project, target_iterations=1, max_iterations=1, driver=second_driver)
    _, second_state = load_machine_state(project)

    assert second_state["execution_queue"]
    selected_after = {
        item["task_id"]: item.get("selected_count", 0)
        for item in second_state["execution_queue"]
    }
    assert selected_after["recover_daily_bars"] >= selected_before["recover_daily_bars"]
    assert "执行队列" in limit_up_project["paths"].execution_queue_path.read_text(encoding="utf-8")


def test_iterative_run_avoids_per_iteration_memory_reload(limit_up_project, monkeypatch) -> None:
    project = limit_up_project["project"]
    driver = _SequenceDriver(
        truths=[
            (
                _truth(blocker="data gap", blocker_key="data_inputs", direction="input_recovery", data_ready=False),
                _truth(blocker="data gap shrinking", blocker_key="data_inputs", direction="input_recovery", data_ready=False),
            ),
            (
                _truth(blocker="data gap shrinking", blocker_key="data_inputs", direction="input_recovery", data_ready=False),
                _truth(blocker="diagnostics ready", blocker_key="none", direction="verification", data_ready=True),
            ),
            (
                _truth(blocker="drawdown", blocker_key="max_drawdown", direction="strategy_diagnostics", data_ready=True),
                _truth(blocker="drawdown clarified", blocker_key="max_drawdown", direction="strategy_diagnostics", data_ready=True),
            ),
            (
                _truth(blocker="none", blocker_key="none", direction="verification", data_ready=True),
                _truth(blocker="none", blocker_key="none", direction="verification", data_ready=True),
            ),
        ],
        verifications=[
            VerificationResult(classification="blocker_clarified", summary="iteration 1", verified_progress=False, new_information=True, next_recommendation="validate again"),
            VerificationResult(classification="direction_corrected", summary="iteration 2", verified_progress=True, new_information=True, direction_changed=True, allow_extra_iteration=True, next_recommendation="run diagnostics"),
            VerificationResult(classification="verified_progress", summary="iteration 3", verified_progress=True, new_information=True, next_recommendation="dry run"),
            VerificationResult(classification="verified_progress", summary="iteration 4", verified_progress=True, new_information=True, next_recommendation="stop"),
        ],
        action_name="research_audit",
    )
    calls = {"count": 0}
    real_load = loop_module.load_machine_state

    def _counted_load(*args, **kwargs):
        calls["count"] += 1
        return real_load(*args, **kwargs)

    monkeypatch.setattr(loop_module, "load_machine_state", _counted_load)
    result = run_iterative_loop(
        project=project,
        driver=driver,
        target_iterations=4,
        max_iterations=4,
        min_substantive_actions=2,
        target_substantive_actions=3,
    )

    assert result["iteration_count"] == 4
    assert result["controlled_refresh_count"] == 0
    assert result["run_start_read_count"] >= 6
    assert calls["count"] <= 2


def test_iterative_run_auto_closes_finished_subagents(limit_up_project) -> None:
    project = limit_up_project["project"]
    created = register_worker_subagent(
        project=project,
        role="validation_guard",
        summary="temporary validation branch",
        mission_id="mission-test",
        branch_id="branch-test",
        candidate_id="candidate-test",
        worker_task_id="worker-closeout",
        expected_artifacts=["artifact"],
        allowed_paths=["tests"],
    )

    driver = _SequenceDriver(
        truths=[
            (
                _truth(blocker="drawdown", blocker_key="max_drawdown", direction="strategy_diagnostics", data_ready=True),
                _truth(blocker="drawdown", blocker_key="max_drawdown", direction="strategy_diagnostics", data_ready=True),
            ),
        ],
        verifications=[
            VerificationResult(classification="no_meaningful_progress", summary="stalled", verified_progress=False, new_information=False, next_recommendation="stop"),
        ],
    )

    run_iterative_loop(project=project, driver=driver, target_iterations=1, max_iterations=1)
    _, state = load_machine_state(project)
    records = {item["subagent_id"]: item for item in state["subagents"]}

    assert records[created["subagent_id"]]["status"] == "retired"
    assert created["subagent_id"] in state["iterative_loop"]["auto_closed_subagents"]
    assert state["iterative_loop"]["retired_subagent_count"] >= 1


def test_iterative_run_can_replace_old_subagents_when_new_branch_is_justified(limit_up_project) -> None:
    project = limit_up_project["project"]
    created = register_worker_subagent(
        project=project,
        role="data_steward",
        summary="old data branch",
        mission_id="mission-test",
        branch_id="branch-test",
        candidate_id="candidate-test",
        worker_task_id="worker-replace",
        expected_artifacts=["artifact"],
        allowed_paths=["tests"],
    )
    _, state = load_machine_state(project)
    state["subagent_gate_mode"] = "FORCE"
    save_machine_state(project, state)

    driver = _SequenceDriver(
        truths=[
            (
                _truth(blocker="validation memory drift", blocker_key="validation_memory", direction="control_plane_verification", data_ready=True),
                _truth(blocker="validation memory drift", blocker_key="validation_memory", direction="control_plane_verification", data_ready=True),
            ),
        ],
        verifications=[
            VerificationResult(classification="no_meaningful_progress", summary="stalled", verified_progress=False, new_information=False, next_recommendation="stop"),
        ],
        action_name="research_audit",
    )

    result = run_iterative_loop(project=project, driver=driver, target_iterations=1, max_iterations=1)
    _, refreshed = load_machine_state(project)
    records = {item["subagent_id"]: item for item in refreshed["subagents"]}

    assert records[created["subagent_id"]]["status"] == "canceled"
    assert result["alternative_subagents"]
    for item in result["alternative_subagents"]:
        assert created["subagent_id"] in records[item["subagent_id"]]["parent_ids"]
    assert refreshed["iterative_loop"]["alternative_subagents"]
    assert refreshed["iterative_loop"]["canceled_subagent_count"] >= 1


def test_register_worker_subagent_rejects_recursive_spawn(limit_up_project) -> None:
    with pytest.raises(ValueError, match="Recursive subagent spawning is prohibited"):
        register_worker_subagent(
            project=limit_up_project["project"],
            role="validation_guard",
            summary="illegal recursive spawn",
            mission_id="mission-test",
            branch_id="branch-test",
            candidate_id="candidate-test",
            worker_task_id="worker-test",
            expected_artifacts=["artifact"],
            allowed_paths=["tests"],
            requested_by_subagent_id="sa-parent",
        )


def test_register_worker_subagent_enforces_hard_limit(limit_up_project) -> None:
    for index in range(6):
        register_worker_subagent(
            project=limit_up_project["project"],
            role="validation_guard",
            summary=f"worker {index}",
            mission_id="mission-test",
            branch_id="branch-test",
            candidate_id="candidate-test",
            worker_task_id=f"worker-{index}",
            expected_artifacts=["artifact"],
            allowed_paths=["tests"],
        )

    with pytest.raises(ValueError, match="Subagent hard limit exceeded"):
        register_worker_subagent(
            project=limit_up_project["project"],
            role="validation_guard",
            summary="worker overflow",
            mission_id="mission-test",
            branch_id="branch-test",
            candidate_id="candidate-test",
            worker_task_id="worker-overflow",
            expected_artifacts=["artifact"],
            allowed_paths=["tests"],
        )
