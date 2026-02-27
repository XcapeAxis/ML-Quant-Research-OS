"""Generate synthetic OHLCV bars for pipeline testing.

Produces realistic A-share-like data with occasional limit-up events,
regime changes, and varying volatility. Writes directly to the SQLite DB.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quant_mvp.db import upsert_bars
from quant_mvp.project import resolve_project_paths


def _trading_calendar(start: str, end: str) -> pd.DatetimeIndex:
    """Generate weekday-only trading calendar."""
    dates = pd.bdate_range(start, end)
    return dates


def _generate_stock(
    code: str,
    dates: pd.DatetimeIndex,
    initial_price: float,
    daily_drift: float,
    daily_vol: float,
    limit_up_prob: float,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """Generate OHLCV for a single stock."""
    n = len(dates)
    returns = rng.normal(daily_drift, daily_vol, n)

    # Inject limit-up events
    limit_up_mask = rng.random(n) < limit_up_prob
    returns[limit_up_mask] = rng.uniform(0.095, 0.10, limit_up_mask.sum())

    # Occasional limit-down
    limit_down_mask = rng.random(n) < (limit_up_prob * 0.3)
    returns[limit_down_mask] = rng.uniform(-0.10, -0.095, limit_down_mask.sum())

    close_prices = initial_price * np.cumprod(1 + returns)
    close_prices = np.maximum(close_prices, 1.0)

    intraday_range = rng.uniform(0.005, 0.03, n)
    high = close_prices * (1 + intraday_range * rng.uniform(0.3, 1.0, n))
    low = close_prices * (1 - intraday_range * rng.uniform(0.3, 1.0, n))
    open_prices = close_prices * (1 + rng.normal(0, 0.005, n))
    volume = rng.lognormal(15, 1.5, n).astype(int)

    return pd.DataFrame({
        "symbol": code,
        "datetime": [d.strftime("%Y-%m-%d") for d in dates],
        "freq": "1d",
        "open": np.round(open_prices, 2),
        "high": np.round(high, 2),
        "low": np.round(low, 2),
        "close": np.round(close_prices, 2),
        "volume": volume,
    })


def generate_bars(
    n_stocks: int = 200,
    start: str = "2023-01-01",
    end: str = "2026-02-28",
    seed: int = 42,
) -> pd.DataFrame:
    """Generate synthetic bars for multiple stocks."""
    rng = np.random.Generator(np.random.PCG64(seed))
    dates = _trading_calendar(start, end)

    all_frames = []
    codes_pool = [f"{i:06d}" for i in range(1, n_stocks + 1)]

    for i, code in enumerate(codes_pool):
        initial_price = rng.uniform(5, 50)
        daily_drift = rng.normal(0.0003, 0.0005)
        daily_vol = rng.uniform(0.015, 0.04)
        # ~5-15% of stocks are "hot" with higher limit-up frequency
        if i < n_stocks * 0.10:
            limit_up_prob = rng.uniform(0.02, 0.05)
            daily_drift = rng.uniform(0.001, 0.003)
        elif i < n_stocks * 0.30:
            limit_up_prob = rng.uniform(0.005, 0.02)
        else:
            limit_up_prob = rng.uniform(0.001, 0.005)

        df = _generate_stock(code, dates, initial_price, daily_drift, daily_vol, limit_up_prob, rng)
        all_frames.append(df)

    return pd.concat(all_frames, ignore_index=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic OHLCV bars.")
    parser.add_argument("--project", type=str, default="2026Q1_limit_up")
    parser.add_argument("--n-stocks", type=int, default=200)
    parser.add_argument("--start", type=str, default="2023-01-01")
    parser.add_argument("--end", type=str, default="2026-02-28")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    paths = resolve_project_paths(args.project)
    db_path = paths.db_path

    print(f"Generating {args.n_stocks} stocks, {args.start} to {args.end} ...")
    bars = generate_bars(args.n_stocks, args.start, args.end, args.seed)
    print(f"Total rows: {len(bars)}")

    rows = upsert_bars(db_path, bars)
    print(f"Upserted {rows} rows to {db_path}")

    # Also write the codes as universe
    codes = sorted(bars["symbol"].unique().tolist())
    paths.ensure_dirs()
    with open(paths.universe_path, "w", encoding="utf-8") as f:
        for code in codes:
            f.write(f"{code}\n")
    print(f"Universe written: {paths.universe_path} ({len(codes)} codes)")


if __name__ == "__main__":
    main()
