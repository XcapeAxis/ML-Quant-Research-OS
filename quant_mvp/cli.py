from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from .agent.subagent_controller import (
    archive_subagent,
    block_subagent,
    cancel_subagent,
    merge_subagent,
    plan_subagents,
    refactor_subagent,
    retire_subagent,
    sync_subagent_memory,
)
from .agent.subagent_models import SubagentTaskProfile
from .agent.iterative_loop import render_iterative_checkpoint, run_iterative_loop
from .agent.runner import run_agent_cycle
from .data import run_data_validate_flow
from .factors import build_factors_for_project
from .memory.writeback import (
    _looks_data_blocked_text,
    bootstrap_memory_files,
    generate_handoff,
    load_machine_state,
    sync_project_state,
    write_verify_snapshot,
)
from .platform.readiness import project_doctor
from .platform.schemas import PipelineName
from .platform.settings import load_platform_settings
from .project import find_repo_root
from .promotion import promote_candidate
from .research_audit import run_research_audit
from .config import load_config
from .coverage_recovery import run_coverage_recovery
from .f1_pipeline import run_f1_train
from .f1_verify import run_f1_verify
from .f2_pipeline import run_f2_train
from .f2_verify import run_f2_verify
from .excel_export import run_excel_export
from .r1_pipeline import run_r1_verify
from .strategy_campaign import run_baseline_strategy_diagnostic
from .superagent import branch_review, mission_status, mission_tick
from .universe import materialize_universe_from_project_contract


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

    universe_parser = sub.add_parser("materialize_universe", help="Materialize universe_codes.txt from the project contract")
    universe_parser.add_argument("--project", type=str, required=True)
    universe_parser.add_argument("--config", type=Path, default=None)

    bootstrap_parser = sub.add_parser("memory_bootstrap", help="Create tracked memory files and migrate legacy memory")
    bootstrap_parser.add_argument("--project", type=str, required=True)

    agent_bootstrap_parser = sub.add_parser("agent_bootstrap", help="Alias for memory_bootstrap")
    agent_bootstrap_parser.add_argument("--project", type=str, required=True)

    cycle_parser = sub.add_parser("agent_cycle", help="Run one controlled research cycle")
    cycle_parser.add_argument("--project", type=str, required=True)
    cycle_parser.add_argument("--config", type=Path, default=None)
    cycle_parser.add_argument("--dry-run", action="store_true")

    mission_tick_parser = sub.add_parser("mission_tick", help="Run the multi-branch mission orchestrator")
    mission_tick_parser.add_argument("--project", type=str, required=True)
    mission_tick_parser.add_argument("--config", type=Path, default=None)
    mission_tick_parser.add_argument("--dry-run", action="store_true")
    mission_tick_parser.add_argument("--max-branches", type=int, default=3)
    mission_tick_parser.add_argument("--legacy-single-branch", action="store_true")

    mission_status_parser = sub.add_parser("mission_status", help="Show the current mission and latest branch states")
    mission_status_parser.add_argument("--project", type=str, required=True)

    branch_review_parser = sub.add_parser("branch_review", help="Change one branch state before the next mission tick")
    branch_review_parser.add_argument("--project", type=str, required=True)
    branch_review_parser.add_argument("--branch", type=str, required=True)
    branch_review_parser.add_argument("--action", type=str, choices=["keep", "hold", "retire", "promote"], required=True)

    iterative_parser = sub.add_parser("iterative_run", help="Run a bounded higher-order automation loop")
    iterative_parser.add_argument("--project", type=str, required=True)
    iterative_parser.add_argument("--config", type=Path, default=None)
    iterative_parser.add_argument("--target-productive-minutes", type=int, default=40)
    iterative_parser.add_argument("--target-iterations", type=int, default=4)
    iterative_parser.add_argument("--max-iterations", type=int, default=6)
    iterative_parser.add_argument("--min-substantive-actions", type=int, default=2)
    iterative_parser.add_argument("--target-substantive-actions", type=int, default=3)
    iterative_parser.add_argument("--clarify-only-limit", type=int, default=1)
    iterative_parser.add_argument("--format", type=str, choices=["json", "checkpoint"], default="json")

    reflect_parser = sub.add_parser("agent_reflect", help="Alias for a dry-run agent cycle")
    reflect_parser.add_argument("--project", type=str, required=True)
    reflect_parser.add_argument("--config", type=Path, default=None)

    memory_parser = sub.add_parser("memory_sync", help="Refresh tracked project state and machine summary")
    memory_parser.add_argument("--project", type=str, required=True)
    memory_parser.add_argument("--config", type=Path, default=None)

    agent_memory_parser = sub.add_parser("agent_memory_sync", help="Alias for memory_sync")
    agent_memory_parser.add_argument("--project", type=str, required=True)
    agent_memory_parser.add_argument("--config", type=Path, default=None)

    handoff_parser = sub.add_parser("generate_handoff", help="Regenerate tracked handoff and migration prompt files")
    handoff_parser.add_argument("--project", type=str, required=True)

    subagent_plan_parser = sub.add_parser("subagent_plan", help="Evaluate and optionally instantiate a controlled subagent plan")
    subagent_plan_parser.add_argument("--project", type=str, required=True)
    subagent_plan_parser.add_argument("--task-summary", type=str, required=True)
    subagent_plan_parser.add_argument("--gate", type=str, choices=["OFF", "AUTO", "FORCE"], default="AUTO")
    subagent_plan_parser.add_argument("--breadth", type=int, default=1)
    subagent_plan_parser.add_argument("--independence", type=float, default=0.0)
    subagent_plan_parser.add_argument("--file-overlap", type=float, default=1.0)
    subagent_plan_parser.add_argument("--validation-load", type=float, default=0.0)
    subagent_plan_parser.add_argument("--coordination-cost", type=float, default=0.0)
    subagent_plan_parser.add_argument("--risk-isolation", type=float, default=0.0)
    subagent_plan_parser.add_argument("--focus-tag", action="append", default=[])
    subagent_plan_parser.add_argument("--activate", action="store_true")

    subagent_sync_parser = sub.add_parser("subagent_sync", help="Refresh tracked subagent registry and summaries")
    subagent_sync_parser.add_argument("--project", type=str, required=True)

    subagent_retire_parser = sub.add_parser("subagent_retire", help="Retire a subagent and keep the event in tracked memory")
    subagent_retire_parser.add_argument("--project", type=str, required=True)
    subagent_retire_parser.add_argument("--id", type=str, required=True)
    subagent_retire_parser.add_argument("--summary", type=str, required=True)

    subagent_archive_parser = sub.add_parser("subagent_archive", help="Archive a subagent and keep the event in tracked memory")
    subagent_archive_parser.add_argument("--project", type=str, required=True)
    subagent_archive_parser.add_argument("--id", type=str, required=True)
    subagent_archive_parser.add_argument("--summary", type=str, required=True)

    subagent_refactor_parser = sub.add_parser("subagent_refactor", help="Mark a subagent as refactored and preserve the transition")
    subagent_refactor_parser.add_argument("--project", type=str, required=True)
    subagent_refactor_parser.add_argument("--id", type=str, required=True)
    subagent_refactor_parser.add_argument("--summary", type=str, required=True)

    subagent_block_parser = sub.add_parser("subagent_block", help="Mark a subagent as blocked and keep the event in tracked memory")
    subagent_block_parser.add_argument("--project", type=str, required=True)
    subagent_block_parser.add_argument("--id", type=str, required=True)
    subagent_block_parser.add_argument("--summary", type=str, required=True)

    subagent_cancel_parser = sub.add_parser("subagent_cancel", help="Cancel a subagent and keep the event in tracked memory")
    subagent_cancel_parser.add_argument("--project", type=str, required=True)
    subagent_cancel_parser.add_argument("--id", type=str, required=True)
    subagent_cancel_parser.add_argument("--summary", type=str, required=True)

    subagent_merge_parser = sub.add_parser("subagent_merge", help="Merge one subagent into another and preserve lineage")
    subagent_merge_parser.add_argument("--project", type=str, required=True)
    subagent_merge_parser.add_argument("--id", type=str, required=True)
    subagent_merge_parser.add_argument("--into", type=str, required=True)
    subagent_merge_parser.add_argument("--summary", type=str, required=True)

    verify_parser = sub.add_parser("verify_snapshot", help="Write the latest verification snapshot into tracked memory")
    verify_parser.add_argument("--project", type=str, required=True)
    verify_parser.add_argument("--passed-command", action="append", default=[])
    verify_parser.add_argument("--failed-command", action="append", default=[])
    verify_parser.add_argument("--data-status", type=str, default="unknown")
    verify_parser.add_argument("--engineering-boundary", type=str, default="unknown")
    verify_parser.add_argument("--research-boundary", type=str, default="unknown")
    verify_parser.add_argument("--last-verified-capability", type=str, default=None)

    validate_parser = sub.add_parser("data_validate", help="Validate cleaned data and write quality reports")
    validate_parser.add_argument("--project", type=str, required=True)
    validate_parser.add_argument("--config", type=Path, default=None)
    validate_parser.add_argument("--full-refresh", action="store_true")
    validate_parser.add_argument("--skip-clean", action="store_true")

    audit_parser = sub.add_parser("research_audit", help="Write repo audit documents")
    audit_parser.add_argument("--project", type=str, required=True)
    audit_parser.add_argument("--config", type=Path, default=None)

    promote_parser = sub.add_parser("promote_candidate", help="Evaluate the current candidate against promotion gates")
    promote_parser.add_argument("--project", type=str, required=True)
    promote_parser.add_argument("--config", type=Path, default=None)

    f1_parser = sub.add_parser("f1_train", help="Run the first ElasticNet factor-model MVP")
    f1_parser.add_argument("--project", type=str, required=True)
    f1_parser.add_argument("--config", type=Path, default=None)

    f1_verify_parser = sub.add_parser("f1_verify", help="Run the bounded F1 vs control verifier on one shared TopN shell")
    f1_verify_parser.add_argument("--project", type=str, required=True)
    f1_verify_parser.add_argument("--config", type=Path, default=None)

    f2_parser = sub.add_parser("f2_train", help="Run the bounded structured latent deep-factor challenger")
    f2_parser.add_argument("--project", type=str, required=True)
    f2_parser.add_argument("--config", type=Path, default=None)

    f2_verify_parser = sub.add_parser("f2_verify", help="Run the bounded F2 vs F1 vs control verifier on one shared TopN shell")
    f2_verify_parser.add_argument("--project", type=str, required=True)
    f2_verify_parser.add_argument("--config", type=Path, default=None)

    excel_export_parser = sub.add_parser("excel_export", help="Export the Excel console feed and workbook")
    excel_export_parser.add_argument("--project", type=str, required=True)
    excel_export_parser.add_argument("--config", type=Path, default=None)

    r1_verify_parser = sub.add_parser("r1_verify", help="Run the bounded predictive-error regime-overlay verifier on one shared TopN shell")
    r1_verify_parser.add_argument("--project", type=str, required=True)
    r1_verify_parser.add_argument("--config", type=Path, default=None)

    diagnostic_parser = sub.add_parser(
        "baseline_strategy_diagnostic",
        help="Run the baseline strategy diagnostic campaign and write tracked research memory",
    )
    diagnostic_parser.add_argument("--project", type=str, required=True)
    diagnostic_parser.add_argument("--config", type=Path, default=None)
    diagnostic_parser.add_argument("--verified-command", action="append", default=[])

    recovery_parser = sub.add_parser(
        "coverage_recovery",
        help="Audit canonical-universe missingness, run missing-only backfill, and refresh tracked coverage memory",
    )
    recovery_parser.add_argument("--project", type=str, required=True)
    recovery_parser.add_argument("--config", type=Path, default=None)
    recovery_parser.add_argument("--execute-backfill", action="store_true")
    recovery_parser.add_argument("--max-backfill-symbols", type=int, default=None)
    recovery_parser.add_argument("--workers", type=int, default=4)
    recovery_parser.add_argument("--rerun-baseline", action="store_true")

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

    if args.command == "materialize_universe":
        result = materialize_universe_from_project_contract(args.project, config_path=args.config)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command in {"memory_bootstrap", "agent_bootstrap"}:
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

    if args.command == "mission_tick":
        result = mission_tick(
            project=args.project,
            dry_run=args.dry_run,
            max_branches=args.max_branches,
            repo_root=find_repo_root(),
            config_path=args.config,
            legacy_single_branch=args.legacy_single_branch,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == "mission_status":
        result = mission_status(project=args.project, repo_root=find_repo_root())
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == "branch_review":
        result = branch_review(
            project=args.project,
            branch_id=args.branch,
            action=args.action,
            repo_root=find_repo_root(),
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == "iterative_run":
        result = run_iterative_loop(
            project=args.project,
            target_productive_minutes=args.target_productive_minutes,
            target_iterations=args.target_iterations,
            max_iterations=args.max_iterations,
            min_substantive_actions=args.min_substantive_actions,
            target_substantive_actions=args.target_substantive_actions,
            clarify_only_limit=args.clarify_only_limit,
            repo_root=find_repo_root(),
            config_path=args.config,
        )
        if args.format == "checkpoint":
            print(render_iterative_checkpoint(result))
        else:
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

    if args.command in {"memory_sync", "agent_memory_sync"}:
        paths = bootstrap_memory_files(args.project, repo_root=find_repo_root())
        cfg, resolved_paths = load_config(args.project, config_path=args.config)
        _, state = load_machine_state(args.project, repo_root=find_repo_root())
        doctor_command = f"python -m quant_mvp doctor --project {args.project}"
        if args.config:
            doctor_command += f" --config {args.config}"
        doctor_path = resolved_paths.meta_dir / "platform_doctor.json"
        doctor_payload = {}
        if doctor_path.exists():
            try:
                doctor_payload = json.loads(doctor_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                doctor_payload = {}
        blocking_issue = ""
        next_action = ""
        data_status = "unknown"
        if doctor_payload:
            blocking_issues = list(doctor_payload.get("blocking_issues", []) or [])
            blocking_issue = str(blocking_issues[0]).strip() if blocking_issues else ""
            issue_details = list(doctor_payload.get("blocking_issue_details", []) or [])
            if issue_details:
                next_action = str(issue_details[0].get("suggestion", "")).strip()
            if doctor_payload.get("ready"):
                data_status = "validation-ready"
            elif doctor_payload.get("universe_exists"):
                data_status = "prerequisites-blocked"
        current_blocker = str(state.get("current_blocker") or "").strip()
        current_boundary = str(state.get("current_capability_boundary") or "").strip()
        last_verified_capability = str(state.get("last_verified_capability") or "").strip()
        next_priority_action = str(state.get("next_priority_action") or "").strip()
        cleared_data_blocker = False
        if blocking_issue:
            current_blocker = blocking_issue
            if not next_action:
                next_action = next_priority_action
            current_boundary = (
                "Current work is limited to rebuilding research inputs and truthful contracts. No strategy branch should be treated as validated until OKX inputs are usable."
            )
            last_verified_capability = (
                "Doctor confirmed OKX upstream access and the frozen universe, but blocked promotion because local OKX bars are still missing."
            )
        else:
            if _looks_data_blocked_text(current_blocker):
                current_blocker = "none"
                cleared_data_blocker = True
            if not current_boundary or _looks_data_blocked_text(current_boundary):
                current_boundary = "Doctor shows the research floor is available. Continue only through bounded experiments and truthful writeback."
            if cleared_data_blocker or not next_priority_action or _looks_data_blocked_text(next_priority_action):
                next_priority_action = "Run the next bounded experiment bundle and write the evidence back into tracked memory."
            if not last_verified_capability or _looks_data_blocked_text(last_verified_capability):
                last_verified_capability = "Doctor confirmed usable OKX local coverage and reachable upstream checks."
        summary = {
            "current_task": "Prove the crypto plus OKX research loop before any demo or live work.",
            "current_phase": "Phase 0 Backtest First",
            "current_blocker": current_blocker or "none",
            "current_capability_boundary": current_boundary or "Tracked memory sync refreshed the current snapshot; it did not validate any new research claim.",
            "next_priority_action": next_action or next_priority_action or "Run handoff generation.",
            "last_verified_capability": last_verified_capability or f"Tracked memory synced from config {resolved_paths.config_path.name}.",
        }
        state_path = sync_project_state(args.project, summary, repo_root=find_repo_root())
        if doctor_payload:
            passed_commands = list((state.get("verify_last", {}) or {}).get("passed_commands", []) or [])
            failed_commands = list((state.get("verify_last", {}) or {}).get("failed_commands", []) or [])
            if blocking_issue:
                if doctor_command not in failed_commands:
                    failed_commands.append(doctor_command)
                passed_commands = [cmd for cmd in passed_commands if cmd != doctor_command]
            else:
                if doctor_command not in passed_commands:
                    passed_commands.append(doctor_command)
                failed_commands = [cmd for cmd in failed_commands if cmd != doctor_command]
            write_verify_snapshot(
                args.project,
                {
                    "passed_commands": passed_commands,
                    "failed_commands": failed_commands,
                    "default_project_data_status": data_status,
                    "conclusion_boundary_engineering": (
                        "OKX upstream reachability is healthy, but local market bars are still missing for the frozen universe."
                        if blocking_issue
                        else "Doctor has no blocking issue."
                    ),
                    "conclusion_boundary_research": (
                        "Do not treat any candidate as validated until the frozen OKX universe has usable local bars."
                        if blocking_issue
                        else "Research may continue through bounded experiments."
                    ),
                    "last_verified_capability": summary["last_verified_capability"],
                },
                repo_root=find_repo_root(),
            )
        print(
            json.dumps(
                {
                    "project_state_path": str(state_path),
                    "memory_dir": str(resolved_paths.memory_dir),
                    "bootstrap": {k: str(v) for k, v in paths.items()},
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
        return

    if args.command == "generate_handoff":
        result = generate_handoff(args.project, repo_root=find_repo_root())
        print(json.dumps({key: str(value) for key, value in result.items()}, ensure_ascii=False, indent=2))
        return

    if args.command == "subagent_plan":
        result = plan_subagents(
            project=args.project,
            profile=SubagentTaskProfile(
                task_summary=args.task_summary,
                breadth=args.breadth,
                independence=args.independence,
                file_overlap=args.file_overlap,
                validation_load=args.validation_load,
                coordination_cost=args.coordination_cost,
                risk_isolation=args.risk_isolation,
                focus_tags=list(args.focus_tag),
            ),
            gate_mode=args.gate,
            activate=args.activate,
            repo_root=find_repo_root(),
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == "subagent_sync":
        result = sync_subagent_memory(args.project, repo_root=find_repo_root())
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == "subagent_retire":
        result = retire_subagent(args.project, subagent_id=args.id, summary=args.summary, repo_root=find_repo_root())
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == "subagent_archive":
        result = archive_subagent(args.project, subagent_id=args.id, summary=args.summary, repo_root=find_repo_root())
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == "subagent_refactor":
        result = refactor_subagent(args.project, subagent_id=args.id, summary=args.summary, repo_root=find_repo_root())
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == "subagent_block":
        result = block_subagent(args.project, subagent_id=args.id, summary=args.summary, repo_root=find_repo_root())
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == "subagent_cancel":
        result = cancel_subagent(args.project, subagent_id=args.id, summary=args.summary, repo_root=find_repo_root())
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == "subagent_merge":
        result = merge_subagent(
            args.project,
            subagent_id=args.id,
            into_subagent_id=args.into,
            summary=args.summary,
            repo_root=find_repo_root(),
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == "verify_snapshot":
        path = write_verify_snapshot(
            args.project,
            {
                "passed_commands": args.passed_command,
                "failed_commands": args.failed_command,
                "default_project_data_status": args.data_status,
                "conclusion_boundary_engineering": args.engineering_boundary,
                "conclusion_boundary_research": args.research_boundary,
                "last_verified_capability": args.last_verified_capability,
            },
            repo_root=find_repo_root(),
        )
        print(json.dumps({"verify_last_path": str(path)}, ensure_ascii=False, indent=2))
        return

    if args.command == "data_validate":
        result = run_data_validate_flow(
            project=args.project,
            config_path=args.config,
            full_refresh=args.full_refresh,
            skip_clean=args.skip_clean,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == "research_audit":
        result = run_research_audit(args.project, repo_root=find_repo_root(), config_path=args.config)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == "promote_candidate":
        result = promote_candidate(args.project, config_path=args.config)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == "f1_train":
        result = run_f1_train(
            args.project,
            config_path=args.config,
            repo_root=find_repo_root(),
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == "f1_verify":
        result = run_f1_verify(
            args.project,
            config_path=args.config,
            repo_root=find_repo_root(),
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == "f2_train":
        result = run_f2_train(
            args.project,
            config_path=args.config,
            repo_root=find_repo_root(),
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == "f2_verify":
        result = run_f2_verify(
            args.project,
            config_path=args.config,
            repo_root=find_repo_root(),
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == "excel_export":
        result = run_excel_export(
            args.project,
            config_path=args.config,
            repo_root=find_repo_root(),
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == "r1_verify":
        result = run_r1_verify(
            args.project,
            config_path=args.config,
            repo_root=find_repo_root(),
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == "baseline_strategy_diagnostic":
        result = run_baseline_strategy_diagnostic(
            args.project,
            config_path=args.config,
            verified_commands=list(args.verified_command),
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == "coverage_recovery":
        result = run_coverage_recovery(
            args.project,
            config_path=args.config,
            execute_backfill=args.execute_backfill,
            max_backfill_symbols=args.max_backfill_symbols,
            workers=args.workers,
            rerun_baseline=args.rerun_baseline,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return


if __name__ == "__main__":
    main()
