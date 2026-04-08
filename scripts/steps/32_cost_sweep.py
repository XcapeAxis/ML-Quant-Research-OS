from __future__ import annotations

import argparse
from pathlib import Path
import sys

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quant_mvp.backtest_engine import BacktestConfig, rank_targets, run_rebalance_backtest, summarize_equity
from quant_mvp.config import load_config
from quant_mvp.db import load_close_volume_panel
from quant_mvp.manifest import update_run_manifest
from quant_mvp.universe import load_universe_codes


def _parse_grid(value: str | None) -> list[float] | None:
    if value is None:
        return None
    parts = [item.strip() for item in value.split(",") if item.strip()]
    return [float(item) for item in parts]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run commission/slippage cost sweep (5x5 default).")
    parser.add_argument("--project", type=str, default="crypto_okx_research_v1")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--commission-grid", type=str, default=None)
    parser.add_argument("--slippage-grid", type=str, default=None)
    args = parser.parse_args()

    cfg, paths = load_config(
        args.project,
        config_path=args.config,
        overrides={
            "cost_sweep": {
                "commission_grid": _parse_grid(args.commission_grid),
                "slippage_grid": _parse_grid(args.slippage_grid),
            },
        },
    )
    paths.ensure_dirs()

    topk = int(cfg["topk"])
    rank_path = paths.signals_dir / f"rank_top{topk}.parquet"
    rank_df = pd.read_parquet(rank_path)
    rank_df["date"] = pd.to_datetime(rank_df["date"])
    rank_df["code"] = rank_df["code"].astype(str).str.zfill(6)
    rank_df["rank"] = rank_df["rank"].astype(int)
    universe = set(load_universe_codes(args.project))
    rank_df = rank_df[rank_df["code"].isin(universe)].copy()
    if rank_df.empty:
        raise RuntimeError("Rank file is empty after universe filter.")

    start = rank_df["date"].min().strftime("%Y-%m-%d")
    end = rank_df["date"].max().strftime("%Y-%m-%d")
    codes = sorted(rank_df["code"].unique().tolist())
    close, _ = load_close_volume_panel(Path(cfg["db_path"]), cfg["freq"], codes, start=start, end=end)
    targets = rank_targets(rank_df, topn=topk)

    commission_grid = cfg["cost_sweep"]["commission_grid"]
    slippage_grid = cfg["cost_sweep"]["slippage_grid"]
    if len(commission_grid) != 5 or len(slippage_grid) != 5:
        raise ValueError("Cost grid must be 5x5. Set 5 commission values and 5 slippage values.")

    rows: list[dict[str, float]] = []
    for commission in commission_grid:
        for slippage in slippage_grid:
            bt_cfg = BacktestConfig(
                cash=float(cfg["cash"]),
                commission=float(commission),
                stamp_duty=float(cfg["stamp_duty"]),
                slippage=float(slippage),
                risk_free_rate=float(cfg["risk_free_rate"]),
                risk_overlay=cfg.get("risk_overlay", {}),
            )
            equity = run_rebalance_backtest(close, targets, bt_cfg)
            metrics = summarize_equity(equity, bt_cfg)
            rows.append(
                {
                    "commission": float(commission),
                    "slippage": float(slippage),
                    **metrics,
                },
            )

    metrics_df = pd.DataFrame(rows).sort_values(["commission", "slippage"]).reset_index(drop=True)
    metrics_path = paths.artifacts_dir / "cost_sweep_metrics.csv"
    metrics_df.to_csv(metrics_path, index=False, encoding="utf-8-sig")

    heat = metrics_df.pivot(index="commission", columns="slippage", values="total_return")
    plt.figure(figsize=(8, 6))
    plt.imshow(heat.values, aspect="auto")
    plt.xticks(range(len(heat.columns)), [f"{x:.4f}" for x in heat.columns], rotation=45)
    plt.yticks(range(len(heat.index)), [f"{x:.4f}" for x in heat.index])
    plt.title(f"{args.project}: cost sweep total return")
    plt.xlabel("slippage")
    plt.ylabel("commission")
    plt.colorbar(label="total_return")
    plt.tight_layout()
    heatmap_path = paths.artifacts_dir / "cost_sweep_heatmap.png"
    plt.savefig(heatmap_path, dpi=200)
    plt.close()

    update_run_manifest(
        args.project,
        {
            "cost_sweep": {
                "metrics_path": str(metrics_path),
                "heatmap_path": str(heatmap_path),
                "commission_grid": commission_grid,
                "slippage_grid": slippage_grid,
            },
            "db_path": str(cfg["db_path"]),
        },
    )
    print(f"[cost_sweep] metrics={metrics_path}")
    print(f"[cost_sweep] heatmap={heatmap_path}")


if __name__ == "__main__":
    main()
