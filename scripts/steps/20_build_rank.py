"""Build project-scoped stock ranking.

Supports two strategy modes via the ``strategy_mode`` config key:
  * ``"momentum"``            -- classic momentum rank (``build_momentum_rank``).
  * ``"limit_up_screening"``  -- limit-up screening + start-point rank.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quant_mvp.config import load_config
from quant_mvp.manifest import candidate_count_stats, update_run_manifest
from quant_mvp.pools import resolve_research_universe_codes
from quant_mvp.ranking import build_momentum_rank
from quant_mvp.research_core import build_limit_up_rank_artifacts
from quant_mvp.universe import load_universe_codes


def _run_momentum(cfg: dict, paths, universe: list[str]) -> None:
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

    topk = int(cfg["topk"])
    rank_path = paths.signals_dir / f"rank_top{topk}.parquet"
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
        paths.project,
        {
            "strategy_mode": "momentum",
            "freq": cfg["freq"],
            "params": {
                "lookback": int(cfg["lookback"]),
                "rebalance_every": int(cfg["rebalance_every"]),
                "topk": topk,
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
        f"[build_rank] mode=momentum project={paths.project} rank={rank_path} "
        f"rows={len(rank.rank_df)} dates={rank.rank_df['date'].nunique()}"
    )


def _run_limit_up_screening(cfg: dict, paths, universe: list[str]) -> None:
    artifacts = build_limit_up_rank_artifacts(cfg=cfg, paths=paths, universe_codes=universe)
    update_run_manifest(paths.project, artifacts.manifest_updates)
    print(
        f"[build_rank] mode=limit_up_screening project={paths.project} rank={artifacts.rank_path} "
        f"rows={len(artifacts.selection.rank_df)} dates={artifacts.selection.rank_df['date'].nunique()}"
    )


def _load_strategy_universe(project: str, config_path: Path | None) -> list[str]:
    try:
        return load_universe_codes(project)
    except FileNotFoundError:
        universe, _ = resolve_research_universe_codes(
            project,
            config_path=config_path,
            build_if_missing=True,
        )
        return universe


def main() -> None:
    parser = argparse.ArgumentParser(description="Build project-scoped stock ranking.")
    parser.add_argument("--project", type=str, default="as_share_research_v1")
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
    universe = _load_strategy_universe(args.project, args.config)

    mode = str(cfg.get("strategy_mode", "momentum"))
    if mode == "limit_up_screening":
        _run_limit_up_screening(cfg, paths, universe)
    else:
        _run_momentum(cfg, paths, universe)


if __name__ == "__main__":
    main()
