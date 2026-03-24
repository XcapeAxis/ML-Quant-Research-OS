from __future__ import annotations

import pandas as pd

from ..contracts import ProviderFetchRequest
from .base import MarketDataProvider


def normalize_akshare_frame(df: pd.DataFrame, symbol: str, freq: str) -> pd.DataFrame:
    aliases: dict[str, set[str]] = {
        "datetime": {"日期", "date", "datetime", "time"},
        "open": {"开盘", "open"},
        "high": {"最高", "high"},
        "low": {"最低", "low"},
        "close": {"收盘", "close"},
        "volume": {"成交量", "volume"},
    }
    rename_map: dict[str, str] = {}
    for col in df.columns:
        raw = str(col).strip()
        low = raw.lower()
        for canonical, names in aliases.items():
            lowered = {item.lower() for item in names}
            if raw in names or low in lowered:
                rename_map[col] = canonical
                break

    normalized = df.rename(columns=rename_map)
    required = {"datetime", "open", "high", "low", "close"}
    if not required.issubset(normalized.columns):
        return pd.DataFrame()
    if "volume" not in normalized.columns:
        normalized["volume"] = 0.0

    out = normalized[["datetime", "open", "high", "low", "close", "volume"]].copy()
    out["datetime"] = pd.to_datetime(out["datetime"], errors="coerce").dt.strftime("%Y-%m-%d")
    out["symbol"] = str(symbol).zfill(6)
    out["freq"] = freq
    for col in ["open", "high", "low", "close", "volume"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    return out.dropna(subset=["datetime", "open", "high", "low", "close"]).reset_index(drop=True)


class AkshareDailyProvider(MarketDataProvider):
    name = "akshare"

    def __init__(self, *, timeout_seconds: float = 30.0) -> None:
        self.timeout_seconds = float(timeout_seconds)

    def normalize_symbol(self, symbol: str) -> str:
        return str(symbol).zfill(6)

    def fetch_daily_bars(self, request: ProviderFetchRequest) -> pd.DataFrame:
        try:
            import akshare as ak
        except ImportError as exc:
            raise RuntimeError("akshare is required to fetch daily bars") from exc

        frame = ak.stock_zh_a_hist(
            symbol=self.normalize_symbol(request.symbol),
            period="daily",
            start_date=request.start_date.replace("-", ""),
            end_date=request.end_date.replace("-", ""),
            adjust=request.adjust,
            timeout=self.timeout_seconds,
        )
        if frame is None or frame.empty:
            return pd.DataFrame()
        return normalize_akshare_frame(frame, request.symbol, request.frequency)
