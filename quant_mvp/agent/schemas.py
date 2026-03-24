from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ExperimentPlan:
    mode: str
    primary_hypothesis: str
    steps: list[str]
    success_criteria: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExecutionRecord:
    mode: str
    executed_steps: list[str]
    outputs: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvaluationRecord:
    passed: bool
    summary: str
    promotion_decision: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReflectionRecord:
    summary: str
    next_hypotheses: list[str]
    lessons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AgentCycleRecord:
    cycle_id: str
    timestamp: str
    backend: str
    hypotheses: list[str]
    plan: dict[str, Any]
    execution: dict[str, Any]
    evaluation: dict[str, Any]
    reflection: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
