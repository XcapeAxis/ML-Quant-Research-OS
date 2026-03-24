from __future__ import annotations

from pathlib import Path

import pandas as pd

from quant_mvp.db import coverage_report, list_db_codes, load_close_volume_panel, upsert_bars


def _make_rows(close_value: float, symbol: str = "000001") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "symbol": symbol,
                "datetime": "2024-01-02",
                "freq": "1d",
                "open": close_value - 0.1,
                "high": close_value + 0.1,
                "low": close_value - 0.2,
                "close": close_value,
                "volume": 1000.0,
            },
        ],
    )


def test_load_close_volume_panel_prefers_clean_when_available(tmp_path: Path) -> None:
    db_path = tmp_path / "modes.db"
    upsert_bars(db_path, _make_rows(10.0))
    upsert_bars(db_path, _make_rows(11.0), table_name="bars_clean")

    close, _ = load_close_volume_panel(db_path, "1d", ["000001"], data_mode="auto")

    assert float(close.iloc[0, 0]) == 11.0


def test_load_close_volume_panel_auto_falls_back_to_raw_without_clean_table(tmp_path: Path) -> None:
    db_path = tmp_path / "modes.db"
    upsert_bars(db_path, _make_rows(10.0))

    close, _ = load_close_volume_panel(db_path, "1d", ["000001"], data_mode="auto")

    assert float(close.iloc[0, 0]) == 10.0


def test_auto_mode_uses_clean_per_code_and_raw_for_missing_codes(tmp_path: Path) -> None:
    db_path = tmp_path / "modes.db"
    upsert_bars(db_path, _make_rows(10.0, symbol="000001"))
    upsert_bars(db_path, _make_rows(20.0, symbol="600000"))
    upsert_bars(db_path, _make_rows(11.0, symbol="000001"), table_name="bars_clean")

    close, _ = load_close_volume_panel(db_path, "1d", ["000001", "600000"], data_mode="auto")

    assert float(close.loc[pd.Timestamp("2024-01-02"), "000001"]) == 11.0
    assert float(close.loc[pd.Timestamp("2024-01-02"), "600000"]) == 20.0
    assert list_db_codes(db_path, "1d", data_mode="auto") == {"000001", "600000"}


def test_coverage_report_supports_explicit_clean_and_raw_modes(tmp_path: Path) -> None:
    db_path = tmp_path / "modes.db"
    upsert_bars(db_path, _make_rows(10.0))
    upsert_bars(db_path, _make_rows(11.0), table_name="bars_clean")

    raw_df = coverage_report(db_path, "1d", ["000001"], data_mode="raw")
    clean_df = coverage_report(db_path, "1d", ["000001"], data_mode="clean")

    assert int(raw_df.loc[0, "bars_count"]) == 1
    assert int(clean_df.loc[0, "bars_count"]) == 1
