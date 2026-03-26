from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


@dataclass
class PromotionDecision:
    promotable: bool
    reasons: list[str]
    checks: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_promotion_gate(
    *,
    metrics: Mapping[str, Any],
    leakage_report,
    walk_forward: Mapping[str, Any],
    baselines: Mapping[str, Any],
    cost_sensitivity: Mapping[str, Any],
    parameter_robustness: Mapping[str, Any],
    research_hypothesis: str,
    cfg: Mapping[str, Any],
) -> PromotionDecision:
    rules = cfg.get("research_validation", {})
    max_drawdown_limit = float(rules.get("max_drawdown_limit", 0.30))
    min_windows_alive = int(rules.get("min_walk_forward_windows_alive", 2))
    min_cost_return_ratio = float(rules.get("min_cost_sensitivity_return_ratio", 0.50))

    reasons: list[str] = []
    max_drawdown = abs(float(metrics.get("max_drawdown", 0.0)))
    if not leakage_report.passed:
        reasons.append("Leakage audit failed.")
    if max_drawdown > max_drawdown_limit:
        reasons.append(f"Max drawdown {max_drawdown:.2%} exceeds {max_drawdown_limit:.2%}.")
    if int(walk_forward.get("windows_alive", 0)) < min_windows_alive:
        reasons.append("Walk-forward survival is below the promotion threshold.")
    benchmark_available = bool(baselines.get("benchmark_available", False))
    equal_weight_available = bool(baselines.get("equal_weight_available", False))
    baselines_status = str(
        baselines.get(
            "status",
            "pass" if benchmark_available and equal_weight_available else "degraded",
        )
    )
    if baselines_status != "pass" or not benchmark_available or not equal_weight_available:
        reasons.append("Benchmark or equal-weight baselines are incomplete.")
    if float(cost_sensitivity.get("return_retention_ratio", 0.0)) < min_cost_return_ratio:
        reasons.append("Cost sensitivity collapses too much of the base return.")
    if not research_hypothesis.strip():
        reasons.append("Research hypothesis is empty.")
    if int(parameter_robustness.get("variant_count", 0)) <= 0:
        reasons.append("Parameter perturbation coverage is missing.")

    walk_forward_status = str(
        walk_forward.get(
            "status",
            "pass" if int(walk_forward.get("windows_alive", 0)) >= min_windows_alive else "degraded",
        )
    )
    parameter_robustness_status = str(
        parameter_robustness.get(
            "status",
            "pass" if int(parameter_robustness.get("variant_count", 0)) > 0 else "missing",
        )
    )

    checks = {
        "leakage_passed": leakage_report.passed,
        "walk_forward_windows_alive": int(walk_forward.get("windows_alive", 0)),
        "walk_forward_status": walk_forward_status,
        "max_drawdown": max_drawdown,
        "baselines_status": baselines_status,
        "cost_return_retention_ratio": float(cost_sensitivity.get("return_retention_ratio", 0.0)),
        "has_economic_rationale": bool(research_hypothesis.strip()),
        "parameter_variants_checked": int(parameter_robustness.get("variant_count", 0)),
        "parameter_robustness_status": parameter_robustness_status,
    }
    return PromotionDecision(promotable=not reasons, reasons=reasons, checks=checks)
