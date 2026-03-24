from __future__ import annotations

from .schemas import ExperimentPlan


def build_plan(*, hypothesis: str, backend_plan: dict) -> ExperimentPlan:
    return ExperimentPlan(
        mode=str(backend_plan.get("mode", "dry_run")),
        primary_hypothesis=hypothesis,
        steps=list(backend_plan.get("steps", [])),
        success_criteria=list(backend_plan.get("success_criteria", [])),
    )
