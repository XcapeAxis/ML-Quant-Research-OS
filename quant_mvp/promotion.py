from __future__ import annotations

import json
from typing import Any

from .config import load_config
from .memory.ledger import stable_hash
from .memory.writeback import record_experiment_result, record_failure, sync_project_state
from .pools import resolve_research_universe_codes
from .strategy_diagnostics import run_strategy_diagnostics


def promote_candidate(project: str, *, config_path=None) -> dict[str, Any]:
    cfg, paths = load_config(project, config_path=config_path)
    hypothesis = str(
        cfg.get("research_hypothesis")
        or "Repeated limit-up behaviour may identify persistent re-accumulation candidates."
    )
    universe_codes, research_universe_source = resolve_research_universe_codes(
        project,
        config_path=config_path,
    )
    diagnostics = run_strategy_diagnostics(
        project=project,
        cfg=cfg,
        paths=paths,
        universe_codes=universe_codes,
        hypothesis=hypothesis,
        core_snapshot_id=research_universe_source if research_universe_source.startswith("core-") else None,
        branch_candidate_codes=universe_codes,
    )
    payload = diagnostics["decision"]
    report_json_path = paths.artifacts_dir / "promotion_gate.json"
    report_md_path = paths.artifacts_dir / "promotion_gate.md"
    failure_report = diagnostics["strategy_failure_report"]
    readiness = payload.get("checks", {}).get("research_readiness", {}) if isinstance(payload, dict) else {}
    research_ready = bool(readiness.get("ready"))
    if payload["promotable"]:
        boundary = "Promotion gate currently passes for the evaluated candidate."
        next_action = "Confirm the passing result on a fresh validated snapshot before trusting it as durable evidence."
        last_failed = "none"
    elif research_ready:
        boundary = "Research inputs are ready, but the candidate still fails strategy-quality checks."
        next_action = failure_report.get("next_experiment_themes", ["Choose one bounded strategy experiment."])[0]
        last_failed = "Promotion gate blocked on strategy-quality checks."
    else:
        boundary = "Engineering guardrails work; promotion remains blocked on data readiness or the current research boundary."
        next_action = "Restore readiness on the current research universe before retrying promotion."
        last_failed = "Promotion gate blocked on data readiness."

    sync_project_state(
        project,
        {
            "current_phase": "Phase 1 Research OS - promotion evaluation",
            "current_task": "Keep promotion honest by separating data-readiness blockers from strategy-quality blockers.",
            "current_blocker": "; ".join(payload.get("reasons", [])) if payload.get("reasons") else "none",
            "current_capability_boundary": boundary,
            "next_priority_action": next_action,
            "last_verified_capability": "Promotion gate diagnostics were generated and written to runtime artifacts.",
            "last_failed_capability": last_failed,
        },
    )
    record_experiment_result(
        project,
        {
            "timestamp": "promotion-gate",
            "experiment_id": "promote_candidate",
            "hypothesis": hypothesis,
            "config_hash": stable_hash(cfg),
            "result": "passed" if payload["promotable"] else "blocked",
            "blockers": payload.get("reasons", []),
            "artifact_refs": [
                str(report_json_path),
                str(report_md_path),
                str(diagnostics["strategy_failure_report_json"]),
                str(diagnostics["strategy_failure_report_md"]),
            ],
        },
    )
    if not payload["promotable"]:
        record_failure(
            project,
            {
                "timestamp": "promotion-gate",
                "experiment_id": "promote_candidate",
                "summary": "Promotion gate blocked the current candidate.",
                "root_cause": "; ".join(payload.get("reasons", [])),
                "corrective_action": next_action,
                "resolution_status": "not_fixed",
            },
        )
    return {
        "promotion_report_json": str(report_json_path),
        "promotion_report_md": str(report_md_path),
        "decision": payload,
        "strategy_failure_report_json": str(diagnostics["strategy_failure_report_json"]),
        "strategy_failure_report_md": str(diagnostics["strategy_failure_report_md"]),
        "strategy_failure_report": failure_report,
        "readiness_report": diagnostics["readiness_report"].to_dict(),
        "research_universe_source": research_universe_source,
    }
