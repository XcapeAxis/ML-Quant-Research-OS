from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


GateMode = Literal["OFF", "AUTO", "FORCE"]
SubagentStatus = Literal["proposed", "active", "blocked", "merged", "retired", "canceled", "archived", "refactored"]


@dataclass(frozen=True)
class SubagentTaskProfile:
    task_summary: str
    breadth: int
    independence: float
    file_overlap: float
    validation_load: float
    coordination_cost: float
    risk_isolation: float
    focus_tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SubagentRoleTemplate:
    role: str
    responsibilities: list[str]
    allowed_paths: list[str]
    expected_artifacts: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SubagentWorkPackage:
    role: str
    summary: str
    allowed_paths: list[str]
    expected_artifacts: list[str]
    transient: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SubagentPlan:
    gate_mode: GateMode
    recommended_gate: GateMode
    recommended_count: int
    recommended_roles: list[str]
    work_packages: list[SubagentWorkPackage]
    should_expand: bool
    no_split_reason: str
    rationale: str
    score: float

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["work_packages"] = [item.to_dict() for item in self.work_packages]
        return payload


@dataclass
class SubagentRecord:
    subagent_id: str
    role: str
    summary: str
    status: SubagentStatus
    transient: bool
    allowed_paths: list[str]
    expected_artifacts: list[str]
    artifact_dir: str | None = None
    parent_ids: list[str] = field(default_factory=list)
    child_ids: list[str] = field(default_factory=list)
    merged_into: str | None = None
    mission_id: str | None = None
    branch_id: str | None = None
    candidate_id: str | None = None
    worker_task_id: str | None = None
    lineage_root_id: str | None = None
    spawn_depth: int = 0
    created_at: str = ""
    updated_at: str = ""
    last_action: str = ""
    last_note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SubagentEvent:
    timestamp: str
    action: str
    project: str
    subagent_id: str
    from_status: str
    to_status: str
    summary: str
    related_ids: list[str] = field(default_factory=list)
    artifact_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
