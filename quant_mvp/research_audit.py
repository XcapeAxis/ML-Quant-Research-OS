from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from .config import load_config
from .db import table_row_count
from .project import find_repo_root, resolve_project_paths
from .ranking import get_rebalance_dates_tuesday
from .strategy_schema import default_limit_up_spec


def _manifest_has_stale_paths(manifest_path: Path, repo_root: Path) -> bool:
    if not manifest_path.exists():
        return False
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    paths = payload.get("paths", {})
    for value in paths.values():
        if not value:
            continue
        try:
            path = Path(str(value))
        except Exception:
            return True
        if path.is_absolute() and repo_root.drive and path.drive and path.drive.lower() != repo_root.drive.lower():
            return True
    return False


def _script_uses_core(path: Path, symbol: str) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    return symbol in text


def _weekday_contract_ok() -> bool:
    calendar = pd.date_range("2026-01-05", periods=10, freq="B")
    dates = get_rebalance_dates_tuesday(calendar, lookback=0, weekday=1)
    return all(item.weekday() == 1 for item in dates)


def _build_system_audit_markdown(project: str, findings: list[dict[str, Any]]) -> str:
    lines = [
        "# System Audit",
        "",
        f"- Date: {date.today().isoformat()}",
        f"- Project: {project}",
        "- Scope: Phase 1 A-share daily/weekly research operating system audit",
        "",
        "## Findings",
        "",
        "| Area | Status | Detail |",
        "| --- | --- | --- |",
    ]
    for item in findings:
        lines.append(f"| {item['area']} | {item['status']} | {item['detail']} |")
    lines.extend(
        [
            "",
            "## Key Observations",
            "",
            "- The repo now routes both the standalone script and the step pipeline through the same audited limit-up core.",
            "- The historical repo state had Wednesday/Tuesday drift and mismatched 250 vs 750 day defaults; those are now locked by schema and tests.",
            "- Tracked long-term memory now belongs under `memory/projects/<project>/`, while runtime data and artifacts stay under `data/` and `artifacts/`.",
            "- The default project still needs fresh universe/data artifacts to reproduce any real historical showcase, so documentation must remain conservative.",
        ],
    )
    return "\n".join(lines).rstrip() + "\n"


def _build_failure_modes_markdown() -> str:
    return """# Failure Modes

## Research Integrity
- Using standalone entrypoints that diverge from the audited strategy core.
- Letting README claims outlive the artifacts or manifests that once supported them.
- Running selection or backtests without a frozen universe snapshot.

## Data and Leakage
- Treating raw AKShare bars as validated data without cleaning and validation reports.
- Using same-day prices as forward labels instead of next-trading-day returns.
- Ignoring zero-volume, suspension, or limit-lock proxies when ranking or evaluating.

## Agent Control
- Allowing the agent loop to skip memory writeback.
- Letting tools execute outside the allowlist or without being logged.
- Overwriting failure records instead of appending postmortems and experiment ledgers.

## Memory Layering
- Writing durable project memory only into ignored runtime directories.
- Mixing compact tracked ledgers with full raw experiment payloads.
- Starting a new chat without refreshing handoff, migration prompt, and machine-state summaries.
"""


def _build_decision_log_markdown() -> str:
    return """# Decision Log

## 2026-03-24
- Keep `quant_mvp/db.py`, `quant_mvp/backtest_engine.py`, `quant_mvp/selection.py`, and `quant_mvp/project.py` as the reusable low-level core because they already expose deterministic, testable primitives.
- Rewrite `scripts/run_limit_up_screening.py` so it cannot drift away from the modular pipeline.
- Introduce schema modules (`quant_mvp/strategy_schema.py`, `quant_mvp/config_schema.py`) as the single source of truth for defaults and contracts.
- Introduce provider/data validation abstractions instead of binding update logic directly to AKShare response quirks.
- Keep the agent control plane dry-run capable by default; a live LLM backend is optional and never required for tests.

## 2026-03-25
- Move durable project memory into git-tracked `memory/projects/<project>/`.
- Keep raw cycle payloads, manifests, and other high-noise outputs under ignored runtime directories.
- Add handoff, migration prompt, verify snapshot, and machine-state files so sessions can migrate without rereading the whole repository.
"""


def run_research_audit(
    project: str,
    *,
    repo_root: Path | None = None,
    config_path: Path | None = None,
) -> dict[str, Any]:
    root = find_repo_root(repo_root)
    cfg, paths = load_config(project, config_path=config_path)
    del cfg
    spec = default_limit_up_spec()
    manifest_path = paths.meta_dir / "run_manifest.json"
    has_project_bars = table_row_count(paths.db_path, "bars", freq="1d") > 0 or table_row_count(paths.db_path, "bars_clean", freq="1d") > 0
    findings = [
        {
            "area": "standalone_vs_pipeline",
            "status": "pass" if _script_uses_core(root / "scripts" / "run_limit_up_screening.py", "build_limit_up_rank_artifacts") else "fail",
            "detail": "Standalone strategy entrypoint uses the same audited research core as the modular steps.",
        },
        {
            "area": "weekday_contract",
            "status": "pass" if _weekday_contract_ok() else "fail",
            "detail": "Tuesday rebalance helper returns only weekday=1 dates.",
        },
        {
            "area": "strategy_defaults",
            "status": "pass" if int(spec.limit_days_window) == 250 else "fail",
            "detail": "Limit-up window defaults are centralized in the schema and set to 250 trading days.",
        },
        {
            "area": "manifest_paths",
            "status": "warn" if _manifest_has_stale_paths(manifest_path, root) else "pass",
            "detail": "Manifest path block should point to the current repository root rather than a stale machine-specific location.",
        },
        {
            "area": "reproducible_project_artifacts",
            "status": "pass" if paths.universe_path.exists() and has_project_bars else "warn",
            "detail": "The default project needs both a frozen universe and usable local bars before any historical claim is treated as reproducible.",
        },
    ]

    docs_dir = root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    system_audit_path = docs_dir / "SYSTEM_AUDIT.md"
    failure_modes_path = docs_dir / "FAILURE_MODES.md"
    decision_log_path = docs_dir / "DECISION_LOG.md"

    system_audit_path.write_text(_build_system_audit_markdown(project, findings), encoding="utf-8")
    failure_modes_path.write_text(_build_failure_modes_markdown(), encoding="utf-8")
    decision_log_path.write_text(_build_decision_log_markdown(), encoding="utf-8")

    return {
        "system_audit_path": str(system_audit_path),
        "failure_modes_path": str(failure_modes_path),
        "decision_log_path": str(decision_log_path),
        "findings": findings,
    }
