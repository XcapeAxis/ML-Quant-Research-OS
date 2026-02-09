from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quant_mvp.config import load_config
from quant_mvp.factors import build_factors_for_project
from quant_mvp.manifest import update_run_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Build factor library outputs into project-scoped features dir.")
    parser.add_argument("--project", type=str, default="2026Q1_mom")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--factors", type=str, default="mom20,rev5,vol20,range,vol_surge,ma_gap")
    parser.add_argument("--start", type=str, default=None)
    parser.add_argument("--end", type=str, default=None)
    parser.add_argument("--freq", type=str, default=None)
    args = parser.parse_args()

    cfg, _ = load_config(
        args.project,
        config_path=args.config,
        overrides={
            "freq": args.freq,
        },
    )

    names = [name.strip() for name in args.factors.split(",") if name.strip()]
    outputs = build_factors_for_project(
        project=args.project,
        factor_names=names,
        freq=cfg["freq"],
        start=args.start,
        end=args.end,
    )
    update_run_manifest(
        args.project,
        {
            "factor_library": {
                "factors": names,
                "outputs": [str(path) for path in outputs],
            },
            "db_path": str(cfg["db_path"]),
        },
    )
    for path in outputs:
        print(f"[factor] {path}")


if __name__ == "__main__":
    main()
