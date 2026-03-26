from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quant_mvp.config import load_config
from quant_mvp.data_quality import rebuild_clean_bars, write_quality_outputs
from quant_mvp.db import list_db_codes
from quant_mvp.manifest import update_run_manifest
from quant_mvp.universe import load_universe_codes


def _parse_codes(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip().zfill(6) for item in value.split(",") if item.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean raw OHLCV bars into bars_clean.")
    parser.add_argument("--project", type=str, default="as_share_research_v1")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--freq", type=str, default=None)
    parser.add_argument("--full-refresh", action="store_true")
    parser.add_argument("--codes", type=str, default=None, help="Comma-separated code list.")
    args = parser.parse_args()

    cfg, paths = load_config(
        args.project,
        config_path=args.config,
        overrides={"freq": args.freq},
    )
    paths.ensure_dirs()
    freq = str(cfg["freq"])

    codes = _parse_codes(args.codes)
    if not codes:
        if args.full_refresh:
            codes = sorted(list_db_codes(Path(cfg["db_path"]), freq=freq, data_mode="raw"))
        else:
            codes = load_universe_codes(args.project)

    stats = rebuild_clean_bars(
        db_path=Path(cfg["db_path"]),
        freq=freq,
        codes=codes,
        full_refresh=args.full_refresh,
        data_quality_cfg=cfg.get("data_quality"),
    )
    summary_path, by_symbol_path = write_quality_outputs(
        project=args.project,
        freq=freq,
        meta_dir=paths.meta_dir,
        stats=stats,
    )

    update_run_manifest(
        args.project,
        {
            "data_quality": {
                "source_table": stats["source_table"],
                "clean_table": stats["clean_table"],
                "updated_codes": len(stats["updated_codes"]),
                "scanned_rows": stats["scanned_rows"],
                "kept_rows": stats["kept_rows"],
                "dropped_rows": stats["dropped_rows"],
                "repaired_rows": stats["repaired_rows"],
                "warned_rows": stats["warned_rows"],
                "issue_counts_by_code": stats["issue_counts_by_code"],
                "issue_counts_by_type": stats["issue_counts_by_type"],
                "summary_path": str(summary_path),
                "by_symbol_path": str(by_symbol_path),
            },
            "db_path": str(cfg["db_path"]),
            "freq": freq,
        },
    )

    print(
        f"[clean_bars] project={args.project} codes={len(stats['updated_codes'])} "
        f"kept_rows={stats['kept_rows']} dropped_rows={stats['dropped_rows']}",
    )
    print(f"[clean_bars] summary={summary_path}")
    print(f"[clean_bars] by_symbol={by_symbol_path}")


if __name__ == "__main__":
    main()
