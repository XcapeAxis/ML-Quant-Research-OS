from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path
import sys
import types

import pandas as pd
import pytest

from quant_mvp.data.contracts import ProviderFetchRequest
from quant_mvp.data.providers import akshare_provider


def _load_script_module(module_name: str, rel_path: str):
    root = Path(__file__).resolve().parents[1]
    path = root / rel_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fetch_akshare_daily_maps_chinese_columns(monkeypatch) -> None:
    step11 = _load_script_module("step11_for_test", "scripts/steps/11_update_bars.py")
    fake_df = pd.DataFrame(
        {
            "日期": ["2025-01-02", "2025-01-03"],
            "开盘": [10.0, 10.2],
            "收盘": [10.1, 10.3],
            "最高": [10.2, 10.4],
            "最低": [9.9, 10.1],
            "成交量": [100000, 120000],
        },
    )
    fake_ak = types.SimpleNamespace(stock_zh_a_hist=lambda **_: fake_df.copy())
    monkeypatch.setitem(sys.modules, "akshare", fake_ak)

    out = step11._fetch_akshare_daily(
        code="1",
        start_yyyymmdd="20250101",
        end_yyyymmdd="20250103",
        freq="1d",
        timeout_seconds=3,
    )

    assert not out.empty
    assert {"datetime", "open", "high", "low", "close", "volume", "symbol", "freq"}.issubset(out.columns)
    assert out["symbol"].unique().tolist() == ["000001"]
    assert out["freq"].unique().tolist() == ["1d"]


def test_akshare_provider_prefers_tencent_path_before_eastmoney(monkeypatch) -> None:
    calls: list[str] = []

    def _fake_tencent(request: ProviderFetchRequest, *, timeout_seconds: float) -> pd.DataFrame:
        del timeout_seconds
        calls.append(f"tx:{request.symbol}")
        return pd.DataFrame(
            [
                {
                    "datetime": "2025-01-02",
                    "open": 10.0,
                    "high": 10.2,
                    "low": 9.9,
                    "close": 10.1,
                    "volume": 123456.0,
                    "symbol": str(request.symbol).zfill(6),
                    "freq": request.frequency,
                },
            ],
        )

    def _fail_eastmoney(request: ProviderFetchRequest, *, timeout_seconds: float) -> pd.DataFrame:
        del request, timeout_seconds
        raise AssertionError("eastmoney should not be called when the preferred Tencent path succeeds")

    monkeypatch.setattr(akshare_provider, "_fetch_tencent_history", _fake_tencent)
    monkeypatch.setattr(akshare_provider, "_fetch_eastmoney_history", _fail_eastmoney)

    provider = akshare_provider.AkshareDailyProvider(timeout_seconds=3)
    out = provider.fetch_daily_bars(
        ProviderFetchRequest(symbol="1", start_date="20250101", end_date="20250103", frequency="1d"),
    )

    assert calls == ["tx:000001"]
    assert out["symbol"].unique().tolist() == ["000001"]
    assert out["freq"].unique().tolist() == ["1d"]
    assert float(out.iloc[0]["volume"]) == 123456.0


def test_build_symbols_falls_back_to_db_when_remote_fetch_fails(monkeypatch, tmp_path: Path) -> None:
    step10 = _load_script_module("step10_for_test", "scripts/steps/10_symbols.py")
    db_path = tmp_path / "market.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE bars (symbol TEXT, datetime TEXT, freq TEXT, open REAL, high REAL, low REAL, close REAL, volume REAL)")
    conn.executemany(
        "INSERT INTO bars VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("000001", "2025-01-02", "1d", 10, 10.5, 9.8, 10.2, 100000),
            ("600000", "2025-01-02", "1d", 11, 11.2, 10.8, 11.1, 120000),
            ("300001", "2025-01-02", "1d", 12, 12.3, 11.9, 12.1, 130000),
        ],
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(step10, "_fetch_remote_symbols", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("network down")))

    def _fake_save_universe_codes(project: str, codes: list[str]) -> Path:
        out = tmp_path / "data" / "projects" / project / "meta" / "universe_codes.txt"
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as handle:
            for code in codes:
                handle.write(f"{code}\n")
        return out

    monkeypatch.setattr(step10, "save_universe_codes", _fake_save_universe_codes)

    symbols_path, universe_path, count, source = step10.build_symbols(
        project="unit_test_project",
        db_path=db_path,
        freq="1d",
        target_size=None,
    )

    assert symbols_path.exists()
    assert universe_path.exists()
    saved = pd.read_csv(symbols_path)
    codes = set(saved["code"].astype(str).str.zfill(6).tolist())
    assert codes == {"000001", "600000"}
    assert count == 2
    assert source == "db"


def test_fetch_remote_symbols_requires_both_exchanges(monkeypatch) -> None:
    step10 = _load_script_module("step10_remote_test", "scripts/steps/10_symbols.py")
    monkeypatch.setattr(
        step10,
        "_fetch_sse_mainboard_symbols",
        lambda _cfg: pd.DataFrame({"code": ["600000"], "name": ["浦发银行"]}),
    )
    monkeypatch.setattr(
        step10,
        "_fetch_szse_a_symbols",
        lambda _cfg: pd.DataFrame(columns=["code", "name"]),
    )

    with pytest.raises(RuntimeError, match="remote symbol fetch failed"):
        step10._fetch_remote_symbols(step10.NetworkRuntimeConfig())


def test_is_st_recognizes_delisted_keyword() -> None:
    step10 = _load_script_module("step10_st_test", "scripts/steps/10_symbols.py")
    assert step10._is_st("ST中珠")
    assert step10._is_st("退市海航")
    assert not step10._is_st("平安银行")
