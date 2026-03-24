from __future__ import annotations

from pathlib import Path

from quant_mvp.agent.subagent_models import SubagentTaskProfile
from quant_mvp.agent.subagent_policy import evaluate_subagent_plan, load_subagent_policy, load_subagent_roles


ROOT = Path(__file__).resolve().parents[1]


def _policy():
    return load_subagent_policy(ROOT / "configs" / "subagent_policy.yaml")


def _roles():
    return load_subagent_roles(ROOT / "configs" / "subagent_roles.yaml")


def test_auto_mode_small_task_stays_off() -> None:
    plan = evaluate_subagent_plan(
        SubagentTaskProfile(
            task_summary="Touch one config file and refresh one summary",
            breadth=1,
            independence=0.4,
            file_overlap=0.1,
            validation_load=0.2,
            coordination_cost=0.4,
            risk_isolation=0.1,
            focus_tags=["memory"],
        ),
        gate_mode="AUTO",
        policy=_policy(),
        role_templates=_roles(),
    )

    assert plan.gate_mode == "AUTO"
    assert plan.recommended_gate == "OFF"
    assert plan.recommended_count == 0
    assert not plan.should_expand


def test_high_independence_task_gets_subagent_plan() -> None:
    plan = evaluate_subagent_plan(
        SubagentTaskProfile(
            task_summary="Split future data ingestion, validation, and integration work after bars are restored",
            breadth=3,
            independence=0.9,
            file_overlap=0.15,
            validation_load=0.8,
            coordination_cost=0.2,
            risk_isolation=0.6,
            focus_tags=["data", "validation", "merge"],
        ),
        gate_mode="AUTO",
        policy=_policy(),
        role_templates=_roles(),
    )

    assert plan.recommended_gate == "AUTO"
    assert plan.should_expand
    assert plan.recommended_count >= 2
    assert {"data_steward", "validation_guard"}.issubset(set(plan.recommended_roles))


def test_high_overlap_task_is_suppressed() -> None:
    plan = evaluate_subagent_plan(
        SubagentTaskProfile(
            task_summary="Edit the same core files from multiple angles",
            breadth=4,
            independence=0.8,
            file_overlap=0.9,
            validation_load=0.8,
            coordination_cost=0.4,
            risk_isolation=0.5,
            focus_tags=["strategy", "validation"],
        ),
        gate_mode="AUTO",
        policy=_policy(),
        role_templates=_roles(),
    )

    assert plan.recommended_gate == "OFF"
    assert "overlap" in plan.no_split_reason.lower()
