from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description="Wrapper for scripts/steps/30_bt_rebalance.py")
    parser.add_argument("--project", type=str, default="2026Q1_mom")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--topn-max", type=int, default=None)
    parser.add_argument("--cash", type=float, default=None)
    parser.add_argument("--commission", type=float, default=None)
    parser.add_argument("--stamp-duty", type=float, default=None)
    parser.add_argument("--slippage", type=float, default=None)
    parser.add_argument("--save", type=str, default="auto")
    parser.add_argument("--no-show", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    cmd = [
        sys.executable,
        str(root / "scripts" / "steps" / "30_bt_rebalance.py"),
        "--project",
        args.project,
        "--save",
        args.save,
    ]
    if args.config:
        cmd.extend(["--config", str(args.config)])
    if args.topn_max is not None:
        cmd.extend(["--topn-max", str(args.topn_max)])
    if args.cash is not None:
        cmd.extend(["--cash", str(args.cash)])
    if args.commission is not None:
        cmd.extend(["--commission", str(args.commission)])
    if args.stamp_duty is not None:
        cmd.extend(["--stamp-duty", str(args.stamp_duty)])
    if args.slippage is not None:
        cmd.extend(["--slippage", str(args.slippage)])
    if args.no_show:
        cmd.append("--no-show")

    raise SystemExit(subprocess.run(cmd, cwd=root).returncode)


if __name__ == "__main__":
    main()
