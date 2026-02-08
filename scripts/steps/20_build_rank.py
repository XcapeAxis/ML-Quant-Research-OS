from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from quant_mvp.config import load_config
from quant_mvp.manifest import candidate_count_stats, update_run_manifest
from quant_mvp.ranking import build_momentum_rank
from quant_mvp.universe import load_universe_codes


def main() -> None:
    parser = argparse.ArgumentParser(description="Build project-scoped momentum rank and candidate statistics.")
    parser.add_argument("--project", type=str, default="2026Q1_mom")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--freq", type=str, default=None)
    parser.add_argument("--lookback", type=int, default=None)
    parser.add_argument("--rebalance-every", type=int, default=None)
    parser.add_argument("--topk", type=int, default=None)
    parser.add_argument("--min-bars", type=int, default=None)
    parser.add_argument("--max-codes-scan", type=int, default=None)
    args = parser.parse_args()

    cfg, paths = load_config(
        args.project,
        config_path=args.config,
        overrides={
            "freq": args.freq,
            "lookback": args.lookback,
            "rebalance_every": args.rebalance_every,
            "topk": args.topk,
            "min_bars": args.min_bars,
            "max_codes_scan": args.max_codes_scan,
        },
    )
    paths.ensure_dirs()

    universe = load_universe_codes(args.project)
    rank = build_momentum_rank(
        db_path=Path(cfg["db_path"]),
        freq=cfg["freq"],
        universe_codes=universe,
        lookback=int(cfg["lookback"]),
        rebalance_every=int(cfg["rebalance_every"]),
        topk=int(cfg["topk"]),
        min_bars=int(cfg["min_bars"]),
        max_codes_scan=int(cfg["max_codes_scan"]),
        require_positive_volume=bool(cfg.get("tradability", {}).get("require_positive_volume", False)),
        min_volume=float(cfg.get("tradability", {}).get("min_volume", 0.0)),
    )

    rank_path = paths.signals_dir / f"rank_top{int(cfg['topk'])}.parquet"
    candidates_path = paths.signals_dir / "rank_candidates.parquet"
    candidate_count_path = paths.meta_dir / "rank_candidate_count.csv"

    rank.rank_df.to_parquet(rank_path, index=False)
    rank.candidate_scores_df.to_parquet(candidates_path, index=False)
    rank.candidate_count_df.to_csv(candidate_count_path, index=False, encoding="utf-8-sig")

    stats = candidate_count_stats(candidate_count_path)
    tradability_stats = None
    if "candidate_count_raw" in rank.candidate_count_df.columns:
        raw = rank.candidate_count_df["candidate_count_raw"]
        filtered = rank.candidate_count_df["candidate_count"]
        tradability_stats = {
            "raw_median": float(raw.median()),
            "filtered_median": float(filtered.median()),
            "median_drop": float((raw - filtered).median()),
        }
    update_run_manifest(
        args.project,
        {
            "freq": cfg["freq"],
            "params": {
                "lookback": int(cfg["lookback"]),
                "rebalance_every": int(cfg["rebalance_every"]),
                "topk": int(cfg["topk"]),
                "min_bars": int(cfg["min_bars"]),
                "max_codes_scan": int(cfg["max_codes_scan"]),
            },
            "db_path": str(cfg["db_path"]),
            "rank_path": str(rank_path),
            "candidate_scores_path": str(candidates_path),
            "rank_dates": int(rank.rank_df["date"].nunique()),
            "rank_unique_codes": int(rank.rank_df["code"].nunique()),
            "candidate_count_stats": stats,
            "tradability_stats": tradability_stats,
        },
    )

    print(
        f"[build_rank] project={args.project} rank={rank_path} "
        f"rows={len(rank.rank_df)} dates={rank.rank_df['date'].nunique()}",
    )


if __name__ == "__main__":
    main()
