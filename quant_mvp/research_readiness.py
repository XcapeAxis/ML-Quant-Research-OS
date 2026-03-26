from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from .data.contracts import DataQualityReport


@dataclass(frozen=True)
class ResearchReadinessDecision:
    ready: bool
    stage: str
    reasons: list[str]
    checks: dict[str, Any]
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_research_readiness(
    *,
    report: DataQualityReport,
    cfg: Mapping[str, Any],
) -> ResearchReadinessDecision:
    rules = cfg.get("research_readiness", {}) if isinstance(cfg, Mapping) else {}
    min_coverage_ratio = float(rules.get("min_coverage_ratio", 0.95))
    min_covered_symbols = int(rules.get("min_covered_symbols", 1))
    min_validated_rows = int(rules.get("min_validated_rows", 1))

    reasons: list[str] = []
    if report.covered_symbols < min_covered_symbols:
        reasons.append(
            f"Covered symbols {report.covered_symbols} are below the minimum readiness floor {min_covered_symbols}.",
        )
    if report.validated_rows < min_validated_rows:
        reasons.append(
            f"Validated rows {report.validated_rows} are below the minimum readiness floor {min_validated_rows}.",
        )
    if report.coverage_ratio < min_coverage_ratio:
        reasons.append(
            f"Coverage ratio {report.coverage_ratio:.2%} is below the promotion-readiness threshold {min_coverage_ratio:.2%}.",
        )

    if report.covered_symbols <= 0 or report.validated_rows <= 0:
        stage = "empty"
    elif reasons:
        stage = "pilot"
    else:
        stage = "ready"

    checks = {
        "coverage_ratio": report.coverage_ratio,
        "covered_symbols": report.covered_symbols,
        "universe_symbols": report.universe_symbols,
        "validated_rows": report.validated_rows,
        "missing_symbols": report.missing_rows,
        "min_coverage_ratio": min_coverage_ratio,
        "min_covered_symbols": min_covered_symbols,
        "min_validated_rows": min_validated_rows,
    }
    notes = [
        "Research readiness gates data completeness before promotion so pilot subsets do not masquerade as full-universe evidence.",
        "Promotion should measure strategy quality only after data coverage is good enough for the frozen universe definition.",
    ]
    return ResearchReadinessDecision(
        ready=not reasons,
        stage=stage,
        reasons=reasons,
        checks=checks,
        notes=notes,
    )


def build_research_readiness_state_update(
    *,
    report: DataQualityReport,
    decision: ResearchReadinessDecision,
) -> dict[str, str]:
    coverage_summary = (
        f"{decision.stage} coverage: {report.covered_symbols}/{report.universe_symbols} "
        f"symbols with validated bars (coverage_ratio={report.coverage_ratio:.4f}, "
        f"raw_rows={report.raw_rows}, cleaned_rows={report.cleaned_rows}, validated_rows={report.validated_rows})."
    )

    if decision.ready:
        return {
            "current_task": "Keep the default project research-ready so promotion reflects strategy quality rather than data availability noise.",
            "current_phase": "Phase 1 Research OS - research-ready data snapshot",
            "current_blocker": "none",
            "current_capability_boundary": (
                "Validated data coverage now clears the research-readiness gate, so promotion can evaluate strategy quality on the frozen universe definition."
            ),
            "next_priority_action": "Run promotion and treat any remaining failure as a strategy or validation issue rather than a data-coverage issue.",
            "last_verified_capability": "Research readiness gate passed on the current validated data snapshot.",
            "last_failed_capability": "none",
            "data_status": coverage_summary,
        }

    if decision.stage == "empty":
        blocker = "No validated bars are currently available for the frozen universe."
        boundary = "Engineering guardrails exist, but real research is still blocked by missing validated inputs."
        next_action = "Restore validated daily bars for the frozen universe, then rerun data_validate and research_readiness."
    else:
        blocker = (
            f"Research readiness is blocked because coverage is only {report.covered_symbols}/{report.universe_symbols} "
            f"symbols ({report.coverage_ratio:.2%}), below the promotion threshold."
        )
        boundary = (
            "The project can execute on a real-input subset, but promotion and broad research claims remain blocked until coverage clears the readiness gate."
        )
        next_action = (
            "Expand validated coverage or explicitly shrink and refreeze the target universe before trusting promotion results."
        )

    return {
        "current_task": "Keep the default project on validated daily inputs and reach research readiness before interpreting promotion outcomes.",
        "current_phase": (
            "Phase 1 Research OS - input recovery"
            if decision.stage == "empty"
            else "Phase 1 Research OS - pilot real-input recovery"
        ),
        "current_blocker": blocker,
        "current_capability_boundary": boundary,
        "next_priority_action": next_action,
        "last_verified_capability": "Research readiness gate evaluated the current validated data snapshot.",
        "last_failed_capability": "Research readiness gate is still blocking promotion.",
        "data_status": coverage_summary,
    }


def render_research_readiness_markdown(
    *,
    report: DataQualityReport,
    decision: ResearchReadinessDecision,
) -> str:
    lines = [
        "# Research Readiness",
        "",
        f"- ready: {decision.ready}",
        f"- stage: {decision.stage}",
        f"- coverage_ratio: {report.coverage_ratio:.4f}",
        f"- covered_symbols: {report.covered_symbols}",
        f"- universe_symbols: {report.universe_symbols}",
        f"- raw_rows: {report.raw_rows}",
        f"- cleaned_rows: {report.cleaned_rows}",
        f"- validated_rows: {report.validated_rows}",
        "",
        "## Reasons",
    ]
    if decision.reasons:
        lines.extend(f"- {reason}" for reason in decision.reasons)
    else:
        lines.append("- Current validated data snapshot is ready for promotion-grade research checks.")
    lines.extend(["", "## Notes"])
    lines.extend(f"- {note}" for note in decision.notes)
    return "\n".join(lines).rstrip() + "\n"


def write_research_readiness_artifacts(
    *,
    meta_dir: Path,
    report: DataQualityReport,
    decision: ResearchReadinessDecision,
) -> tuple[Path, Path]:
    meta_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = meta_dir / "RESEARCH_READINESS.md"
    json_path = meta_dir / "research_readiness.json"
    markdown_path.write_text(
        render_research_readiness_markdown(report=report, decision=decision),
        encoding="utf-8",
    )
    json_path.write_text(
        json.dumps(
            {
                "report": report.to_dict(),
                "decision": decision.to_dict(),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return markdown_path, json_path
