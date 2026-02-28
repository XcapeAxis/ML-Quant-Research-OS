from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description="Wrapper for scripts/steps/20_build_rank.py")
    parser.add_argument("--project", type=str, default="2026Q1_limit_up")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--lookback", type=int, default=None)
    parser.add_argument("--rebalance-every", type=int, default=None)
    parser.add_argument("--topk", type=int, default=None)
    parser.add_argument("--min-bars", type=int, default=None)
    parser.add_argument("--max-codes-scan", type=int, default=None)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    cmd = [
        sys.executable,
        str(root / "scripts" / "steps" / "20_build_rank.py"),
        "--project",
        args.project,
    ]
    if args.config:
        cmd.extend(["--config", str(args.config)])
    if args.lookback is not None:
        cmd.extend(["--lookback", str(args.lookback)])
    if args.rebalance_every is not None:
        cmd.extend(["--rebalance-every", str(args.rebalance_every)])
    if args.topk is not None:
        cmd.extend(["--topk", str(args.topk)])
    if args.min_bars is not None:
        cmd.extend(["--min-bars", str(args.min_bars)])
    if args.max_codes_scan is not None:
        cmd.extend(["--max-codes-scan", str(args.max_codes_scan)])

    raise SystemExit(subprocess.run(cmd, cwd=root).returncode)


if __name__ == "__main__":
    main()
