from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description="Wrapper for scripts/steps/11_update_bars.py")
    parser.add_argument("--project", type=str, default="as_share_research_v1")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--mode", type=str, default="incremental", choices=["incremental", "backfill"])
    parser.add_argument("--start-date", type=str, default=None)
    parser.add_argument("--end-date", type=str, default=None)
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--freq", type=str, default=None)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    cmd = [
        sys.executable,
        str(root / "scripts" / "steps" / "11_update_bars.py"),
        "--project",
        args.project,
        "--mode",
        args.mode,
    ]
    if args.config:
        cmd.extend(["--config", str(args.config)])
    if args.start_date:
        cmd.extend(["--start-date", args.start_date])
    if args.end_date:
        cmd.extend(["--end-date", args.end_date])
    if args.workers is not None:
        cmd.extend(["--workers", str(args.workers)])
    if args.freq:
        cmd.extend(["--freq", args.freq])

    raise SystemExit(subprocess.run(cmd, cwd=root).returncode)


if __name__ == "__main__":
    main()
