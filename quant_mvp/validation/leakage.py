from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

import pandas as pd

from ..data.validation import build_tradability_mask


def _stable_hash(payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class LeakageIssue:
    check: str
    severity: str
    message: str


@dataclass
class LeakageReport:
    passed: bool
    timestamp_alignment_ok: bool
    feature_shift_ok: bool
    tradability_mask_ok: bool
    cross_section_ok: bool
    config_hash: str
    universe_hash: str
    data_snapshot_hash: str
    issues: list[LeakageIssue] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["issues"] = [asdict(item) for item in self.issues]
        return payload


def check_feature_label_shift(
    feature_index: pd.Index,
    label_index: pd.Index,
    *,
    forward_horizon_days: int = 1,
) -> bool:
    features = pd.to_datetime(feature_index)
    labels = pd.to_datetime(label_index)
    if len(features) == 0 or len(labels) == 0:
        return False
    label_set = pd.DatetimeIndex(labels).sort_values()
    for feature_date in pd.DatetimeIndex(features).sort_values():
        later = label_set[label_set > pd.Timestamp(feature_date)]
        if later.empty:
            return False
        delta_days = int((pd.Timestamp(later[0]) - pd.Timestamp(feature_date)).days)
        if delta_days < forward_horizon_days:
            return False
    return True


def audit_strategy_leakage(
    *,
    rank_df: pd.DataFrame,
    close_panel: pd.DataFrame,
    volume_panel: pd.DataFrame,
    cfg: Mapping[str, Any],
    universe_codes: list[str],
) -> LeakageReport:
    issues: list[LeakageIssue] = []
    rank_frame = rank_df.copy()
    rank_frame["date"] = pd.to_datetime(rank_frame["date"])
    calendar = pd.DatetimeIndex(pd.to_datetime(close_panel.index)).sort_values()
    rank_dates = pd.DatetimeIndex(rank_frame["date"].drop_duplicates().sort_values())

    timestamp_alignment_ok = True
    if rank_dates.empty or not rank_dates.isin(calendar).all():
        timestamp_alignment_ok = False
        issues.append(
            LeakageIssue(
                check="timestamp_alignment",
                severity="error",
                message="Rank dates are not fully aligned to the trading calendar.",
            ),
        )
    else:
        last_rank = pd.Timestamp(rank_dates.max())
        if calendar.get_loc(last_rank) >= len(calendar) - 1:
            timestamp_alignment_ok = False
            issues.append(
                LeakageIssue(
                    check="timestamp_alignment",
                    severity="error",
                    message="The last rebalance date has no next trading day for out-of-sample returns.",
                ),
            )

    feature_shift_ok = check_feature_label_shift(
        feature_index=rank_dates,
        label_index=calendar[1:],
        forward_horizon_days=int(cfg.get("research_validation", {}).get("forward_horizon_days", 1)),
    )
    if not feature_shift_ok:
        issues.append(
            LeakageIssue(
                check="feature_shift",
                severity="error",
                message="Feature dates overlap the forward return label window.",
            ),
        )

    tradability_mask = build_tradability_mask(
        close_panel.astype(float),
        volume_panel.astype(float),
        limit_threshold=float(cfg.get("limit_up_threshold", 0.095)),
        min_volume=float(cfg.get("tradability", {}).get("min_volume", 0.0)),
    )
    tradability_mask_ok = True
    selected_mask_violations = 0
    for dt, group in rank_frame.groupby("date"):
        if dt not in tradability_mask.index:
            tradability_mask_ok = False
            continue
        row = tradability_mask.loc[dt]
        selected_mask_violations += sum(not bool(row.get(code, False)) for code in group["code"])
    if selected_mask_violations > 0:
        tradability_mask_ok = False
        issues.append(
            LeakageIssue(
                check="tradability_mask",
                severity="error",
                message=f"{selected_mask_violations} ranked rows violate positive-volume or limit-lock checks.",
            ),
        )

    universe = set(str(code).zfill(6) for code in universe_codes)
    cross_section_ok = bool(rank_frame["code"].astype(str).str.zfill(6).isin(universe).all())
    if not cross_section_ok:
        issues.append(
            LeakageIssue(
                check="cross_section",
                severity="error",
                message="Rank output contains codes outside the frozen universe.",
            ),
        )
    if not rank_frame.empty:
        expected_weekday = int(cfg.get("rebalance_weekday", 1))
        actual_weekdays = set(rank_frame["date"].dt.weekday.unique().tolist())
        if actual_weekdays != {expected_weekday}:
            cross_section_ok = False
            issues.append(
                LeakageIssue(
                    check="weekday_contract",
                    severity="error",
                    message=f"Expected weekday {expected_weekday} but saw {sorted(actual_weekdays)}.",
                ),
            )

    report = LeakageReport(
        passed=timestamp_alignment_ok and feature_shift_ok and tradability_mask_ok and cross_section_ok,
        timestamp_alignment_ok=timestamp_alignment_ok,
        feature_shift_ok=feature_shift_ok,
        tradability_mask_ok=tradability_mask_ok,
        cross_section_ok=cross_section_ok,
        config_hash=_stable_hash(dict(cfg)),
        universe_hash=_stable_hash(sorted(universe)),
        data_snapshot_hash=_stable_hash(
            {
                "close_shape": close_panel.shape,
                "volume_shape": volume_panel.shape,
                "first_date": str(calendar.min()) if len(calendar) else None,
                "last_date": str(calendar.max()) if len(calendar) else None,
            },
        ),
        issues=issues,
        assumptions=[
            "Signals use the rebalance close as the last available observation.",
            "Forward returns start on the next trading day in the calendar.",
        ],
    )
    return report
