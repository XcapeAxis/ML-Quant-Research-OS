from __future__ import annotations

import pandas as pd


def build_trading_calendar(index: pd.Index | pd.Series | list[pd.Timestamp]) -> pd.DatetimeIndex:
    if isinstance(index, pd.Series):
        values = index.dropna().tolist()
    else:
        values = list(index)
    calendar = pd.to_datetime(values)
    return pd.DatetimeIndex(sorted(set(calendar)))


def weekday_dates(calendar: pd.DatetimeIndex, weekday: int) -> list[pd.Timestamp]:
    return [pd.Timestamp(item) for item in calendar if pd.Timestamp(item).weekday() == weekday]


def align_panel_to_calendar(panel: pd.DataFrame, calendar: pd.DatetimeIndex) -> pd.DataFrame:
    aligned = panel.copy()
    aligned.index = pd.to_datetime(aligned.index)
    return aligned.reindex(calendar)
