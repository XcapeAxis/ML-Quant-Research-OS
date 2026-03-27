from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from ..data.validation import validate_project_data
from ..research_readiness import evaluate_research_readiness
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
    readiness_report = validate_project_data(
        project=project,
        db_path=Path(str(cfg["db_path"])),
        freq=str(cfg["freq"]),
        universe_codes=universe_codes,
        provider_name=str(cfg.get("data_provider", {}).get("provider", "akshare")),
        data_quality_cfg=cfg.get("data_quality"),
        limit_threshold=float(cfg.get("limit_up_threshold", 0.095)),
    )
    readiness = evaluate_research_readiness(report=readiness_report, cfg=cfg)
    if not readiness.ready:
        payload = {
            "promotable": False,
            "reasons": list(readiness.reasons),
            "checks": {
                "research_readiness": readiness.to_dict(),
            },
            "baselines": {
                "status": "not_run",
                "benchmark_available": False,
                "equal_weight_available": False,
                "reasons": ["blocked_by_research_readiness"],
            },
        }
        return EvaluationRecord(
            passed=False,
            summary=f"Promotion gate blocked: {'; '.join(payload['reasons'])}",
            promotion_decision=payload,
        )

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
    payload.setdefault("checks", {})
    payload["checks"]["research_readiness"] = readiness.to_dict()
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
