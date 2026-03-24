from __future__ import annotations

from pathlib import Path
import shutil
import sys

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quant_mvp.db import upsert_bars
from quant_mvp.project import resolve_project_paths


def _make_bars(codes: list[str], start: str, periods: int) -> pd.DataFrame:
    dates = pd.date_range(start=start, periods=periods, freq="B")
    rows: list[dict[str, object]] = []
    for idx, code in enumerate(codes):
        price = 10.0 + idx
        for i, dt in enumerate(dates):
            price = price * (1.0 + 0.001 * (idx + 1))
            rows.append(
                {
                    "symbol": str(code).zfill(6),
                    "datetime": dt.strftime("%Y-%m-%d"),
                    "freq": "1d",
                    "open": price * 0.99,
                    "high": price * 1.01,
                    "low": price * 0.98,
                    "close": price,
                    "volume": 100000 + 1000 * i + idx,
                },
            )
    return pd.DataFrame(rows)


def _make_limit_up_bars(codes: list[str], start: str, periods: int) -> pd.DataFrame:
    dates = pd.date_range(start=start, periods=periods, freq="B")
    rows: list[dict[str, object]] = []
    for idx, code in enumerate(codes):
        close_price = 10.0 + idx
        jump_interval = 12 + idx * 3
        for i, dt in enumerate(dates):
            prev_close = close_price
            if i > 40 and i % jump_interval == jump_interval - 1:
                open_price = prev_close * 1.03
                close_price = prev_close * 0.98
            elif i > 40 and i % jump_interval == 0:
                open_price = prev_close * 1.01
                close_price = prev_close * 1.10
            else:
                drift = 0.0015 + idx * 0.0002
                open_price = prev_close * (1.0 + drift / 3.0)
                close_price = prev_close * (1.0 + drift)

            high = max(open_price, close_price) * 1.01
            low = min(open_price, close_price) * 0.99
            volume = 100000 + 500 * i + idx * 100
            if code == codes[-1] and i % 19 == 0:
                volume = 0.0
            rows.append(
                {
                    "symbol": str(code).zfill(6),
                    "datetime": dt.strftime("%Y-%m-%d"),
                    "freq": "1d",
                    "open": round(open_price, 4),
                    "high": round(high, 4),
                    "low": round(low, 4),
                    "close": round(close_price, 4),
                    "volume": float(volume),
                },
            )
    return pd.DataFrame(rows)


def _cleanup_project(paths) -> None:
    for path in [paths.project_data_dir, paths.artifacts_dir, paths.logs_dir, paths.memory_dir]:
        if path.exists():
            shutil.rmtree(path)


@pytest.fixture(autouse=True)
def preserve_tracked_docs():
    tracked_docs = [
        ROOT / "docs" / "SYSTEM_AUDIT.md",
        ROOT / "docs" / "FAILURE_MODES.md",
        ROOT / "docs" / "DECISION_LOG.md",
    ]
    snapshots = {
        path: (path.read_text(encoding="utf-8") if path.exists() else None)
        for path in tracked_docs
    }

    yield

    for path, content in snapshots.items():
        if content is None:
            if path.exists():
                path.unlink()
        else:
            path.write_text(content, encoding="utf-8")


