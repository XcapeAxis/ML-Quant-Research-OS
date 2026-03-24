from __future__ import annotations

from typing import Any, Mapping

import pandas as pd


def cost_sensitivity_summary(
    *,
    metrics_df: pd.DataFrame,
    commission_grid: list[float] | tuple[float, ...],
    slippage_grid: list[float] | tuple[float, ...],
) -> dict[str, Any]:
    base_return = float(metrics_df["total_return"].iloc[0]) if not metrics_df.empty else 0.0
    stressed_returns = []
    for commission in commission_grid:
        for slippage in slippage_grid:
            stressed_returns.append(base_return - float(commission) * 10.0 - float(slippage) * 5.0)
    worst_return = min(stressed_returns) if stressed_returns else base_return
    return {
        "base_total_return": base_return,
        "worst_cost_stressed_return": float(worst_return),
        "return_retention_ratio": float(worst_return / base_return) if base_return not in {0.0, -0.0} else 0.0,
    }


def parameter_perturbation_summary(
    *,
    cfg: Mapping[str, Any],
    perturbations: list[Mapping[str, float]] | tuple[Mapping[str, float], ...],
) -> dict[str, Any]:
    baseline_window = float(cfg.get("limit_days_window", 0))
    baseline_top_pct = float(cfg.get("top_pct_limit_up", 0))
    variants = []
    for perturbation in perturbations:
        variant = {
            "limit_days_window": max(1, int(round(baseline_window * (1.0 + float(perturbation.get("limit_days_window", 0.0)))))),
            "top_pct_limit_up": round(baseline_top_pct * (1.0 + float(perturbation.get("top_pct_limit_up", 0.0))), 4),
        }
        variants.append(variant)
    return {
        "baseline": {
            "limit_days_window": int(baseline_window),
            "top_pct_limit_up": baseline_top_pct,
        },
        "variants": variants,
        "variant_count": len(variants),
    }
