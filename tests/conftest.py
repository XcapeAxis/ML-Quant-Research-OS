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


@pytest.fixture()
def synthetic_project(tmp_path: Path):
    project = "test_smoke_project"
    paths = resolve_project_paths(project)

    # clean previous run artifacts if any
    if paths.project_data_dir.exists():
        shutil.rmtree(paths.project_data_dir)
    if paths.artifacts_dir.exists():
        shutil.rmtree(paths.artifacts_dir)
    if paths.logs_dir.exists():
        shutil.rmtree(paths.logs_dir)

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
