from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quant_mvp.config import load_config
from quant_mvp.manifest import update_run_manifest
from quant_mvp.reporting import generate_report_markdown


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate project-scoped markdown report.")
    parser.add_argument("--project", type=str, default="2026Q1_mom")
    parser.add_argument("--config", type=Path, default=None)
    _ = parser.parse_args()
    args = _

    load_config(args.project, config_path=args.config)
    report_path = generate_report_markdown(args.project)
    update_run_manifest(args.project, {"report_path": str(report_path)})
    print(f"[report] generated={report_path}")


if __name__ == "__main__":
    main()
