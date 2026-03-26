from __future__ import annotations

import json

import pytest

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
    def __init__(self, *, truths: list[tuple[RepoTruth, RepoTruth]], verifications: list[VerificationResult], action_name: str = "agent_cycle_dry_run"):
        self.truths = truths
        self.verifications = verifications
        self.action_name = action_name
        self.iteration = 0
        self.scan_index = 0

    def rescan(self, *, project: str, repo_root=None, config_path=None) -> RepoTruth:
        del project, repo_root, config_path
        pair = self.truths[min(self.scan_index // 2, len(self.truths) - 1)]
        truth = pair[0] if self.scan_index % 2 == 0 else pair[1]
        self.scan_index += 1
        return truth

    def choose_action(self, *, truth: RepoTruth, history: list[dict], config: LoopConfig) -> LoopAction | None:
        del history, config
        return LoopAction(
            name=self.action_name,
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
    assert session["iterative_loop"]["direction_change"] is True
    assert "## Last Iterative Run" in handoff
    assert "## Last Iterative Run" in migration


def test_iterative_run_stops_when_no_verified_progress(limit_up_project) -> None:
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

    result = run_iterative_loop(project=limit_up_project["project"], driver=driver)

    assert result["stop_reason"] == "no_verified_progress"
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

    assert result["stop_reason"] == "verification_failed_scope_expanded"


def test_iterative_run_escalates_repeated_blocker(limit_up_project) -> None:
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
        project=limit_up_project["project"],
        target_iterations=5,
        max_iterations=5,
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

    result = run_iterative_loop(project=project, driver=driver)
    session = json.loads(limit_up_project["paths"].session_state_path.read_text(encoding="utf-8"))

    assert result["stop_reason"] == "low_roi_repeated_blocker"
    assert result["blocker_repeat_count"] == 3
    assert result["blocker_escalation"] is True
    assert "Escalated blocker" in result["next_recommendation"]
    assert session["iterative_loop"]["blocker_escalation"] is True


def test_iterative_checkpoint_stays_lightweight() -> None:
    checkpoint = render_iterative_checkpoint(
        {
            "completed": "refreshed readiness",
            "direction_change": False,
            "stop_reason": "target_iterations_reached",
            "iteration_count": 2,
            "target_iterations": 2,
            "max_iterations": 5,
            "blocker_key": "data_inputs",
            "blocker_repeat_count": 1,
            "next_recommendation": "run dry-run cycle",
            "max_active_subagents": 0,
            "subagent_gate_mode": "AUTO",
            "subagent_reason": "Keeping the gate effectively OFF is correct while the task stays single-path.",
            "subagent_status": {
                "active_count": 0,
                "blocked_count": 0,
                "retired_count": 0,
                "merged_count": 0,
                "gate_mode": "AUTO",
            },
        },
    )

    assert checkpoint.splitlines()[0] == "Done"
    assert "Evidence" in checkpoint
    assert "Next action" in checkpoint
    assert "Subagent status" in checkpoint
    assert len(checkpoint.splitlines()) <= 12


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
