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


def main() -> None:
    parser = argparse.ArgumentParser(description="Run walk-forward validation by configured windows.")
    parser.add_argument("--project", type=str, default="2026Q1_mom")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--topn", type=int, default=None)
    args = parser.parse_args()

    cfg, paths = load_config(args.project, config_path=args.config)
    paths.ensure_dirs()
    topn = int(args.topn if args.topn is not None else cfg["topk"])

    rank_path = paths.signals_dir / f"rank_top{int(cfg['topk'])}.parquet"
    rank_df = pd.read_parquet(rank_path)
    rank_df["date"] = pd.to_datetime(rank_df["date"])
    rank_df["code"] = rank_df["code"].astype(str).str.zfill(6)
    rank_df["rank"] = rank_df["rank"].astype(int)
    universe = set(load_universe_codes(args.project))
    rank_df = rank_df[rank_df["code"].isin(universe)].copy()

    windows = cfg.get("walk_forward", {}).get("windows", [])
    if not windows:
        raise RuntimeError("walk_forward.windows is empty in config")

    bt_cfg = BacktestConfig(
        cash=float(cfg["cash"]),
        commission=float(cfg["commission"]),
        stamp_duty=float(cfg["stamp_duty"]),
        slippage=float(cfg["slippage"]),
        risk_free_rate=float(cfg["risk_free_rate"]),
        risk_overlay=cfg.get("risk_overlay", {}),
    )

    rows: list[dict[str, float | str]] = []
    for window in windows:
        name = window["name"]
        start = pd.to_datetime(window["start"])
        end = pd.to_datetime(window["end"])
        sub_rank = rank_df[(rank_df["date"] >= start) & (rank_df["date"] <= end)].copy()
        if sub_rank.empty:
            continue
        codes = sorted(sub_rank["code"].unique().tolist())
        close, _ = load_close_volume_panel(
            db_path=Path(cfg["db_path"]),
            freq=cfg["freq"],
            codes=codes,
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
        )
        if close.empty:
            continue
        targets = rank_targets(sub_rank, topn=topn)
        equity = run_rebalance_backtest(close, targets, bt_cfg)
        metrics = summarize_equity(equity, bt_cfg)
        rows.append({"window": name, "start": str(start.date()), "end": str(end.date()), **metrics})

    out_df = pd.DataFrame(rows)
    metrics_path = paths.artifacts_dir / "walk_forward_metrics.csv"
    out_df.to_csv(metrics_path, index=False, encoding="utf-8-sig")

    fig_path = paths.artifacts_dir / "walk_forward_panel.png"
    if not out_df.empty:
        plt.figure(figsize=(10, 6))
        x = range(len(out_df))
        plt.bar(x, out_df["total_return"], label="total_return")
        plt.plot(x, out_df["max_drawdown"], color="red", marker="o", label="max_drawdown")
        plt.xticks(list(x), out_df["window"], rotation=20)
        plt.title(f"{args.project}: walk-forward")
        plt.grid(True, axis="y", alpha=0.3)
        plt.legend()
        plt.tight_layout()
        plt.savefig(fig_path, dpi=200)
        plt.close()

    update_run_manifest(
        args.project,
        {
            "walk_forward": {
                "metrics_path": str(metrics_path),
                "panel_path": str(fig_path),
                "windows": windows,
            },
            "db_path": str(cfg["db_path"]),
        },
    )
    print(f"[walk_forward] metrics={metrics_path}")
    print(f"[walk_forward] panel={fig_path}")


if __name__ == "__main__":
    main()
