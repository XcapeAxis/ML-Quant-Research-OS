from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import pandas as pd


@dataclass
class WalkForwardWindowResult:
    name: str
    start: str
    end: str
    rows: int
    mean_score: float
    survived: bool


def walk_forward_summary(
    *,
    rank_df: pd.DataFrame,
    windows: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
) -> dict[str, Any]:
    results: list[WalkForwardWindowResult] = []
    rank_frame = rank_df.copy()
    rank_frame["date"] = pd.to_datetime(rank_frame["date"])
    for window in windows:
        start = pd.Timestamp(window["start"])
        end = pd.Timestamp(window["end"])
        sub = rank_frame[(rank_frame["date"] >= start) & (rank_frame["date"] <= end)]
        mean_score = float(sub["score"].mean()) if not sub.empty and "score" in sub.columns else 0.0
        survived = bool(not sub.empty)
        results.append(
            WalkForwardWindowResult(
                name=str(window["name"]),
                start=str(window["start"]),
                end=str(window["end"]),
                rows=int(len(sub)),
                mean_score=mean_score,
                survived=survived,
            ),
        )
    alive = sum(1 for item in results if item.survived)
    return {
        "windows": [item.__dict__ for item in results],
        "windows_alive": alive,
        "all_windows_alive": alive == len(results),
    }
