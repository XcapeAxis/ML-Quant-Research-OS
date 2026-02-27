from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

from .db import load_close_volume_panel


@dataclass
class SelectionConfig:
    """Configuration for stock selection."""

    stock_num: int = 6
    rebalance_weekday: int = 1  # 0=Monday, 1=Tuesday
    lookback: int = 60
    topk_multiplier: int = 2
    min_bars: int = 20
    max_codes_scan: int = 1000
    require_positive_volume: bool = True


def get_tuesday_rebalance_dates(
    calendar: pd.DatetimeIndex,
    weekday: int = 1,
) -> list[pd.Timestamp]:
    """Get rebalance dates that fall on specified weekday (default Tuesday).

    Args:
        calendar: Trading calendar DatetimeIndex
        weekday: Day of week (0=Monday, 1=Tuesday, ..., 6=Sunday)

    Returns:
        List of timestamps that match the specified weekday
    """
    return [pd.Timestamp(dt) for dt in calendar if dt.weekday() == weekday]


def filter_kcbj_stock(codes: list[str]) -> list[str]:
    """Filter out STAR Market (科创板) and Beijing Exchange (北交所) stocks.

    Args:
        codes: List of stock codes

    Returns:
        Filtered list excluding codes starting with '4', '8', or '68'
    """
    return [
        code for code in codes
        if not (code.startswith("4") or code.startswith("8") or code.startswith("68"))
    ]


def filter_st_stock_by_name(codes: list[str], names: dict[str, str] | None = None) -> list[str]:
    """Filter out ST and delisting stocks by name patterns.

    Args:
        codes: List of stock codes
        names: Optional mapping of code to name for ST filtering

    Returns:
        Filtered list excluding ST stocks
    """
    if names is None:
        return codes
    return [
        code for code in codes
        if code in names
        and "ST" not in names[code]
        and "*" not in names[code]
        and "退" not in names[code]
    ]


def filter_new_stock(
    codes: list[str],
    listing_dates: dict[str, pd.Timestamp],
    current_date: pd.Timestamp,
    min_days: int = 375,
) -> list[str]:
    """Filter out newly listed stocks (次新股).

    Args:
        codes: List of stock codes
        listing_dates: Mapping of code to listing date
        current_date: Current date for comparison
        min_days: Minimum days since listing (default 375 days)

    Returns:
        Filtered list excluding new stocks
    """
    result = []
    for code in codes:
        if code in listing_dates:
            days_since_listing = (current_date - listing_dates[code]).days
            if days_since_listing >= min_days:
                result.append(code)
        else:
            # If no listing date info, include by default
            result.append(code)
    return result


def filter_limit_up_down(
    codes: list[str],
    close: pd.Series,
    prev_close: pd.Series,
    limit_pct: float = 0.099,
) -> list[str]:
    """Filter out stocks that are limit-up or limit-down.

    Approximates limit up/down using daily return threshold since
    actual limit prices may not be available.

    Args:
        codes: List of stock codes to filter
        close: Current close prices
        prev_close: Previous close prices
        limit_pct: Return threshold to consider as limit (default 9.9%)

    Returns:
        Filtered list excluding limit-up and limit-down stocks
    """
    result = []
    for code in codes:
        if code not in close or code not in prev_close:
            continue
        if pd.isna(close[code]) or pd.isna(prev_close[code]) or prev_close[code] == 0:
            continue
        ret = close[code] / prev_close[code] - 1.0
        if abs(ret) < limit_pct:
            result.append(code)
    return result


def compute_momentum_score(
    close: pd.DataFrame,
    lookback: int = 60,
) -> pd.Series:
    """Compute momentum score as percentage change over lookback period.

    Args:
        close: Close price DataFrame (dates x codes)
        lookback: Number of periods for momentum calculation

    Returns:
        Series of momentum scores indexed by code
    """
    momentum = close.pct_change(lookback, fill_method=None)
    return momentum.iloc[-1] if not momentum.empty else pd.Series(dtype=float)


def compute_start_point_score(
    close: pd.DataFrame,
    high: pd.DataFrame | None = None,
    lookback: int = 60,
) -> pd.Series:
    """Compute start-point score based on price relative to recent low.

    This is a simplified approximation of the "start point" concept from
    the original strategy. Returns lower values for stocks closer to
    their recent lows (potential breakout candidates).

    Args:
        close: Close price DataFrame (dates x codes)
        high: Optional high price DataFrame
        lookback: Number of periods for calculation

    Returns:
        Series of start-point scores indexed by code (lower = closer to low)
    """
    recent_low = close.tail(lookback).min()
    current = close.iloc[-1]
    # Ratio of current price to recent low (lower = closer to breakout point)
    ratio = current / recent_low.replace(0, np.nan)
    return ratio


def rank_by_momentum_and_start_point(
    close: pd.DataFrame,
    high: pd.DataFrame | None = None,
    momentum_lookback: int = 60,
    start_point_lookback: int = 60,
    momentum_weight: float = 0.6,
) -> pd.Series:
    """Rank stocks by combined momentum and start-point scores.

    Args:
        close: Close price DataFrame (dates x codes)
        high: Optional high price DataFrame
        momentum_lookback: Periods for momentum calculation
        start_point_lookback: Periods for start-point calculation
        momentum_weight: Weight for momentum vs start-point (0-1)

    Returns:
        Series of combined scores indexed by code (higher = better)
    """
    momentum = compute_momentum_score(close, momentum_lookback)
    start_point = compute_start_point_score(close, high, start_point_lookback)

    # Normalize both scores to 0-1 range
    momentum_norm = (momentum - momentum.min()) / (momentum.max() - momentum.min() + 1e-10)
    start_point_norm = (start_point - start_point.min()) / (start_point.max() - start_point.min() + 1e-10)

    # Combined score: higher momentum + lower start_point (closer to low)
    # Invert start_point so lower values (closer to low) get higher scores
    combined = momentum_weight * momentum_norm + (1 - momentum_weight) * (1 - start_point_norm)

    return combined.sort_values(ascending=False)


