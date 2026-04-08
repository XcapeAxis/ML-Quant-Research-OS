from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quant_mvp.backtest_engine import (
    BacktestConfig,
    equal_weight_targets,
    rank_targets,
    run_rebalance_backtest,
    summarize_equity,
)
from quant_mvp.config import load_config
from quant_mvp.db import load_close_volume_panel
from quant_mvp.manifest import update_run_manifest
from quant_mvp.universe import load_universe_codes


def _read_rank(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"])
    df["code"] = df["code"].astype(str).str.zfill(6)
    df["rank"] = df["rank"].astype(int)
    return df.sort_values(["date", "rank", "code"]).reset_index(drop=True)


def _equity_from_close(close: pd.Series, cash: float) -> pd.Series:
    base = close.dropna()
    if base.empty:
        return pd.Series(dtype=float)
    equity = cash * (base / base.iloc[0])
    equity.name = "equity"
    return equity


def main() -> None:
    parser = argparse.ArgumentParser(description="Run baselines and random controls.")
    parser.add_argument("--project", type=str, default="crypto_okx_research_v1")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--random-trials", type=int, default=None)
    parser.add_argument("--random-seed", type=int, default=None)
    args = parser.parse_args()

    cfg, paths = load_config(
        args.project,
        config_path=args.config,
        overrides={
            "baselines": {
                "random_trials": args.random_trials,
                "random_seed": args.random_seed,
            },
        },
    )
    paths.ensure_dirs()

    topk = int(cfg["topk"])
    rank_path = paths.signals_dir / f"rank_top{topk}.parquet"
    candidates_path = paths.signals_dir / "rank_candidates.parquet"
    rank_df = _read_rank(rank_path)
    universe = set(load_universe_codes(args.project))
    rank_df = rank_df[rank_df["code"].isin(universe)].copy()
    if rank_df.empty:
        raise RuntimeError("No rank rows after universe filter.")

    start = rank_df["date"].min().strftime("%Y-%m-%d")
    end = rank_df["date"].max().strftime("%Y-%m-%d")

    bt_cfg = BacktestConfig(
        cash=float(cfg["cash"]),
        commission=float(cfg["commission"]),
        stamp_duty=float(cfg["stamp_duty"]),
        slippage=float(cfg["slippage"]),
        risk_free_rate=float(cfg["risk_free_rate"]),
        risk_overlay=cfg.get("risk_overlay", {}),
    )

    # Strategy Top5
    strategy_codes = sorted(rank_df["code"].unique().tolist())
    close_strategy, _ = load_close_volume_panel(
        db_path=Path(cfg["db_path"]),
        freq=cfg["freq"],
        codes=strategy_codes,
        start=start,
        end=end,
    )
    top_targets = rank_targets(rank_df=rank_df, topn=topk)
    strategy_equity = run_rebalance_backtest(close_strategy, top_targets, bt_cfg)
    strategy_metrics = summarize_equity(strategy_equity, bt_cfg)

    # Benchmark (000001 by default)
    benchmark_code = str(cfg.get("baselines", {}).get("benchmark_code", "000001")).zfill(6)
    benchmark_close, _ = load_close_volume_panel(
        db_path=Path(cfg["db_path"]),
        freq=cfg["freq"],
        codes=[benchmark_code],
        start=start,
        end=end,
    )
    benchmark_series = benchmark_close[benchmark_code] if benchmark_code in benchmark_close.columns else pd.Series(dtype=float)
    benchmark_equity = _equity_from_close(benchmark_series, cash=float(cfg["cash"]))
    benchmark_metrics = summarize_equity(benchmark_equity, bt_cfg) if not benchmark_equity.empty else {
        "total_return": 0.0,
        "annualized_return": 0.0,
        "annualized_volatility": 0.0,
        "max_drawdown": 0.0,
        "sharpe_ratio": 0.0,
        "days": 0.0,
        "final_equity": float(cfg["cash"]),
    }

    # Equal-weight universe baseline
    universe_codes = sorted(load_universe_codes(args.project))
    close_universe, _ = load_close_volume_panel(
        db_path=Path(cfg["db_path"]),
        freq=cfg["freq"],
        codes=universe_codes,
        start=start,
        end=end,
    )
    eq_targets = equal_weight_targets(
        calendar=close_universe.index,
        codes=list(close_universe.columns),
        rebalance_every=int(cfg["rebalance_every"]),
    )
    equal_equity = run_rebalance_backtest(close_universe, eq_targets, bt_cfg)
    equal_metrics = summarize_equity(equal_equity, bt_cfg)

    # Random Top5 controls
    if not candidates_path.exists():
        raise FileNotFoundError(f"Candidate file not found: {candidates_path}. Run 20_build_rank.py first.")
    candidate_df = pd.read_parquet(candidates_path)
    candidate_df["date"] = pd.to_datetime(candidate_df["date"])
    candidate_df["code"] = candidate_df["code"].astype(str).str.zfill(6)
    candidate_df = candidate_df[candidate_df["code"].isin(universe)]
    grouped = {dt: grp["code"].tolist() for dt, grp in candidate_df.groupby("date")}

    rng = np.random.default_rng(int(cfg.get("baselines", {}).get("random_seed", 42)))
    trials = int(cfg.get("baselines", {}).get("random_trials", 200))
    random_rows: list[dict[str, float]] = []
    for trial in range(trials):
        targets: dict[pd.Timestamp, list[str]] = {}
        for dt, pool in grouped.items():
            if not pool:
                continue
            k = min(topk, len(pool))
            picks = rng.choice(pool, size=k, replace=False)
            targets[pd.Timestamp(dt)] = [str(code).zfill(6) for code in picks.tolist()]
        eq = run_rebalance_backtest(close_strategy, targets, bt_cfg)
        row = summarize_equity(eq, bt_cfg)
        row["trial"] = float(trial)
        random_rows.append(row)

    random_df = pd.DataFrame(random_rows)
    random_dist_path = paths.artifacts_dir / "random_top5_distribution.csv"
    random_df.to_csv(random_dist_path, index=False, encoding="utf-8-sig")
    random_summary = {
        "total_return_mean": float(random_df["total_return"].mean()),
        "total_return_p10": float(random_df["total_return"].quantile(0.1)),
        "total_return_p90": float(random_df["total_return"].quantile(0.9)),
        "sharpe_mean": float(random_df["sharpe_ratio"].mean()),
    }
    random_mean_row = {
        "name": "random_top5_mean",
        "total_return": float(random_df["total_return"].mean()),
        "annualized_return": float(random_df["annualized_return"].mean()),
        "annualized_volatility": float(random_df["annualized_volatility"].mean()),
        "max_drawdown": float(random_df["max_drawdown"].mean()),
        "sharpe_ratio": float(random_df["sharpe_ratio"].mean()),
        "days": float(random_df["days"].mean()),
        "final_equity": float(random_df["final_equity"].mean()),
        "total_return_p10": float(random_df["total_return"].quantile(0.1)),
        "total_return_p90": float(random_df["total_return"].quantile(0.9)),
    }

    baseline_rows = [
        {"name": "strategy_top5", **strategy_metrics},
        {"name": f"benchmark_{benchmark_code}", **benchmark_metrics},
        {"name": "equal_weight_universe", **equal_metrics},
        random_mean_row,
    ]
    baseline_metrics_path = paths.artifacts_dir / "baseline_metrics.csv"
    pd.DataFrame(baseline_rows).to_csv(baseline_metrics_path, index=False, encoding="utf-8-sig")

    update_run_manifest(
        args.project,
        {
            "baseline_metrics_path": str(baseline_metrics_path),
            "random_distribution_path": str(random_dist_path),
            "baselines": {
                "benchmark_code": benchmark_code,
                "random_trials": trials,
                "random_seed": int(cfg.get("baselines", {}).get("random_seed", 42)),
                "random_summary": random_summary,
            },
            "db_path": str(cfg["db_path"]),
        },
    )
    print(f"[baselines] metrics={baseline_metrics_path}")
    print(f"[baselines] random={random_dist_path}")


if __name__ == "__main__":
    main()
