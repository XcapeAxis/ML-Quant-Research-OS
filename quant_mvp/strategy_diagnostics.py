from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .data.validation import validate_project_data
from .research_core import build_limit_up_rank_artifacts, run_limit_up_backtest_artifacts
from .research_readiness import evaluate_research_readiness, write_research_readiness_artifacts
from .validation.baselines import run_simple_baselines
from .validation.leakage import audit_strategy_leakage
from .validation.promotion_gate import evaluate_promotion_gate
from .validation.robustness import cost_sensitivity_summary, parameter_perturbation_summary
from .validation.walk_forward import walk_forward_summary


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _sort_blockers(reasons: list[str]) -> list[str]:
    priorities = {
        "drawdown": 0,
        "leakage": 1,
        "walk": 2,
        "coverage": 3,
        "missing_research_inputs": 4,
    }

    def _score(reason: str) -> tuple[int, str]:
        lowered = reason.lower()
        for key, score in priorities.items():
            if key in lowered:
                return score, lowered
        return 99, lowered

    return sorted([str(item).strip() for item in reasons if str(item).strip()], key=_score)


def _next_experiment_themes(reasons: list[str], *, research_ready: bool) -> list[str]:
    lowered = " | ".join(reason.lower() for reason in reasons)
    themes: list[str] = []
    if "drawdown" in lowered:
        themes.append("Break down whether drawdown comes from time-window concentration, name concentration, or long holding tails.")
        themes.append("Compare a risk-constrained strategy variant against the current version before opening a broad parameter sweep.")
    if "walk" in lowered:
        themes.append("Split the result by walk-forward window and check whether failure clusters in one market regime.")
    if "leakage" in lowered:
        themes.append("Recheck signal timing alignment and tradability constraints before judging the strategy itself.")
    if "coverage" in lowered or not research_ready:
        themes.append("Clarify the data boundary and the research range before comparing strategy outcomes.")
    if not themes:
        themes.append("Design one controlled experiment around the highest-priority blocker instead of opening a broad search.")
    return themes


def build_strategy_failure_report(
    *,
    project: str,
    hypothesis: str,
    decision: dict[str, Any],
) -> dict[str, Any]:
    promotable = bool(decision.get("promotable"))
    checks = decision.get("checks", {}) if isinstance(decision, dict) else {}
    readiness = checks.get("research_readiness", {}) if isinstance(checks, dict) else {}
    research_ready = bool(readiness.get("ready"))
    reasons = _sort_blockers(list(decision.get("reasons", [])))
    if promotable:
        classification = "passed"
    elif research_ready:
        classification = "strategy_quality_failure"
    else:
        classification = "data_or_boundary_failure"

    evidence = {
        "research_ready": readiness.get("ready"),
        "research_stage": readiness.get("stage"),
        "max_drawdown": checks.get("max_drawdown"),
        "leakage_passed": checks.get("leakage_passed"),
        "walk_forward_windows_alive": checks.get("walk_forward_windows_alive"),
        "walk_forward_status": checks.get("walk_forward_status"),
        "baselines_status": checks.get("baselines_status"),
        "cost_return_retention_ratio": checks.get("cost_return_retention_ratio"),
        "parameter_robustness_status": checks.get("parameter_robustness_status"),
    }

    if promotable:
        unsupported = [
            "A passing promotion result still does not prove durable profitability.",
        ]
    elif research_ready:
        unsupported = [
            "Do not blame this failure on missing data; the current research range is already data-ready.",
            "Do not reduce the drawdown problem to generic parameter tuning before decomposing where the risk comes from.",
        ]
    else:
        unsupported = [
            "Do not treat this as a pure strategy failure while data readiness or the research boundary is still blocking the result.",
        ]

    return {
        "project": project,
        "generated_at": _utc_now(),
        "hypothesis": hypothesis,
        "status": "passed" if promotable else "blocked",
        "classification": classification,
        "primary_blockers": reasons,
        "key_evidence": evidence,
        "cannot_conclude": unsupported,
        "next_experiment_themes": _next_experiment_themes(reasons, research_ready=research_ready),
    }


