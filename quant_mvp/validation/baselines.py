from __future__ import annotations

from typing import Any

import pandas as pd


def run_simple_baselines(
    *,
    close_panel: pd.DataFrame,
    benchmark_code: str,
) -> dict[str, Any]:
    benchmark = close_panel.get(str(benchmark_code).zfill(6))
    if benchmark is None or benchmark.empty:
        return {
            "benchmark_available": False,
            "benchmark_total_return": 0.0,
            "equal_weight_total_return": 0.0,
        }
    benchmark = benchmark.dropna().astype(float)
    equal_weight = close_panel.astype(float).pct_change(fill_method=None).fillna(0.0).mean(axis=1)
    equal_weight_curve = (1.0 + equal_weight).cumprod()
    return {
        "benchmark_available": True,
        "benchmark_total_return": float(benchmark.iloc[-1] / benchmark.iloc[0] - 1.0) if len(benchmark) > 1 else 0.0,
        "equal_weight_total_return": float(equal_weight_curve.iloc[-1] - 1.0) if len(equal_weight_curve) > 0 else 0.0,
    }
