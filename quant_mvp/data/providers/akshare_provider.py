from __future__ import annotations

from contextlib import contextmanager

import pandas as pd

from ..contracts import ProviderFetchRequest
from .base import MarketDataProvider


_EASTMONEY_ALIASES: dict[str, set[str]] = {
    "datetime": {"日期", "date", "datetime", "time"},
    "open": {"开盘", "open"},
    "high": {"最高", "high"},
    "low": {"最低", "low"},
    "close": {"收盘", "close"},
    "volume": {"成交量", "volume"},
}


def normalize_akshare_frame(df: pd.DataFrame, symbol: str, freq: str) -> pd.DataFrame:
    rename_map: dict[str, str] = {}
    for col in df.columns:
        raw = str(col).strip()
        lowered = raw.lower()
        for canonical, aliases in _EASTMONEY_ALIASES.items():
            if raw in aliases or lowered in {item.lower() for item in aliases}:
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


def normalize_akshare_tx_frame(df: pd.DataFrame, symbol: str, freq: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    normalized = df.rename(columns={"date": "datetime", "amount": "volume"})
    required = {"datetime", "open", "high", "low", "close", "volume"}
    if not required.issubset(normalized.columns):
        return pd.DataFrame()

    out = normalized[["datetime", "open", "high", "low", "close", "volume"]].copy()
    out["datetime"] = pd.to_datetime(out["datetime"], errors="coerce").dt.strftime("%Y-%m-%d")
    out["symbol"] = str(symbol).zfill(6)
    out["freq"] = freq
    for col in ["open", "high", "low", "close", "volume"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    return out.dropna(subset=["datetime", "open", "high", "low", "close", "volume"]).reset_index(drop=True)


def normalize_tencent_symbol(symbol: str) -> str:
    code = str(symbol).zfill(6)
    if code.startswith(("5", "6", "9")):
        prefix = "sh"
    elif code.startswith(("4", "8")):
        prefix = "bj"
    else:
        prefix = "sz"
    return f"{prefix}{code}"


@contextmanager
def suppress_akshare_tx_progress():
    try:
        from akshare.stock_feature import stock_hist_tx as tx_module
    except Exception:
        yield
        return

    original = getattr(tx_module, "get_tqdm", None)
    if original is None:
        yield
        return

    tx_module.get_tqdm = lambda: (lambda iterable, **_kwargs: iterable)
    try:
        yield
    finally:
        tx_module.get_tqdm = original


def _fetch_tencent_history(request: ProviderFetchRequest, *, timeout_seconds: float) -> pd.DataFrame:
    try:
        import akshare as ak
    except ImportError as exc:
        raise RuntimeError("akshare is required to fetch daily bars") from exc

    with suppress_akshare_tx_progress():
        frame = ak.stock_zh_a_hist_tx(
            symbol=normalize_tencent_symbol(request.symbol),
            start_date=request.start_date.replace("-", ""),
            end_date=request.end_date.replace("-", ""),
            adjust=request.adjust,
            timeout=timeout_seconds,
        )
    return normalize_akshare_tx_frame(frame, request.symbol, request.frequency)


def _fetch_eastmoney_history(request: ProviderFetchRequest, *, timeout_seconds: float) -> pd.DataFrame:
    try:
        import akshare as ak
    except ImportError as exc:
        raise RuntimeError("akshare is required to fetch daily bars") from exc

    frame = ak.stock_zh_a_hist(
        symbol=str(request.symbol).zfill(6),
        period="daily",
        start_date=request.start_date.replace("-", ""),
        end_date=request.end_date.replace("-", ""),
        adjust=request.adjust,
        timeout=timeout_seconds,
    )
    return normalize_akshare_frame(frame, request.symbol, request.frequency)


class AkshareDailyProvider(MarketDataProvider):
    name = "akshare"

    def __init__(
        self,
        *,
        timeout_seconds: float = 30.0,
        endpoint_order: tuple[str, ...] = ("tencent", "eastmoney"),
    ) -> None:
        self.timeout_seconds = float(timeout_seconds)
        self.endpoint_order = tuple(endpoint_order)

    def normalize_symbol(self, symbol: str) -> str:
        return str(symbol).zfill(6)

    def fetch_daily_bars(self, request: ProviderFetchRequest) -> pd.DataFrame:
        ordered_request = ProviderFetchRequest(
            symbol=self.normalize_symbol(request.symbol),
            start_date=request.start_date,
            end_date=request.end_date,
            frequency=request.frequency,
            adjust=request.adjust,
            market=request.market,
        )
        errors: list[str] = []

        for endpoint in self.endpoint_order:
            try:
                if endpoint == "tencent":
                    frame = _fetch_tencent_history(ordered_request, timeout_seconds=self.timeout_seconds)
                elif endpoint == "eastmoney":
                    frame = _fetch_eastmoney_history(ordered_request, timeout_seconds=self.timeout_seconds)
                else:
                    raise ValueError(f"Unsupported AKShare endpoint: {endpoint}")
            except Exception as exc:
                errors.append(f"{endpoint}: {exc}")
                continue
            if frame is not None and not frame.empty:
                return frame

        if errors:
            raise RuntimeError("AKShare daily fetch failed via configured endpoints: " + " | ".join(errors))
        return pd.DataFrame()
