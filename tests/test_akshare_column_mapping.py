from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types

import pandas as pd

from quant_mvp.data.contracts import ProviderFetchRequest
from quant_mvp.data.providers import akshare_provider
from quant_mvp.security_master import _fetch_remote_security_master, _st_label, build_security_master


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


def test_build_security_master_falls_back_to_db_when_remote_fetch_fails(monkeypatch, synthetic_project) -> None:
    ctx = synthetic_project
    monkeypatch.setattr(
        "quant_mvp.security_master._fetch_remote_security_master",
        lambda: (_ for _ in ()).throw(RuntimeError("network down")),
    )

    result = build_security_master(ctx["project"], config_path=ctx["config_path"])

    assert result.source == "db_fallback"
    assert result.count == 3
    saved = pd.read_csv(ctx["paths"].meta_dir / "security_master.csv", dtype={"code": str})
    assert set(saved["code"].astype(str).str.zfill(6).tolist()) == {"000001", "000002", "000003"}
    assert {"exchange", "board", "security_type", "share_class", "is_st", "st_label"}.issubset(saved.columns)
    assert saved["board"].eq("mainboard").all()
    assert saved["security_type"].eq("common_stock").all()
    assert saved["share_class"].eq("A").all()


def test_fetch_remote_security_master_keeps_mainboard_st_as_label(monkeypatch) -> None:
    fake_ak = types.SimpleNamespace(
        stock_info_sh_name_code=lambda **_: pd.DataFrame(
            {
                "证券代码": ["600000", "688001"],
                "证券简称": ["浦发银行", "星河芯片"],
                "证券全称": ["上海浦东发展银行股份有限公司", "星河芯片股份有限公司"],
                "上市日期": ["1999-11-10", "2019-01-01"],
            },
        ),
        stock_info_sz_name_code=lambda **_: pd.DataFrame(
            {
                "板块": ["主板", "创业板"],
                "A股代码": ["000001", "300001"],
                "A股简称": ["*ST样本", "创业样本"],
                "A股上市日期": ["1991-04-03", "2020-01-01"],
            },
        ),
    )
    monkeypatch.setitem(sys.modules, "akshare", fake_ak)

    frame, source, assumptions = _fetch_remote_security_master()

    assert source == "akshare_exchange_lists"
    assert assumptions == []
    filtered = frame[
        frame["exchange"].isin({"SSE", "SZSE"})
        & frame["board"].eq("mainboard")
        & frame["security_type"].eq("common_stock")
        & frame["share_class"].eq("A")
    ]
    assert filtered["code"].tolist() == ["000001", "600000"]
    assert bool(filtered.loc[filtered["code"] == "000001", "is_st"].iloc[0]) is True
    assert filtered.loc[filtered["code"] == "000001", "st_label"].iloc[0] == "*ST"


def test_st_label_recognizes_prefixed_st_names() -> None:
    assert _st_label("*ST中珠") == "*ST"
    assert _st_label("ST海航") == "ST"
    assert _st_label("平安银行") == ""
