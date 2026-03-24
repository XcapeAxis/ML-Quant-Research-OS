from __future__ import annotations

import json
from typing import Any

from .config import load_config
from .memory.writeback import record_failure, sync_project_state
from .research_core import build_limit_up_rank_artifacts, run_limit_up_backtest_artifacts
from .universe import load_universe_codes
from .validation.baselines import run_simple_baselines
from .validation.leakage import audit_strategy_leakage
from .validation.promotion_gate import evaluate_promotion_gate
from .validation.robustness import cost_sensitivity_summary, parameter_perturbation_summary
from .validation.walk_forward import walk_forward_summary


def promote_candidate(project: str, *, config_path=None) -> dict[str, Any]:
    cfg, paths = load_config(project, config_path=config_path)
    try:
        universe = load_universe_codes(project)
        rank_artifacts = build_limit_up_rank_artifacts(cfg=cfg, paths=paths, universe_codes=universe)
        backtest_artifacts = run_limit_up_backtest_artifacts(
            cfg=cfg,
            paths=paths,
            rank_df=rank_artifacts.selection.rank_df,
            save="none",
            no_show=True,
        )
        leakage = audit_strategy_leakage(
            rank_df=rank_artifacts.selection.rank_df,
            close_panel=backtest_artifacts.close_panel,
            volume_panel=backtest_artifacts.volume_panel,
            cfg=cfg,
            universe_codes=universe,
        )
        walk_forward = walk_forward_summary(
            rank_df=rank_artifacts.selection.rank_df,
            windows=list(cfg.get("walk_forward", {}).get("windows", [])),
        )
        baselines = run_simple_baselines(
            close_panel=backtest_artifacts.close_panel,
            benchmark_code=str(cfg.get("baselines", {}).get("benchmark_code", "000001")),
        )
        cost = cost_sensitivity_summary(
            metrics_df=backtest_artifacts.metrics_df,
            commission_grid=list(cfg.get("cost_sweep", {}).get("commission_grid", [])),
            slippage_grid=list(cfg.get("cost_sweep", {}).get("slippage_grid", [])),
        )
        parameter_robustness = parameter_perturbation_summary(
            cfg=cfg,
            perturbations=list(cfg.get("research_validation", {}).get("parameter_perturbations", [])),
        )
        metrics = backtest_artifacts.metrics_df.iloc[0].to_dict() if not backtest_artifacts.metrics_df.empty else {}
        decision = evaluate_promotion_gate(
            metrics=metrics,
            leakage_report=leakage,
            walk_forward=walk_forward,
            cost_sensitivity=cost,
            parameter_robustness=parameter_robustness,
            research_hypothesis=str(
                cfg.get("research_hypothesis")
                or "Repeated limit-up behaviour may identify persistent re-accumulation candidates."
            ),
            cfg=cfg,
        )
        payload = decision.to_dict()
        payload["leakage"] = leakage.to_dict()
        payload["walk_forward"] = walk_forward
        payload["baselines"] = baselines
        payload["cost_sensitivity"] = cost
        payload["parameter_robustness"] = parameter_robustness
    except Exception as exc:
        payload = {
            "promotable": False,
            "reasons": [f"missing_research_inputs: {exc}"],
            "checks": {},
        }

    report_json_path = paths.artifacts_dir / "promotion_gate.json"
    report_md_path = paths.artifacts_dir / "promotion_gate.md"
    report_json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Promotion Gate",
        "",
        f"- promotable: {payload['promotable']}",
        f"- max_drawdown: {payload.get('checks', {}).get('max_drawdown', 'n/a')}",
        f"- leakage_passed: {payload.get('checks', {}).get('leakage_passed', 'n/a')}",
        f"- walk_forward_windows_alive: {payload.get('checks', {}).get('walk_forward_windows_alive', 'n/a')}",
        f"- cost_return_retention_ratio: {payload.get('checks', {}).get('cost_return_retention_ratio', 'n/a')}",
        "",
        "## Reasons",
    ]
    if payload["reasons"]:
        lines.extend(f"- {reason}" for reason in payload["reasons"])
    else:
        lines.append("- Candidate meets the current Phase 1 promotion gate.")
    report_md_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    sync_project_state(
        project,
        {
            "phase": "Phase 1 Research OS",
            "last_promotion_gate": payload["promotable"],
            "promotion_report": str(report_md_path),
        },
    )
    if not payload["promotable"]:
        record_failure(
            project,
            {
                "timestamp": "promotion-gate",
                "experiment_id": "promote_candidate",
                "summary": "Candidate failed the current promotion gate.",
                "root_cause": "; ".join(payload.get("reasons", [])),
                "corrective_action": "Resolve the failed gate reasons before the next promotion attempt.",
            },
        )
    return {
        "promotion_report_json": str(report_json_path),
        "promotion_report_md": str(report_md_path),
        "decision": payload,
    }
