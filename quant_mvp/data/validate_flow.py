from __future__ import annotations

from pathlib import Path
from typing import Any

from ..config import load_config
from ..memory.writeback import load_machine_state, save_machine_state, sync_project_state, write_verify_snapshot
from ..research_readiness import build_research_readiness_state_update, evaluate_research_readiness, write_research_readiness_artifacts
from ..universe import load_universe_codes
from .cleaning import clean_project_bars
from .coverage_gap import (
    apply_auto_refreeze,
    build_coverage_gap_ledger,
    ledger_with_artifact_paths,
    reload_project_config,
    write_coverage_gap_artifacts,
    write_coverage_gap_decision_to_manifest,
)
from .validation import validate_project_data


def _validate_snapshot(
    *,
    project: str,
    cfg: dict[str, Any],
    paths,
    universe_codes: list[str],
) -> tuple[Any, Any, Path, Path, Path]:
    report = validate_project_data(
        project=project,
        db_path=Path(str(cfg["db_path"])),
        freq=str(cfg["freq"]),
        universe_codes=universe_codes,
        provider_name=str(cfg.get("data_provider", {}).get("provider", "akshare")),
        data_quality_cfg=cfg.get("data_quality"),
        limit_threshold=float(cfg.get("limit_up_threshold", 0.095)),
    )
    readiness = evaluate_research_readiness(report=report, cfg=cfg)
    readiness_md_path, readiness_json_path = write_research_readiness_artifacts(
        meta_dir=paths.meta_dir,
        report=report,
        decision=readiness,
    )
    data_quality_md_path = paths.meta_dir / "DATA_QUALITY_REPORT.md"
    lines = [
        "# Data Quality Report",
        "",
        f"- project: {report.project}",
        f"- frequency: {report.frequency}",
        f"- provider: {report.source_provider}",
        f"- coverage_ratio: {report.coverage_ratio:.4f}",
        f"- covered_symbols: {report.covered_symbols}",
        f"- universe_symbols: {report.universe_symbols}",
        f"- raw_rows: {report.raw_rows}",
        f"- cleaned_rows: {report.cleaned_rows}",
        f"- validated_rows: {report.validated_rows}",
        f"- duplicate_rows: {report.duplicate_rows}",
        f"- missing_rows: {report.missing_rows}",
        f"- zero_volume_rows: {report.zero_volume_rows}",
        f"- limit_locked_rows: {report.limit_locked_rows}",
        "",
        "## Findings",
    ]
    if report.findings:
        lines.extend(f"- {item.code}: {item.message} ({item.count})" for item in report.findings)
    else:
        lines.append("- No critical findings.")
    data_quality_md_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return report, readiness, readiness_md_path, readiness_json_path, data_quality_md_path


