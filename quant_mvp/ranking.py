from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .db import load_close_volume_panel


def get_rebalance_dates_tuesday(
    calendar: pd.DatetimeIndex,
    lookback: int,
    weekday: int = 2,
) -> list[pd.Timestamp]:
    """Return rebalance dates that fall on weekday (0=Mon, 2=Tue). Requires at least lookback bars before first date."""
    cal = calendar.sort_values()
    if len(cal) <= lookback:
        return []
    candidates = cal[lookback:]
    tuesdays = [pd.Timestamp(d) for d in candidates if d.weekday() == weekday]
    return tuesdays


@dataclass
class RankBuildResult:
    rank_df: pd.DataFrame
    candidate_count_df: pd.DataFrame
    candidate_scores_df: pd.DataFrame
    rebalance_dates: list[pd.Timestamp]
    used_codes: list[str]


def build_momentum_rank(
    db_path,
    freq: str,
    universe_codes: list[str],
    lookback: int,
    rebalance_every: int,
    topk: int,
    min_bars: int,
    max_codes_scan: int,
    require_positive_volume: bool = False,
    min_volume: float = 0.0,
) -> RankBuildResult:
    if topk <= 0:
        raise ValueError("topk must be positive")
    if rebalance_every <= 0:
        raise ValueError("rebalance_every must be positive")
    if lookback <= 0:
        raise ValueError("lookback must be positive")

    codes = sorted(set(universe_codes))[:max_codes_scan]
    close, volume = load_close_volume_panel(db_path=db_path, freq=freq, codes=codes)

    enough_history = close.count() >= min_bars
    eligible_codes = enough_history[enough_history].index.tolist()
    if not eligible_codes:
        raise RuntimeError("No codes satisfy min_bars in universe.")

    close = close[eligible_codes]
    volume = volume[eligible_codes]

    calendar = close.index.sort_values()
    if len(calendar) <= lookback:
        raise RuntimeError("Not enough trading days to compute momentum.")
    rebalance_dates = list(calendar[lookback::rebalance_every])

    momentum = close.pct_change(lookback, fill_method=None)
    rows_topk: list[dict[str, object]] = []
    rows_candidates: list[dict[str, object]] = []
    rows_counts: list[dict[str, object]] = []

    for dt in rebalance_dates:
        score_raw = momentum.loc[dt].dropna()
        score = score_raw.copy()
        if require_positive_volume:
            liquid = volume.loc[dt].fillna(0.0)
            score = score[liquid > 0]
        if min_volume > 0:
            liquid = volume.loc[dt].fillna(0.0)
            score = score[liquid >= min_volume]

        score = score.sort_values(ascending=False)
        rows_counts.append(
            {
                "date": dt,
                "candidate_count_raw": int(score_raw.shape[0]),
                "candidate_count": int(score.shape[0]),
            },
        )

        if score.empty:
            continue

        for code, val in score.items():
            rows_candidates.append(
                {
                    "date": dt,
                    "code": str(code).zfill(6),
                    "score": float(val),
                },
            )

        top = score.head(topk)
        for rank, (code, val) in enumerate(top.items(), start=1):
            rows_topk.append(
                {
                    "date": dt,
                    "code": str(code).zfill(6),
                    "score": float(val),
                    "rank": rank,
                },
            )

    rank_df = pd.DataFrame(rows_topk)
    candidate_df = pd.DataFrame(rows_counts)
    candidates_df = pd.DataFrame(rows_candidates)

    if rank_df.empty:
        raise RuntimeError("Rank dataframe is empty. Check coverage/min_bars settings.")

    rank_df["date"] = pd.to_datetime(rank_df["date"])
    candidate_df["date"] = pd.to_datetime(candidate_df["date"])
    candidates_df["date"] = pd.to_datetime(candidates_df["date"])

    return RankBuildResult(
        rank_df=rank_df.sort_values(["date", "rank", "code"]).reset_index(drop=True),
        candidate_count_df=candidate_df.sort_values(["date"]).reset_index(drop=True),
        candidate_scores_df=candidates_df.sort_values(["date", "score"], ascending=[True, False]).reset_index(
            drop=True,
        ),
        rebalance_dates=rebalance_dates,
        used_codes=eligible_codes,
    )


