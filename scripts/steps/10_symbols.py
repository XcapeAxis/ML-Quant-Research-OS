from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quant_mvp.config import load_config
from quant_mvp.manifest import update_run_manifest
from quant_mvp.security_master import CANONICAL_UNIVERSE_ID, build_security_master


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild the canonical project universe from the security master.")
    parser.add_argument("--project", type=str, default="as_share_research_v1")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--no-archive", action="store_true", help="Skip archiving the previous runtime universe inputs.")
    args = parser.parse_args()

    cfg, _ = load_config(args.project, config_path=args.config)
    del cfg
    result = build_security_master(
        args.project,
        config_path=args.config,
        archive_existing=not args.no_archive,
    )
    update_run_manifest(
        args.project,
        {
            "universe_id": CANONICAL_UNIVERSE_ID,
            "symbols_path": result.symbols_path,
            "security_master_path": result.security_master_path,
            "universe_path": result.universe_path,
            "universe_size": result.count,
            "symbols_source": result.source,
            "security_master_assumptions": result.assumptions,
            "security_master_archive_paths": result.archive_paths,
            "universe_excluded_security_types": result.excluded_security_types,
            "st_policy": "include_as_label_only",
        },
    )
    print(
        f"[symbols] universe_id={result.universe_id} source={result.source} "
        f"saved={result.security_master_path} universe={result.universe_path} size={result.count}",
    )


if __name__ == "__main__":
    main()
