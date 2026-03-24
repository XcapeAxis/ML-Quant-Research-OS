from __future__ import annotations

from pathlib import Path

import pandas as pd

from quant_mvp.data_quality import clean_symbol_bars, clean_table_ready
from quant_mvp.db import upsert_bars


def _bars(rows: list[dict[str, object]]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def test_clean_symbol_bars_drops_invalid_price_and_volume() -> None:
    raw = _bars(
        [
            {
                "symbol": "000001",
                "datetime": "2024-01-02",
                "freq": "1d",
                "open": 10.0,
                "high": 10.5,
                "low": 9.8,
                "close": 10.2,
                "volume": 1000,
            },
            {
                "symbol": "000001",
                "datetime": "2024-01-03",
                "freq": "1d",
                "open": 0.0,
                "high": 10.6,
                "low": 10.0,
                "close": 10.4,
                "volume": 1000,
            },
            {
                "symbol": "000001",
                "datetime": "2024-01-04",
                "freq": "1d",
                "open": 10.4,
                "high": 10.8,
                "low": 10.1,
                "close": 10.5,
                "volume": 0,
            },
        ],
    )

    clean_df, issues_df, stats = clean_symbol_bars(raw, None)

    assert clean_df["datetime"].tolist() == ["2024-01-02"]
    assert set(issues_df["issue_code"]) == {"invalid_price", "invalid_volume"}
    assert stats["kept_rows"] == 1
    assert stats["dropped_rows"] == 2


def test_clean_symbol_bars_repairs_ohlc_envelope() -> None:
    raw = _bars(
        [
            {
                "symbol": "000001",
                "datetime": "2024-01-02",
                "freq": "1d",
                "open": 10.0,
                "high": 9.5,
                "low": 10.4,
                "close": 11.0,
                "volume": 1000,
            },
        ],
    )

    clean_df, issues_df, stats = clean_symbol_bars(raw, None)

    assert clean_df.loc[0, "high"] == 11.0
    assert clean_df.loc[0, "low"] == 10.0
    assert set(issues_df["issue_code"]) == {"repair_high", "repair_low"}
    assert stats["repaired_rows"] == 1


def test_clean_symbol_bars_drops_hard_return_using_prev_clean_close() -> None:
    raw = _bars(
        [
            {
                "symbol": "000001",
                "datetime": "2024-01-02",
                "freq": "1d",
                "open": 10.0,
                "high": 10.1,
                "low": 9.9,
                "close": 10.0,
                "volume": 1000,
            },
            {
                "symbol": "000001",
                "datetime": "2024-01-03",
                "freq": "1d",
                "open": 15.0,
                "high": 15.2,
                "low": 14.8,
                "close": 15.0,
                "volume": 1200,
            },
            {
                "symbol": "000001",
                "datetime": "2024-01-04",
                "freq": "1d",
                "open": 11.8,
                "high": 12.0,
                "low": 11.7,
                "close": 12.0,
                "volume": 1300,
            },
        ],
    )

    clean_df, issues_df, stats = clean_symbol_bars(raw, None)

    assert clean_df["datetime"].tolist() == ["2024-01-02", "2024-01-04"]
    assert "hard_daily_return" in set(issues_df["issue_code"])
    assert stats["kept_rows"] == 2
    assert stats["dropped_rows"] == 1


def test_clean_symbol_bars_keeps_warn_level_anomalies_and_records_issues() -> None:
    raw = _bars(
        [
            {
                "symbol": "000001",
                "datetime": "2024-01-02",
                "freq": "1d",
                "open": 10.0,
                "high": 10.1,
                "low": 9.9,
                "close": 10.0,
                "volume": 100.0,
            },
            {
                "symbol": "000001",
                "datetime": "2024-01-03",
                "freq": "1d",
                "open": 12.1,
                "high": 12.6,
                "low": 9.8,
                "close": 12.2,
                "volume": 10000.0,
            },
        ],
    )

    clean_df, issues_df, stats = clean_symbol_bars(raw, None)

    assert clean_df["datetime"].tolist() == ["2024-01-02", "2024-01-03"]
    issue_codes = set(issues_df["issue_code"])
    assert {"warn_daily_return", "warn_open_gap", "warn_intraday_range", "warn_volume_spike"}.issubset(issue_codes)
    assert stats["warned_rows"] == 1


def test_clean_table_ready_requires_full_raw_coverage(tmp_path: Path) -> None:
    db_path = tmp_path / "quality.db"
    raw = _bars(
        [
            {
                "symbol": "000001",
                "datetime": "2024-01-02",
                "freq": "1d",
                "open": 10.0,
                "high": 10.5,
                "low": 9.8,
                "close": 10.2,
                "volume": 1000.0,
            },
            {
                "symbol": "600000",
                "datetime": "2024-01-02",
                "freq": "1d",
                "open": 11.0,
                "high": 11.5,
                "low": 10.8,
                "close": 11.2,
                "volume": 1200.0,
            },
        ],
    )
    clean = raw.iloc[[0]].copy()

    upsert_bars(db_path, raw)
    upsert_bars(db_path, clean, table_name="bars_clean")

    assert clean_table_ready(db_path, freq="1d") is False