def build_rank_tuesday_momentum(
    db_path,
    freq: str,
    universe_codes: list[str],
    lookback: int,
    topk: int,
    min_bars: int,
    max_codes_scan: int,
    require_positive_volume: bool = False,
    min_volume: float = 0.0,
) -> RankBuildResult:
    """
    Build momentum rank with rebalance only on Tuesdays (weekday=2).
    Output format compatible with rank_topK.parquet (date, code, score, rank).
    """
    if topk <= 0:
        raise ValueError("topk must be positive")
    if lookback <= 0:
        raise ValueError("lookback must be positive")

    codes = sorted(set(universe_codes))[:max_codes_scan]
    close, volume = load_close_volume_panel(db_path=db_path, freq=freq, codes=codes)
    enough_history = close.count() >= min_bars
    eligible_codes = enough_history[enough_history].index.tolist()
    if not eligible_codes:
        raise RuntimeError("No codes satisfy min_bars in universe.")

    close = close[eligible_codes]
    volume = volume[eligible_codes]
    calendar = close.index.sort_values()
    if len(calendar) <= lookback:
        raise RuntimeError("Not enough trading days to compute momentum.")

    rebalance_dates = get_rebalance_dates_tuesday(calendar, lookback=lookback, weekday=2)
    if not rebalance_dates:
        raise RuntimeError("No Tuesday rebalance dates in range.")

    momentum = close.pct_change(lookback, fill_method=None)
    rows_topk: list[dict[str, object]] = []
    rows_candidates: list[dict[str, object]] = []
    rows_counts: list[dict[str, object]] = []

    for dt in rebalance_dates:
        if dt not in momentum.index:
            continue
        score_raw = momentum.loc[dt].dropna()
        score = score_raw.copy()
        if require_positive_volume:
            liquid = volume.loc[dt].fillna(0.0)
            score = score[liquid > 0]
        if min_volume > 0:
            liquid = volume.loc[dt].fillna(0.0)
            score = score[liquid >= min_volume]
        score = score.sort_values(ascending=False)
        rows_counts.append({
            "date": dt,
            "candidate_count_raw": int(score_raw.shape[0]),
            "candidate_count": int(score.shape[0]),
        })
        if score.empty:
            continue
        for code, val in score.items():
            rows_candidates.append({"date": dt, "code": str(code).zfill(6), "score": float(val)})
        top = score.head(topk)
        for rank, (code, val) in enumerate(top.items(), start=1):
            rows_topk.append({
                "date": dt,
                "code": str(code).zfill(6),
                "score": float(val),
                "rank": rank,
            })

    rank_df = pd.DataFrame(rows_topk)
    candidate_df = pd.DataFrame(rows_counts)
    candidates_df = pd.DataFrame(rows_candidates)
    if rank_df.empty:
        raise RuntimeError("Rank dataframe is empty. Check coverage/min_bars and Tuesday calendar.")
    rank_df["date"] = pd.to_datetime(rank_df["date"])
    candidate_df["date"] = pd.to_datetime(candidate_df["date"])
    candidates_df["date"] = pd.to_datetime(candidates_df["date"])
    return RankBuildResult(
        rank_df=rank_df.sort_values(["date", "rank", "code"]).reset_index(drop=True),
        candidate_count_df=candidate_df.sort_values(["date"]).reset_index(drop=True),
        candidate_scores_df=candidates_df.sort_values(["date", "score"], ascending=[True, False]).reset_index(drop=True),
        rebalance_dates=rebalance_dates,
        used_codes=eligible_codes,
    )
