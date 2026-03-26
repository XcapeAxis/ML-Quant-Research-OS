from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class CoreUniverseSpec:
    board_scope: str = "mainboard_a_share"
    exclude_st: bool = True
    min_listing_days: int = 375
    min_history_bars: int = 160
    recent_volume_window: int = 20
    min_positive_volume_ratio: float = 0.9
    liquidity_keep_ratio: float = 0.7
    liquidity_proxy: str = "close_x_volume"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BranchPoolSpec:
    branch_id: str
    generator_id: str
    strategy_mode: str
    limit_days_window: int
    top_pct_limit_up: float
    top_candidates: int
    hypothesis: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PoolMembershipDecision:
    code: str
    included: bool
    reasons: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CoreUniverseSnapshot:
    snapshot_id: str
    generated_at: str
    as_of_date: str | None
    spec: CoreUniverseSpec
    source_codes_path: str
    metadata_path: str | None
    codes: list[str]
    hash: str
    decision_counts: dict[str, int]
    decisions: dict[str, PoolMembershipDecision]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["spec"] = self.spec.to_dict()
        payload["decisions"] = {code: item.to_dict() for code, item in self.decisions.items()}
        return payload


@dataclass(frozen=True)
class BranchPoolSnapshot:
    snapshot_id: str
    generated_at: str
    as_of_date: str | None
    branch_id: str
    core_snapshot_id: str
    spec: BranchPoolSpec
    codes: list[str]
    hash: str
    decision_counts: dict[str, int]
    decisions: dict[str, PoolMembershipDecision]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["spec"] = self.spec.to_dict()
        payload["decisions"] = {code: item.to_dict() for code, item in self.decisions.items()}
        return payload


@dataclass(frozen=True)
class PoolExplanation:
    project: str
    kind: str
    snapshot_id: str
    code: str
    included: bool
    reasons: list[str]
    metrics: dict[str, Any]
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
