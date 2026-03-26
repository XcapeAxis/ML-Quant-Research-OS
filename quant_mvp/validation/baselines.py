from __future__ import annotations

from typing import Any

import pandas as pd


def run_simple_baselines(
    *,
    close_panel: pd.DataFrame,
    benchmark_code: str,
    benchmark_series: pd.Series | None = None,
) -> dict[str, Any]:
    benchmark_key = str(benchmark_code).zfill(6)
    explicit_benchmark = benchmark_series.dropna().astype(float) if benchmark_series is not None else pd.Series(dtype=float)
    if explicit_benchmark.empty:
        benchmark = close_panel.get(benchmark_key)
        explicit_benchmark = (
            benchmark.dropna().astype(float)
            if benchmark is not None and not benchmark.empty
            else pd.Series(dtype=float)
        )
    benchmark_available = len(explicit_benchmark) > 1

    equal_weight = close_panel.astype(float).pct_change(fill_method=None).fillna(0.0).mean(axis=1)
    equal_weight_curve = (1.0 + equal_weight).cumprod().dropna()
    equal_weight_available = len(equal_weight_curve) > 1

    reasons: list[str] = []
    if not benchmark_available:
        reasons.append(f"benchmark_missing:{benchmark_key}")
    if not equal_weight_available:
        reasons.append("equal_weight_missing")

    return {
        "status": "pass" if not reasons else "degraded",
        "benchmark_available": benchmark_available,
        "equal_weight_available": equal_weight_available,
        "benchmark_total_return": (
            float(explicit_benchmark.iloc[-1] / explicit_benchmark.iloc[0] - 1.0)
            if benchmark_available
            else 0.0
        ),
        "equal_weight_total_return": float(equal_weight_curve.iloc[-1] - 1.0) if equal_weight_available else 0.0,
        "reasons": reasons,
    }