def write_strategy_failure_report(*, artifacts_dir: Path, report: dict[str, Any]) -> tuple[Path, Path]:
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    json_path = artifacts_dir / "STRATEGY_FAILURE_REPORT.json"
    md_path = artifacts_dir / "STRATEGY_FAILURE_REPORT.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2).rstrip() + "\n", encoding="utf-8")

    lines = [
        "# Strategy Failure Report",
        "",
        f"- project: {report.get('project', 'unknown')}",
        f"- status: {report.get('status', 'unknown')}",
        f"- classification: {report.get('classification', 'unknown')}",
        f"- hypothesis: {report.get('hypothesis', '')}",
        "",
        "## Primary Blockers",
    ]
    blockers = report.get("primary_blockers", [])
    if blockers:
        lines.extend(f"- {item}" for item in blockers)
    else:
        lines.append("- none")
    lines.extend(["", "## Key Evidence"])
    for key, value in (report.get("key_evidence", {}) or {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Cannot Conclude"])
    lines.extend(f"- {item}" for item in report.get("cannot_conclude", []) or ["none"])
    lines.extend(["", "## Next Experiment Themes"])
    lines.extend(f"- {item}" for item in report.get("next_experiment_themes", []) or ["none"])
    md_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return json_path, md_path


def run_strategy_diagnostics(
    *,
    project: str,
    cfg: dict[str, Any],
    paths,
    universe_codes: list[str],
    hypothesis: str,
    core_snapshot_id: str | None = None,
    branch_pool_snapshot_id: str | None = None,
    branch_candidate_codes: list[str] | None = None,
) -> dict[str, Any]:
    paths.artifacts_dir.mkdir(parents=True, exist_ok=True)
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
    readiness_md_path, readiness_json_path = write_research_readiness_artifacts(
        meta_dir=paths.meta_dir,
        report=readiness_report,
        decision=readiness,
    )

    if not readiness.ready:
        payload = {
            "promotable": False,
            "reasons": list(readiness.reasons),
            "checks": {
                "research_readiness": readiness.to_dict(),
            },
        }
    else:
        try:
            rank_artifacts = build_limit_up_rank_artifacts(cfg=cfg, paths=paths, universe_codes=universe_codes)
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
                universe_codes=universe_codes,
            )
            walk_forward = walk_forward_summary(
                rank_df=rank_artifacts.selection.rank_df,
                windows=list(cfg.get("walk_forward", {}).get("windows", [])),
            )
            baselines = run_simple_baselines(
                close_panel=backtest_artifacts.close_panel,
                benchmark_code=str(cfg.get("baselines", {}).get("benchmark_code", "000001")),
                benchmark_series=backtest_artifacts.benchmark_series,
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
                baselines=baselines,
                cost_sensitivity=cost,
                parameter_robustness=parameter_robustness,
                research_hypothesis=hypothesis,
                cfg=cfg,
            )
            payload = decision.to_dict()
            payload.setdefault("checks", {})
            payload["checks"]["research_readiness"] = readiness.to_dict()
            payload["checks"]["core_snapshot_id"] = core_snapshot_id
            payload["checks"]["branch_pool_snapshot_id"] = branch_pool_snapshot_id
            payload["checks"]["branch_candidate_count"] = len(branch_candidate_codes or [])
            payload["checks"]["baselines_status"] = baselines.get("status", "unknown")
            payload["checks"]["walk_forward_status"] = walk_forward.get("status", "unknown")
            payload["checks"]["parameter_robustness_status"] = parameter_robustness.get("status", "unknown")
            payload["leakage"] = leakage.to_dict()
            payload["walk_forward"] = walk_forward
            payload["baselines"] = baselines
            payload["cost_sensitivity"] = cost
            payload["parameter_robustness"] = parameter_robustness
        except Exception as exc:
            payload = {
                "promotable": False,
                "reasons": [f"missing_research_inputs: {exc}"],
                "checks": {
                    "research_readiness": readiness.to_dict(),
                },
            }

    report_json_path = paths.artifacts_dir / "promotion_gate.json"
    report_md_path = paths.artifacts_dir / "promotion_gate.md"
    report_json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2).rstrip() + "\n", encoding="utf-8")

    lines = [
        "# Promotion Gate",
        "",
        f"- promotable: {payload['promotable']}",
        f"- max_drawdown: {payload.get('checks', {}).get('max_drawdown', 'n/a')}",
        f"- leakage_passed: {payload.get('checks', {}).get('leakage_passed', 'n/a')}",
        f"- walk_forward_windows_alive: {payload.get('checks', {}).get('walk_forward_windows_alive', 'n/a')}",
        f"- cost_return_retention_ratio: {payload.get('checks', {}).get('cost_return_retention_ratio', 'n/a')}",
        f"- research_readiness_stage: {payload.get('checks', {}).get('research_readiness', {}).get('stage', 'n/a')}",
        f"- research_ready: {payload.get('checks', {}).get('research_readiness', {}).get('ready', 'n/a')}",
        f"- baselines_status: {payload.get('checks', {}).get('baselines_status', 'n/a')}",
        f"- walk_forward_status: {payload.get('checks', {}).get('walk_forward_status', 'n/a')}",
        f"- parameter_robustness_status: {payload.get('checks', {}).get('parameter_robustness_status', 'n/a')}",
        "",
        "## Reasons",
    ]
    if payload["reasons"]:
        lines.extend(f"- {reason}" for reason in payload["reasons"])
    else:
        lines.append("- Candidate meets the current Phase 1 promotion gate.")
    report_md_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    failure_report = build_strategy_failure_report(project=project, hypothesis=hypothesis, decision=payload)
    failure_json_path, failure_md_path = write_strategy_failure_report(
        artifacts_dir=paths.artifacts_dir,
        report=failure_report,
    )
    return {
        "decision": payload,
        "readiness_report": readiness_report,
        "readiness": readiness,
        "promotion_report_json": str(report_json_path),
        "promotion_report_md": str(report_md_path),
        "strategy_failure_report_json": str(failure_json_path),
        "strategy_failure_report_md": str(failure_md_path),
        "strategy_failure_report": failure_report,
        "readiness_markdown_path": str(readiness_md_path),
        "readiness_json_path": str(readiness_json_path),
    }
