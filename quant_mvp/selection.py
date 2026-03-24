"""Stock selection module implementing the limit-up screening strategy.

Core idea: identify stocks with frequent historical limit-up events, then rank
by proximity to their most recent breakout start-point. Combined with universe
filters (STAR/BJ exclusion, ST exclusion, new-stock exclusion, limit-up/down
exclusion) and Tuesday-only rebalancing.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .db import load_ohlcv_panel


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class LimitUpScreeningConfig:
    """Parameters for the limit-up screening selection strategy."""

    stock_num: int = 6
    rebalance_weekday: int = 1  # 0=Mon, 1=Tue
    limit_days_window: int = 250  # ~1 year of trading days
    top_pct_limit_up: float = 0.10  # keep top 10% by limit-up count
    limit_up_threshold: float = 0.095  # daily return >= this => proxy limit-up
    init_pool_size: int = 1000  # pre-filter universe to this size
    min_bars: int = 160
    max_codes_scan: int = 4000
    topk_multiplier: int = 2  # rank 2*stock_num candidates
    require_positive_volume: bool = True
    min_new_listing_days: int = 375


# ---------------------------------------------------------------------------
# Filters (reusable across strategies)
# ---------------------------------------------------------------------------

def get_tuesday_rebalance_dates(
    calendar: pd.DatetimeIndex,
    weekday: int = 1,
) -> list[pd.Timestamp]:
    """Return trading dates that fall on *weekday* (default Tuesday)."""
    return [pd.Timestamp(dt) for dt in calendar if dt.weekday() == weekday]


def filter_kcbj_stock(codes: list[str]) -> list[str]:
    """Keep only mainboard A-share codes and exclude growth / STAR / BSE boards."""
    return [
        c for c in codes
        if not (
            c.startswith("4")
            or c.startswith("8")
            or c.startswith("68")
            or c.startswith("300")
            or c.startswith("301")
        )
    ]


def filter_st_stock_by_name(codes: list[str], names: dict[str, str] | None = None) -> list[str]:
    """Exclude ST / *ST / delisting stocks by name pattern."""
    if names is None:
        return codes
    return [
        c for c in codes
        if c in names
        and "ST" not in names[c]
        and "*" not in names[c]
        and "\u9000" not in names[c]  # Chinese character for "delisting"
    ]


def filter_new_stock(
    codes: list[str],
    listing_dates: dict[str, pd.Timestamp],
    current_date: pd.Timestamp,
    min_days: int = 375,
) -> list[str]:
    """Exclude stocks listed fewer than *min_days* ago."""
    result = []
    for c in codes:
        if c in listing_dates:
            if (current_date - listing_dates[c]).days >= min_days:
                result.append(c)
        else:
            result.append(c)
    return result


def filter_limit_up_down(
    codes: list[str],
    close: pd.Series,
    prev_close: pd.Series,
    limit_pct: float = 0.095,
) -> list[str]:
    """Exclude stocks that are at limit-up or limit-down today."""
    result = []
    for c in codes:
        if c not in close or c not in prev_close:
            continue
        if pd.isna(close[c]) or pd.isna(prev_close[c]) or prev_close[c] == 0:
            continue
        ret = close[c] / prev_close[c] - 1.0
        if abs(ret) < limit_pct:
            result.append(c)
    return result


# ---------------------------------------------------------------------------
# Limit-up history analysis
# ---------------------------------------------------------------------------

def _detect_limit_up_days(
    close: pd.DataFrame,
    open_df: pd.DataFrame,
    threshold: float = 0.095,
) -> pd.DataFrame:
    """Return a boolean DataFrame (dates x codes) marking proxy limit-up days.

    A day is considered limit-up when ``close / prev_close - 1 >= threshold``.
    Using close-to-close return avoids needing exchange-provided high_limit.
    """
    prev_close = close.shift(1)
    daily_ret = close / prev_close - 1.0
    return daily_ret >= threshold


def count_limit_up_history(
    close: pd.DataFrame,
    open_df: pd.DataFrame,
    window: int,
    threshold: float = 0.095,
) -> pd.Series:
    """Count limit-up days in the trailing *window* for each code.

    Returns a Series indexed by code with the count of limit-up days.
    """
    limit_up = _detect_limit_up_days(close, open_df, threshold)
    tail = limit_up.tail(window)
    return tail.sum().astype(int)


def filter_top_limit_up(
    codes: list[str],
    limit_up_counts: pd.Series,
    top_pct: float = 0.10,
) -> list[str]:
    """Keep top *top_pct* of *codes* ranked by limit-up count (descending).

    Stocks with zero limit-up days are always excluded.
    """
    sub = limit_up_counts.reindex(codes).fillna(0).astype(int)
    sub = sub[sub > 0].sort_values(ascending=False)
    if sub.empty:
        return []
    n_keep = max(1, int(len(sub) * top_pct))
    return sub.head(n_keep).index.tolist()


# ---------------------------------------------------------------------------
# Start-point scoring
# ---------------------------------------------------------------------------

def compute_start_point_scores(
    close: pd.DataFrame,
    open_df: pd.DataFrame,
    low_df: pd.DataFrame,
    codes: list[str],
    window: int,
    threshold: float = 0.095,
) -> pd.Series:
    """Compute start-point bias score for each code.

    Algorithm per stock:
      1. In the trailing *window*, find all proxy limit-up days.
      2. Take the most recent one.
      3. Scan backward from that day for the first day where close < open.
      4. Record that day's low as the *start price*.
      5. Score = current_close / start_price  (lower = closer to breakout origin).

    Stocks without a valid start-point are assigned NaN.
    """
    limit_up = _detect_limit_up_days(close, open_df, threshold)
    tail_limit = limit_up.tail(window)
    tail_close = close.tail(window)
    tail_open = open_df.tail(window)
    tail_low = low_df.tail(window)

    current_close = close.iloc[-1]
    scores: dict[str, float] = {}

    for code in codes:
        if code not in tail_limit.columns:
            continue
        lu_series = tail_limit[code]
        lu_dates = lu_series[lu_series].index
        if lu_dates.empty:
            continue

        latest_lu = lu_dates[-1]
        latest_lu_pos = tail_close.index.get_loc(latest_lu)

        start_price = np.nan
        for j in range(latest_lu_pos, -1, -1):
            dt_j = tail_close.index[j]
            c_j = tail_close.loc[dt_j, code]
            o_j = tail_open.loc[dt_j, code]
            if pd.notna(c_j) and pd.notna(o_j) and c_j < o_j:
                start_price = float(tail_low.loc[dt_j, code])
                break

        if pd.isna(start_price) or start_price <= 0:
            continue

        cur = current_close.get(code, np.nan)
        if pd.isna(cur) or cur <= 0:
            continue

        scores[code] = cur / start_price

    return pd.Series(scores, dtype=float)


# ---------------------------------------------------------------------------
# Main selection entry-point
# ---------------------------------------------------------------------------

@dataclass
class SelectionResult:
    """Output of the selection pipeline (compatible with downstream rank format)."""

    rank_df: pd.DataFrame  # columns: date, code, score, rank
    candidate_count_df: pd.DataFrame
    rebalance_dates: list[pd.Timestamp]
    used_codes: list[str]


def build_limit_up_screening_rank(
    db_path: Path,
    freq: str,
    universe_codes: list[str],
    cfg: LimitUpScreeningConfig,
    start_date: str | None = None,
    end_date: str | None = None,
    stock_names: dict[str, str] | None = None,
    listing_dates: dict[str, pd.Timestamp] | None = None,
) -> SelectionResult:
    """Build ranked stock list using the limit-up screening strategy.

    Pipeline per rebalance date:
      1. Universe filters (STAR/BJ, ST, new stock, limit-up/down, volume).
      2. Sort by smallest market-cap proxy (not available -- use full filtered pool).
      3. Count historical limit-up days in trailing window; keep top fraction.
      4. Score by start-point bias (ascending = preferred).
      5. Output top ``stock_num * topk_multiplier`` candidates with rank.

    Args:
        db_path: Path to SQLite market database.
        freq: Bar frequency (e.g. ``'1d'``).
        universe_codes: Pre-filtered universe code list.
        cfg: Strategy configuration.
        start_date: Optional start date for data loading.
        end_date: Optional end date for data loading.
        stock_names: Optional code-to-name map for ST filtering.
        listing_dates: Optional code-to-listing-date map.

    Returns:
        SelectionResult with rank_df, candidate_count_df, rebalance_dates, used_codes.
    """
    if cfg.stock_num <= 0:
        raise ValueError("stock_num must be positive")

    codes = sorted(set(universe_codes))[: cfg.max_codes_scan]
    ohlcv = load_ohlcv_panel(db_path=db_path, freq=freq, codes=codes, start=start_date, end=end_date)
    close = ohlcv["close"]
    open_df = ohlcv["open"]
    low_df = ohlcv["low"]
    volume = ohlcv["volume"]

    enough = close.count() >= cfg.min_bars
    eligible = enough[enough].index.tolist()
    if not eligible:
        raise RuntimeError("No codes satisfy min_bars in universe.")

    close = close[eligible]
    open_df = open_df[eligible]
    low_df = low_df[eligible]
    volume = volume[eligible]

    calendar = close.index.sort_values()
    if len(calendar) <= cfg.limit_days_window:
        raise RuntimeError("Not enough trading days for limit_days_window.")

    rebalance_dates = get_tuesday_rebalance_dates(calendar, cfg.rebalance_weekday)
    if not rebalance_dates:
        raise RuntimeError("No rebalance dates found in calendar.")

    rows_topk: list[dict[str, object]] = []
    rows_counts: list[dict[str, object]] = []

    for dt in rebalance_dates:
        dt_idx = calendar.get_loc(dt)
        if dt_idx < cfg.limit_days_window or dt_idx >= len(calendar) - 1:
            continue

        available = close.loc[dt].dropna().index.tolist()
        filtered = filter_kcbj_stock(available)
        if stock_names:
            filtered = filter_st_stock_by_name(filtered, stock_names)
        if listing_dates:
            filtered = filter_new_stock(filtered, listing_dates, dt, min_days=cfg.min_new_listing_days)

        if dt_idx >= 1:
            prev_dt = calendar[dt_idx - 1]
            filtered = filter_limit_up_down(
                filtered,
                close.loc[dt],
                close.loc[prev_dt],
                limit_pct=cfg.limit_up_threshold,
            )

        if cfg.require_positive_volume:
            vol = volume.loc[dt].fillna(0.0)
            filtered = [c for c in filtered if vol.get(c, 0) > 0]

        rows_counts.append({
            "date": dt,
            "candidate_count_raw": len(available),
            "candidate_count": len(filtered),
        })

        if len(filtered) < cfg.stock_num:
            continue

        pool = filtered[: cfg.init_pool_size]

        hist_start = max(0, dt_idx - cfg.limit_days_window)
        hist_close = close.iloc[hist_start : dt_idx + 1]
        hist_open = open_df.iloc[hist_start : dt_idx + 1]
        hist_low = low_df.iloc[hist_start : dt_idx + 1]

        lu_counts = count_limit_up_history(
            hist_close[pool], hist_open[pool],
            window=cfg.limit_days_window,
            threshold=cfg.limit_up_threshold,
        )
        screened = filter_top_limit_up(pool, lu_counts, top_pct=cfg.top_pct_limit_up)
        if len(screened) < cfg.stock_num:
            continue

        sp_scores = compute_start_point_scores(
            hist_close, hist_open, hist_low,
            codes=screened,
            window=cfg.limit_days_window,
            threshold=cfg.limit_up_threshold,
        )
        sp_scores = sp_scores.dropna().sort_values(ascending=True)

        top_count = cfg.stock_num * cfg.topk_multiplier
        top = sp_scores.head(top_count)

        for rank, (code, score) in enumerate(top.items(), start=1):
            rows_topk.append({
                "date": dt,
                "code": str(code).zfill(6),
                "score": float(score),
                "rank": rank,
            })

    rank_df = pd.DataFrame(rows_topk)
    candidate_df = pd.DataFrame(rows_counts)

    if rank_df.empty:
        raise RuntimeError("Rank dataframe is empty. Check coverage / min_bars / limit_days_window.")

    rank_df["date"] = pd.to_datetime(rank_df["date"])
    if not candidate_df.empty:
        candidate_df["date"] = pd.to_datetime(candidate_df["date"])

    return SelectionResult(
        rank_df=rank_df.sort_values(["date", "rank", "code"]).reset_index(drop=True),
        candidate_count_df=candidate_df.sort_values("date").reset_index(drop=True) if not candidate_df.empty else candidate_df,
        rebalance_dates=rebalance_dates,
        used_codes=eligible,
    )
