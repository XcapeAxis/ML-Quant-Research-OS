from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    project = "test_performance"
    rank_cmd = [sys.executable, "scripts/steps/20_build_rank.py", "--project", project, "--max-codes-scan", "500"]
    bt_cmd = [sys.executable, "scripts/steps/30_bt_rebalance.py", "--project", project, "--no-show", "--save", "auto"]

    start = time.time()
    subprocess.run(rank_cmd, cwd=ROOT, check=False)
    result = subprocess.run(bt_cmd, cwd=ROOT, check=False, capture_output=True, text=True)
    elapsed = time.time() - start

    print("=== Performance Test ===")
    print(f"Elapsed seconds: {elapsed:.2f}")
    print(f"Backtest return code: {result.returncode}")
    lines = result.stdout.strip().splitlines()
    for line in lines[-10:]:
        print(line)


if __name__ == "__main__":
    main()