@dataclass
class SelectionResult:
    """Result of stock selection process."""

    rank_df: pd.DataFrame
    rebalance_dates: list[pd.Timestamp]
    used_codes: list[str]


def build_jq_selection(
    db_path,
    freq: str,
    universe_codes: list[str],
    cfg: SelectionConfig,
    start_date: str | None = None,
    end_date: str | None = None,
    stock_names: dict[str, str] | None = None,
    listing_dates: dict[str, pd.Timestamp] | None = None,
) -> SelectionResult:
    """Build stock selection using momentum + start-point ranking.

    This implements a simplified version of the original strategy's
    selection logic, adapted for local SQLite data.

    Args:
        db_path: Path to SQLite database
        freq: Data frequency (e.g., '1d')
        universe_codes: List of candidate stock codes
        cfg: Selection configuration
        start_date: Optional start date filter
        end_date: Optional end date filter
        stock_names: Optional mapping of code to name for ST filtering
        listing_dates: Optional mapping of code to listing date

    Returns:
        SelectionResult containing ranked stocks and rebalance dates
    """
    if cfg.stock_num <= 0:
        raise ValueError("stock_num must be positive")

    # Load price data
    codes = sorted(set(universe_codes))[:cfg.max_codes_scan]
    close, volume = load_close_volume_panel(
        db_path=db_path, freq=freq, codes=codes, start=start_date, end=end_date,
    )

    # Filter by minimum bars requirement
    enough_history = close.count() >= cfg.min_bars
    eligible_codes = enough_history[enough_history].index.tolist()
    if not eligible_codes:
        raise RuntimeError("No codes satisfy min_bars in universe.")

    close = close[eligible_codes]
    volume = volume[eligible_codes]

    # Get Tuesday rebalance dates
    calendar = close.index.sort_values()
    if len(calendar) <= cfg.lookback:
        raise RuntimeError("Not enough trading days for lookback.")

    rebalance_dates = get_tuesday_rebalance_dates(calendar, cfg.rebalance_weekday)

    rows_topk: list[dict[str, object]] = []

    for dt in rebalance_dates:
        # Get available codes for this date
        available_codes = close.loc[dt].dropna().index.tolist()

        # Apply filters
        filtered_codes = available_codes

        # Filter KCB/BJ stocks
        filtered_codes = filter_kcbj_stock(filtered_codes)

        # Filter ST stocks if names provided
        if stock_names:
            filtered_codes = filter_st_stock_by_name(filtered_codes, stock_names)

        # Filter new stocks if listing dates provided
        if listing_dates:
            filtered_codes = filter_new_stock(
                filtered_codes, listing_dates, dt, min_days=375,
            )

        # Filter by volume if required
        if cfg.require_positive_volume:
            vol = volume.loc[dt].fillna(0.0)
            filtered_codes = [c for c in filtered_codes if vol.get(c, 0) > 0]

        if len(filtered_codes) < cfg.stock_num * cfg.topk_multiplier:
            continue

        # Get historical data for scoring
        dt_idx = close.index.get_loc(dt)
        hist_start = max(0, dt_idx - cfg.lookback)
        hist_close = close.iloc[hist_start:dt_idx + 1][filtered_codes]

        if hist_close.empty or len(hist_close) < cfg.min_bars:
            continue

        # Rank by momentum + start-point
        scores = rank_by_momentum_and_start_point(
            hist_close,
            momentum_lookback=cfg.lookback,
            start_point_lookback=cfg.lookback,
        )

        # Take top 2*stock_num
        top_count = cfg.stock_num * cfg.topk_multiplier
        top = scores.head(top_count)

        for rank, (code, score) in enumerate(top.items(), start=1):
            rows_topk.append(
                {
                    "date": dt,
                    "code": str(code).zfill(6),
                    "score": float(score),
                    "rank": rank,
                },
            )

    rank_df = pd.DataFrame(rows_topk)

    if rank_df.empty:
        raise RuntimeError("Rank dataframe is empty. Check coverage/min_bars settings.")

    rank_df["date"] = pd.to_datetime(rank_df["date"])

    return SelectionResult(
        rank_df=rank_df.sort_values(["date", "rank", "code"]).reset_index(drop=True),
        rebalance_dates=rebalance_dates,
        used_codes=eligible_codes,
    )


def rank_targets_jq(rank_df: pd.DataFrame, stock_num: int) -> dict[pd.Timestamp, list[str]]:
    """Convert rank DataFrame to targets dictionary.

    Args:
        rank_df: Rank DataFrame with columns date, code, rank
        stock_num: Number of stocks to select per rebalance

    Returns:
        Dictionary mapping dates to lists of stock codes
    """
    out: dict[pd.Timestamp, list[str]] = {}
    for dt, group in rank_df.groupby("date"):
        chosen = group[group["rank"] <= stock_num]["code"].astype(str).str.zfill(6).tolist()
        out[pd.Timestamp(dt)] = chosen
    return out
