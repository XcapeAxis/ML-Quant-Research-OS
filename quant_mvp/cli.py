from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from .agent.runner import run_agent_cycle
from .factors import build_factors_for_project
from .memory.writeback import bootstrap_memory_files, sync_project_state
from .platform.readiness import project_doctor
from .platform.schemas import PipelineName
from .platform.settings import load_platform_settings
from .project import find_repo_root
from .promotion import promote_candidate
from .research_audit import run_research_audit
from .config import load_config
from .data.cleaning import clean_project_bars
from .data.validation import validate_project_data
from .universe import load_universe_codes


TASK_TO_SCRIPT = {
    "universe": "scripts/steps/10_symbols.py",
    "update": "scripts/steps/11_update_bars.py",
    "clean": "scripts/steps/12_clean_bars.py",
    "rank": "scripts/steps/20_build_rank.py",
    "backtest": "scripts/steps/30_bt_rebalance.py",
    "strategy": "scripts/run_limit_up_screening.py",
    "baselines": "scripts/steps/31_bt_baselines.py",
    "cost": "scripts/steps/32_cost_sweep.py",
    "walk_forward": "scripts/steps/33_walk_forward.py",
    "audit": "scripts/audit_db.py",
    "report": "scripts/steps/40_make_report.py",
}


def _run_script(script_rel: str, project: str, extra_args: list[str]) -> int:
    root = find_repo_root()
    script_path = root / script_rel
    if not script_path.exists():
        raise FileNotFoundError(f"Task script not found: {script_path}")
    cmd = [sys.executable, str(script_path), "--project", project, *extra_args]
    result = subprocess.run(cmd, cwd=root)
    return int(result.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(description="Quant MVP unified CLI.")
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="Run one pipeline task")
    run_parser.add_argument("--project", type=str, required=True)
    run_parser.add_argument(
        "--task",
        type=str,
        required=True,
        choices=[*TASK_TO_SCRIPT.keys(), "factors"],
    )
    run_parser.add_argument("--factors", type=str, default="mom20,rev5,vol20,range,vol_surge,ma_gap")
    run_parser.add_argument("--freq", type=str, default="1d")
    run_parser.add_argument("--start", type=str, default=None)
    run_parser.add_argument("--end", type=str, default=None)
    run_parser.add_argument("task_args", nargs=argparse.REMAINDER)

    doctor_parser = sub.add_parser("doctor", help="Check whether a project is ready to run")
    doctor_parser.add_argument("--project", type=str, required=True)
    doctor_parser.add_argument("--config", type=Path, default=None)
    doctor_parser.add_argument(
        "--pipeline",
        type=str,
        default=PipelineName.full_analysis_pack.value,
        choices=[item.value for item in PipelineName],
    )

    bootstrap_parser = sub.add_parser("agent_bootstrap", help="Create AGENTS and project memory files")
    bootstrap_parser.add_argument("--project", type=str, required=True)

    cycle_parser = sub.add_parser("agent_cycle", help="Run one controlled research cycle")
    cycle_parser.add_argument("--project", type=str, required=True)
    cycle_parser.add_argument("--config", type=Path, default=None)
    cycle_parser.add_argument("--dry-run", action="store_true")

    reflect_parser = sub.add_parser("agent_reflect", help="Alias for a dry-run agent cycle")
    reflect_parser.add_argument("--project", type=str, required=True)
    reflect_parser.add_argument("--config", type=Path, default=None)

    memory_parser = sub.add_parser("agent_memory_sync", help="Rewrite project state from current repo facts")
    memory_parser.add_argument("--project", type=str, required=True)

    validate_parser = sub.add_parser("data_validate", help="Validate cleaned data and write quality reports")
    validate_parser.add_argument("--project", type=str, required=True)
    validate_parser.add_argument("--config", type=Path, default=None)
    validate_parser.add_argument("--full-refresh", action="store_true")

    audit_parser = sub.add_parser("research_audit", help="Write repo audit documents")
    audit_parser.add_argument("--project", type=str, required=True)
    audit_parser.add_argument("--config", type=Path, default=None)

    promote_parser = sub.add_parser("promote_candidate", help="Evaluate the current candidate against promotion gates")
    promote_parser.add_argument("--project", type=str, required=True)
    promote_parser.add_argument("--config", type=Path, default=None)

    args = parser.parse_args()

    if args.command == "run":
        if args.task == "factors":
            names = [name.strip() for name in args.factors.split(",") if name.strip()]
            paths = build_factors_for_project(
                project=args.project,
                factor_names=names,
                freq=args.freq,
                start=args.start,
                end=args.end,
            )
            for path in paths:
                print(f"[factor] {path}")
            return

        extra = list(args.task_args)
        if extra and extra[0] == "--":
            extra = extra[1:]
        code = _run_script(TASK_TO_SCRIPT[args.task], project=args.project, extra_args=extra)
        raise SystemExit(code)

    if args.command == "doctor":
        settings = load_platform_settings(repo_root=find_repo_root())
        result = project_doctor(
            settings=settings,
            project=args.project,
            pipeline=args.pipeline,
            config_path_override=args.config,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(1 if result["blocking_issue_details"] else 0)

    if args.command == "agent_bootstrap":
        result = bootstrap_memory_files(args.project, repo_root=find_repo_root())
        print(json.dumps({key: str(value) for key, value in result.items()}, ensure_ascii=False, indent=2))
        return

    if args.command == "agent_cycle":
        result = run_agent_cycle(
            project=args.project,
            dry_run=args.dry_run,
            repo_root=find_repo_root(),
            config_path=args.config,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == "agent_reflect":
        result = run_agent_cycle(
            project=args.project,
            dry_run=True,
            repo_root=find_repo_root(),
            config_path=args.config,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == "agent_memory_sync":
        paths = bootstrap_memory_files(args.project, repo_root=find_repo_root())
        cfg, resolved_paths = load_config(args.project)
        summary = {
            "phase": "Phase 1 Research OS",
            "strategy_mode": cfg.get("strategy_mode"),
            "config_path": str(resolved_paths.config_path),
            "meta_dir": str(resolved_paths.meta_dir),
            "artifacts_dir": str(resolved_paths.artifacts_dir),
        }
        state_path = sync_project_state(args.project, summary, repo_root=find_repo_root())
        print(json.dumps({"project_state_path": str(state_path), "bootstrap": {k: str(v) for k, v in paths.items()}}, ensure_ascii=False, indent=2))
        return

    if args.command == "data_validate":
        cfg, paths = load_config(args.project, config_path=args.config)
        universe = load_universe_codes(args.project)
        clean_stats = clean_project_bars(
            project=args.project,
            db_path=Path(cfg["db_path"]),
            freq=str(cfg["freq"]),
            codes=universe,
            meta_dir=paths.meta_dir,
            data_quality_cfg=cfg.get("data_quality"),
            full_refresh=args.full_refresh,
        )
        report = validate_project_data(
            project=args.project,
            db_path=Path(cfg["db_path"]),
            freq=str(cfg["freq"]),
            universe_codes=universe,
            provider_name=str(cfg.get("data_provider", {}).get("provider", "akshare")),
            data_quality_cfg=cfg.get("data_quality"),
            limit_threshold=float(cfg.get("limit_up_threshold", 0.095)),
        )
        md_path = paths.meta_dir / "DATA_QUALITY_REPORT.md"
        lines = [
            "# Data Quality Report",
            "",
            f"- project: {report.project}",
            f"- frequency: {report.frequency}",
            f"- provider: {report.source_provider}",
            f"- coverage_ratio: {report.coverage_ratio:.4f}",
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
        md_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        print(json.dumps({"clean_stats": clean_stats, "report": report.to_dict(), "markdown_path": str(md_path)}, ensure_ascii=False, indent=2))
        return

    if args.command == "research_audit":
        result = run_research_audit(args.project, repo_root=find_repo_root(), config_path=args.config)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == "promote_candidate":
        result = promote_candidate(args.project, config_path=args.config)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return


if __name__ == "__main__":
    main()