def run_data_validate_flow(
    *,
    project: str,
    config_path: Path | None = None,
    full_refresh: bool = False,
    skip_clean: bool = False,
) -> dict[str, Any]:
    cfg, paths = load_config(project, config_path=config_path)
    config_file = Path(config_path) if config_path is not None else paths.config_path
    universe_codes = load_universe_codes(project)
    if skip_clean:
        clean_stats = {
            "source_table": str((cfg.get("data_quality") or {}).get("source_table", "bars")),
            "clean_table": str((cfg.get("data_quality") or {}).get("clean_table", "bars_clean")),
            "updated_codes": [],
            "scanned_rows": 0,
            "kept_rows": 0,
            "dropped_rows": 0,
            "repaired_rows": 0,
            "warned_rows": 0,
            "issue_counts_by_code": {},
            "issue_counts_by_type": {},
            "summary_path": str(paths.meta_dir / "data_quality_summary.json"),
            "by_symbol_path": str(paths.meta_dir / "data_quality_by_symbol.csv"),
            "skipped_clean_rebuild": True,
        }
    else:
        clean_stats = clean_project_bars(
            project=project,
            db_path=Path(str(cfg["db_path"])),
            freq=str(cfg["freq"]),
            codes=universe_codes,
            meta_dir=paths.meta_dir,
            data_quality_cfg=cfg.get("data_quality"),
            full_refresh=full_refresh,
        )

    report, readiness, readiness_md_path, readiness_json_path, data_quality_md_path = _validate_snapshot(
        project=project,
        cfg=cfg,
        paths=paths,
        universe_codes=universe_codes,
    )
    coverage_gap_ledger = build_coverage_gap_ledger(
        project=project,
        db_path=Path(str(cfg["db_path"])),
        freq=str(cfg["freq"]),
        universe_codes=universe_codes,
        cfg=cfg,
        meta_dir=paths.meta_dir,
        data_quality_cfg=cfg.get("data_quality"),
    )
    refreeze_result = apply_auto_refreeze(
        project=project,
        config_path=config_file,
        ledger=coverage_gap_ledger,
    )
    if refreeze_result is not None:
        cfg, paths = reload_project_config(project, config_file)
        universe_codes = load_universe_codes(project)
        report, readiness, readiness_md_path, readiness_json_path, data_quality_md_path = _validate_snapshot(
            project=project,
            cfg=cfg,
            paths=paths,
            universe_codes=universe_codes,
        )

    coverage_gap_md_path, coverage_gap_json_path, coverage_gap_csv_path = write_coverage_gap_artifacts(
        meta_dir=paths.meta_dir,
        ledger=coverage_gap_ledger,
    )
    coverage_gap_ledger = ledger_with_artifact_paths(
        coverage_gap_ledger,
        markdown_path=coverage_gap_md_path,
        json_path=coverage_gap_json_path,
        csv_path=coverage_gap_csv_path,
        refreeze_result=refreeze_result,
    )
    manifest_path = write_coverage_gap_decision_to_manifest(
        project=project,
        ledger=coverage_gap_ledger,
        symbols_source="project_universe_codes",
    )
    state_update = build_research_readiness_state_update(report=report, decision=readiness)
    state_update["last_verified_capability"] = "data_validate refreshed cleaned bars, coverage-gap artifacts, and research readiness."
    sync_project_state(project, state_update)

    _, state = load_machine_state(project)
    state["stage0a_decision"] = {
        **coverage_gap_ledger.decision.to_dict(),
        "ledger_markdown_path": str(coverage_gap_md_path),
        "ledger_json_path": str(coverage_gap_json_path),
        "ledger_csv_path": str(coverage_gap_csv_path),
    }
    save_machine_state(project, state)
    write_verify_snapshot(
        project,
        {
            "passed_commands": [f"python -m quant_mvp data_validate --project {project}"],
            "failed_commands": [],
            "default_project_data_status": state_update.get("data_status", "unknown"),
            "conclusion_boundary_engineering": "Validated data recovery, coverage-gap analysis, and readiness writeback all executed.",
            "conclusion_boundary_research": (
                "Promotion-grade research can proceed on the current validated snapshot."
                if readiness.ready
                else "Coverage improved, but the readiness gate is still blocking broad research claims."
            ),
            "last_verified_capability": "data_validate refreshed readiness artifacts and tracked memory.",
        },
    )
    return {
        "clean_stats": clean_stats,
        "report": report.to_dict(),
        "research_readiness": readiness.to_dict(),
        "data_quality_markdown_path": str(data_quality_md_path),
        "readiness_markdown_path": str(readiness_md_path),
        "readiness_json_path": str(readiness_json_path),
        "coverage_gap_ledger": coverage_gap_ledger.to_dict(),
        "coverage_gap_markdown_path": str(coverage_gap_md_path),
        "coverage_gap_json_path": str(coverage_gap_json_path),
        "coverage_gap_csv_path": str(coverage_gap_csv_path),
        "refreeze_result": refreeze_result.to_dict() if refreeze_result is not None else None,
        "manifest_path": str(manifest_path),
    }
