from __future__ import annotations

from pathlib import Path

import pandas as pd

from .db import load_close_volume_panel
from .project import resolve_project_paths
from .universe import load_universe_codes


def compute_factor_panel(name: str, close: pd.DataFrame, volume: pd.DataFrame) -> pd.DataFrame:
    factor = name.strip().lower()
    adv = (close.astype(float) * volume.astype(float)).where(lambda frame: frame != 0.0)
    ret1 = close.pct_change(fill_method=None)
    if factor == "mom20":
        data = close.pct_change(20, fill_method=None)
    elif factor == "rev5":
        data = -close.pct_change(5, fill_method=None)
    elif factor == "vol20":
        data = close.pct_change(fill_method=None).rolling(20).std()
    elif factor == "range":
        data = close.pct_change(fill_method=None).abs().rolling(20).mean()
    elif factor == "vol_surge":
        data = volume / volume.rolling(20).mean() - 1.0
    elif factor == "ma_gap":
        ma20 = close.rolling(20).mean()
        data = close / ma20 - 1.0
    elif factor == "adv20":
        data = adv.rolling(20).mean()
    elif factor == "amihud20":
        impact = ret1.abs() / adv
        data = impact.replace([float("inf"), float("-inf")], pd.NA).rolling(20).mean()
    else:
        raise ValueError(f"Unsupported factor: {name}")
    return data.astype(float)


def build_factor(name: str, close: pd.DataFrame, volume: pd.DataFrame) -> pd.DataFrame:
    data = compute_factor_panel(name, close=close, volume=volume)
    try:
        stacked = data.stack(future_stack=True).reset_index()
    except (TypeError, ValueError):
        stacked = data.stack(dropna=False).reset_index()
    stacked.columns = ["date", "code", "value"]
    stacked["code"] = stacked["code"].astype(str).str.zfill(6)
    return stacked


def build_factors_for_project(
    project: str,
    factor_names: list[str],
    freq: str = "1d",
    start: str | None = None,
    end: str | None = None,
) -> list[Path]:
    paths = resolve_project_paths(project)
    paths.ensure_dirs()
    codes = load_universe_codes(project)
    close, volume = load_close_volume_panel(paths.db_path, freq=freq, codes=codes, start=start, end=end)

    output_paths: list[Path] = []
    for name in factor_names:
        df = build_factor(name, close=close, volume=volume)
        out = paths.features_dir / f"{name}.parquet"
        df.to_parquet(out, index=False)
        output_paths.append(out)
    return output_paths