@pytest.fixture()
def synthetic_project(tmp_path: Path):
    project = "test_smoke_project"
    paths = resolve_project_paths(project)
    _cleanup_project(paths)

    paths.ensure_dirs()
    universe_codes = ["000001", "000002", "000003"]
    with open(paths.universe_path, "w", encoding="utf-8") as handle:
        for code in universe_codes:
            handle.write(f"{code}\n")

    db_path = tmp_path / "market_test.db"
    bars = _make_bars(codes=universe_codes + ["999999"], start="2020-01-01", periods=120)
    upsert_bars(db_path=db_path, bars_df=bars)

    config_path = tmp_path / "test_config.json"
    config_path.write_text(
        """
{
  "db_path": "%s",
  "freq": "1d",
  "lookback": 5,
  "rebalance_every": 5,
  "topk": 5,
  "topn_max": 5,
  "min_bars": 20,
  "max_codes_scan": 100,
  "cash": 1000000,
  "commission": 0.0003,
  "stamp_duty": 0.001,
  "slippage": 0.0005,
  "risk_free_rate": 0.03,
  "baselines": {
    "benchmark_code": "000001",
    "enable_equal_weight": true,
    "random_trials": 10,
    "random_seed": 42
  },
  "cost_sweep": {
    "commission_grid": [0.0001, 0.0002, 0.0003, 0.0005, 0.001],
    "slippage_grid": [0.0001, 0.0003, 0.0005, 0.001, 0.002]
  },
  "walk_forward": {
    "windows": [
      { "name": "2020H1", "start": "2020-01-01", "end": "2020-06-30" },
      { "name": "2020H2", "start": "2020-07-01", "end": "2020-12-31" }
    ]
  }
}
        """
        % str(db_path).replace("\\", "/"),
        encoding="utf-8",
    )

    yield {
        "project": project,
        "paths": paths,
        "config_path": config_path,
        "db_path": db_path,
        "universe_codes": universe_codes,
    }

    _cleanup_project(paths)


@pytest.fixture()
def limit_up_project(tmp_path: Path):
    project = "test_limit_up_project"
    paths = resolve_project_paths(project)
    _cleanup_project(paths)

    paths.ensure_dirs()
    universe_codes = ["000001", "000002", "000003", "000004", "000005", "000006"]
    with open(paths.universe_path, "w", encoding="utf-8") as handle:
        for code in universe_codes:
            handle.write(f"{code}\n")

    db_path = tmp_path / "limit_up_market.db"
    bars = _make_limit_up_bars(codes=universe_codes + ["999999"], start="2020-01-01", periods=180)
    upsert_bars(db_path=db_path, bars_df=bars)

    config_path = tmp_path / "limit_up_config.json"
    config_path.write_text(
        """
{
  "db_path": "%s",
  "freq": "1d",
  "strategy_mode": "limit_up_screening",
  "stock_num": 3,
  "topk": 3,
  "topn_max": 3,
  "min_bars": 40,
  "max_codes_scan": 100,
  "cash": 1000000,
  "commission": 0.0001,
  "stamp_duty": 0.0005,
  "slippage": 0.001,
  "risk_free_rate": 0.03,
  "calendar_code": "000001",
  "start_date": "2020-01-01",
  "end_date": "2020-09-30",
  "stock_num": 3,
  "limit_days_window": 60,
  "top_pct_limit_up": 0.5,
  "limit_up_threshold": 0.095,
  "init_pool_size": 6,
  "rebalance_weekday": 1,
  "topk_multiplier": 2,
  "stoploss_limit": 0.91,
  "take_profit_ratio": 2.0,
  "market_stoploss_ratio": 0.93,
  "loss_black_days": 10,
  "no_trade_months": [],
  "min_commission": 5.0,
  "tradability": {
    "require_positive_volume": true,
    "min_volume": 1.0
  },
  "baselines": {
    "benchmark_code": "000001",
    "enable_equal_weight": true,
    "random_trials": 10,
    "random_seed": 42
  },
  "cost_sweep": {
    "commission_grid": [0.0001, 0.0003],
    "slippage_grid": [0.001, 0.002]
  },
  "walk_forward": {
    "windows": [
      { "name": "2020H1", "start": "2020-01-01", "end": "2020-06-30" },
      { "name": "2020H2", "start": "2020-07-01", "end": "2020-09-30" }
    ]
  }
}
        """
        % str(db_path).replace("\\", "/"),
        encoding="utf-8",
    )

    yield {
        "project": project,
        "paths": paths,
        "config_path": config_path,
        "db_path": db_path,
        "universe_codes": universe_codes,
    }

    _cleanup_project(paths)
