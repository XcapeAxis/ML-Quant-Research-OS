from __future__ import annotations

from typing import Any

import pandas as pd

from ..validation.baselines import run_simple_baselines
from ..validation.leakage import audit_strategy_leakage
from ..validation.promotion_gate import evaluate_promotion_gate
from ..validation.robustness import cost_sensitivity_summary, parameter_perturbation_summary
from ..validation.walk_forward import walk_forward_summary
from .schemas import EvaluationRecord


def evaluate_execution(
    *,
    project: str,
    cfg: dict[str, Any],
    universe_codes: list[str],
    rank_df: pd.DataFrame,
    close_panel: pd.DataFrame,
    volume_panel: pd.DataFrame,
    metrics_df: pd.DataFrame,
    hypothesis: str,
    benchmark_series: pd.Series | None = None,
) -> EvaluationRecord:
    leakage = audit_strategy_leakage(
        rank_df=rank_df,
        close_panel=close_panel,
        volume_panel=volume_panel,
        cfg=cfg,
        universe_codes=universe_codes,
    )
    walk_forward = walk_forward_summary(
        rank_df=rank_df,
        windows=list(cfg.get("walk_forward", {}).get("windows", [])),
    )
    baselines = run_simple_baselines(
        close_panel=close_panel,
        benchmark_code=str(cfg.get("baselines", {}).get("benchmark_code", "000001")),
        benchmark_series=benchmark_series,
    )
    cost = cost_sensitivity_summary(
        metrics_df=metrics_df,
        commission_grid=list(cfg.get("cost_sweep", {}).get("commission_grid", [])),
        slippage_grid=list(cfg.get("cost_sweep", {}).get("slippage_grid", [])),
    )
    perturbations = parameter_perturbation_summary(
        cfg=cfg,
        perturbations=list(cfg.get("research_validation", {}).get("parameter_perturbations", [])),
    )
    metrics = metrics_df.iloc[0].to_dict() if not metrics_df.empty else {}
    decision = evaluate_promotion_gate(
        metrics=metrics,
        leakage_report=leakage,
        walk_forward=walk_forward,
        baselines=baselines,
        cost_sensitivity=cost,
        parameter_robustness=perturbations,
        research_hypothesis=hypothesis,
        cfg=cfg,
    )
    summary = (
        "Promotion gate passed in dry-run mode."
        if decision.promotable
        else f"Promotion gate blocked: {'; '.join(decision.reasons)}"
    )
    payload = decision.to_dict()
    payload["baselines"] = baselines
    payload["leakage"] = leakage.to_dict()
    payload["walk_forward"] = walk_forward
    payload["cost_sensitivity"] = cost
    payload["parameter_robustness"] = perturbations
    return EvaluationRecord(
        passed=decision.promotable,
        summary=summary,
        promotion_decision=payload,
    )
