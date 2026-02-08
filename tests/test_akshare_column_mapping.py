from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types

import pandas as pd


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
    )

    assert not out.empty
    assert {"datetime", "open", "high", "low", "close", "volume", "symbol", "freq"}.issubset(out.columns)
    assert out["symbol"].unique().tolist() == ["000001"]
    assert out["freq"].unique().tolist() == ["1d"]


def test_build_symbols_accepts_chinese_headers(monkeypatch, tmp_path: Path) -> None:
    step10 = _load_script_module("step10_for_test", "scripts/steps/10_symbols.py")
    fake_ak = types.SimpleNamespace(
        stock_info_a_code_name=lambda: pd.DataFrame(
            {
                "证券代码": ["000001", "600000", "300001", "000003"],
                "证券简称": ["平安银行", "浦发银行", "创业示例", "退市示例"],
            },
        ),
    )
    monkeypatch.setitem(sys.modules, "akshare", fake_ak)
    monkeypatch.setattr(step10, "ROOT", tmp_path)

    def _fake_save_universe_codes(project: str, codes: list[str]) -> Path:
        out = tmp_path / "data" / "projects" / project / "meta" / "universe_codes.txt"
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as handle:
            for code in codes:
                handle.write(f"{code}\n")
        return out

    monkeypatch.setattr(step10, "save_universe_codes", _fake_save_universe_codes)

    symbols_path, universe_path, count = step10.build_symbols(project="unit_test_project", target_size=None)

    assert symbols_path.exists()
    assert universe_path.exists()
    saved = pd.read_csv(symbols_path)
    codes = set(saved["code"].astype(str).str.zfill(6).tolist())
    assert codes == {"000001", "600000"}
    assert count == 2


def test_is_st_recognizes_delisted_keyword() -> None:
    step10 = _load_script_module("step10_st_test", "scripts/steps/10_symbols.py")
    assert step10._is_st("ST中珠")
    assert step10._is_st("退市海航")
    assert not step10._is_st("平安银行")
