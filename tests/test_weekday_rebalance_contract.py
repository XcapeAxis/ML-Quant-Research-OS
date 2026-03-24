from __future__ import annotations

import pandas as pd

from quant_mvp.ranking import get_rebalance_dates_tuesday


def test_weekday_rebalance_contract() -> None:
    calendar = pd.date_range("2026-01-05", periods=15, freq="B")
    dates = get_rebalance_dates_tuesday(calendar, lookback=0, weekday=1)
    assert dates
    assert all(item.weekday() == 1 for item in dates)
    assert pd.Timestamp("2026-01-06") in dates
    assert pd.Timestamp("2026-01-07") not in dates
