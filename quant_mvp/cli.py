from __future__ import annotations

import argparse
import subprocess
import sys

from .factors import build_factors_for_project
from .project import find_repo_root


TASK_TO_SCRIPT = {
    "universe": "scripts/steps/10_symbols.py",
    "update": "scripts/steps/11_update_bars.py",
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


if __name__ == "__main__":
    main()
