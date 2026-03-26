from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from quant_mvp.validation.baselines import run_simple_baselines
from quant_mvp.validation.promotion_gate import evaluate_promotion_gate


def _base_cfg() -> dict[str, object]:
    return {
        "research_validation": {
            "max_drawdown_limit": 0.30,
            "min_walk_forward_windows_alive": 2,
            "min_cost_sensitivity_return_ratio": 0.50,
        }
    }


def test_run_simple_baselines_marks_missing_benchmark_as_degraded() -> None:
    close_panel = pd.DataFrame(
        {
            "000002": [10.0, 10.5, 11.0],
            "000003": [8.0, 8.4, 8.8],
        },
        index=pd.date_range("2020-01-01", periods=3, freq="B"),
    )

    baselines = run_simple_baselines(close_panel=close_panel, benchmark_code="000001")

    assert baselines["status"] == "degraded"
    assert baselines["benchmark_available"] is False
    assert baselines["equal_weight_available"] is True
    assert baselines["reasons"] == ["benchmark_missing:000001"]


def test_run_simple_baselines_accepts_explicit_benchmark_series() -> None:
    close_panel = pd.DataFrame(
        {
            "000002": [10.0, 10.5, 11.0],
            "000003": [8.0, 8.4, 8.8],
        },
        index=pd.date_range("2020-01-01", periods=3, freq="B"),
    )
    benchmark_series = pd.Series(
        [9.5, 9.8, 10.0],
        index=close_panel.index,
        name="000001",
        dtype=float,
    )

    baselines = run_simple_baselines(
        close_panel=close_panel,
        benchmark_code="000001",
        benchmark_series=benchmark_series,
    )

    assert baselines["status"] == "pass"
    assert baselines["benchmark_available"] is True
    assert baselines["equal_weight_available"] is True
    assert baselines["reasons"] == []


def test_evaluate_promotion_gate_blocks_incomplete_baselines() -> None:
    decision = evaluate_promotion_gate(
        metrics={"max_drawdown": 0.10},
        leakage_report=SimpleNamespace(passed=True),
        walk_forward={"windows_alive": 2},
        baselines={
            "status": "degraded",
            "benchmark_available": False,
            "equal_weight_available": True,
        },
        cost_sensitivity={"return_retention_ratio": 0.80},
        parameter_robustness={"variant_count": 1},
        research_hypothesis="A bounded test hypothesis.",
        cfg=_base_cfg(),
    )

    assert decision.promotable is False
    assert "Benchmark or equal-weight baselines are incomplete." in decision.reasons
    assert decision.checks["baselines_status"] == "degraded"


def test_evaluate_promotion_gate_passes_complete_baselines() -> None:
    decision = evaluate_promotion_gate(
        metrics={"max_drawdown": 0.10},
        leakage_report=SimpleNamespace(passed=True),
        walk_forward={"windows_alive": 2},
        baselines={
            "status": "pass",
            "benchmark_available": True,
            "equal_weight_available": True,
        },
        cost_sensitivity={"return_retention_ratio": 0.80},
        parameter_robustness={"variant_count": 1},
        research_hypothesis="A bounded test hypothesis.",
        cfg=_base_cfg(),
    )

    assert decision.promotable is True
    assert decision.reasons == []
    assert decision.checks["baselines_status"] == "pass"
