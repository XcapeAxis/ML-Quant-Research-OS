from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class MissionBudget:
    max_branches: int
    experiments_per_tick: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MissionConstraint:
    research_scope: str
    no_live_trading: bool = True
    board_scope: str = "mainboard_a_share_only"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MissionCheckpoint:
    label: str
    status: str
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ResearchMission:
    mission_id: str
    project: str
    state: str
    objective: str
    created_at: str
    updated_at: str
    budget: MissionBudget
    constraints: MissionConstraint
    checkpoints: list[MissionCheckpoint] = field(default_factory=list)
    active_branch_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["budget"] = self.budget.to_dict()
        payload["constraints"] = self.constraints.to_dict()
        payload["checkpoints"] = [item.to_dict() for item in self.checkpoints]
        return payload


@dataclass(frozen=True)
class BranchBudget:
    experiment_slots: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BranchPriority:
    rank: int
    score: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StrategyCandidate:
    candidate_id: str
    branch_id: str
    name: str
    strategy_mode: str
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ResearchBranch:
    branch_id: str
    mission_id: str
    state: str
    title: str
    objective: str
    hypothesis: str
    created_at: str
    updated_at: str
    budget: BranchBudget
    priority: BranchPriority
    core_universe_snapshot_id: str | None = None
    branch_pool_snapshot_id: str | None = None
    opportunity_generator_id: str | None = None
    strategy_candidate: StrategyCandidate | None = None
    experiment_id: str | None = None
    stop_rules: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["budget"] = self.budget.to_dict()
        payload["priority"] = self.priority.to_dict()
        payload["strategy_candidate"] = self.strategy_candidate.to_dict() if self.strategy_candidate else None
        return payload


@dataclass(frozen=True)
class WorkerTask:
    task_id: str
    mission_id: str
    branch_id: str
    candidate_id: str
    role: str
    state: str
    subagent_id: str | None = None
    expected_artifacts: list[str] = field(default_factory=list)
    artifact_refs: list[str] = field(default_factory=list)
    stop_condition: str = ""
    summary: str = ""
    result_summary: str = ""
    started_at: str | None = None
    finished_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SelectionDecision:
    branch_id: str
    action: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
