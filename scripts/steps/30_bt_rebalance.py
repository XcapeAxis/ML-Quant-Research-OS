from __future__ import annotations

import argparse
from pathlib import Path
import sys

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from quant_mvp.backtest_engine import BacktestConfig, run_topn_suite
from quant_mvp.config import load_config
from quant_mvp.db import load_close_volume_panel
from quant_mvp.manifest import candidate_count_stats, update_run_manifest
from quant_mvp.universe import load_universe_codes


def _read_rank(rank_path: Path) -> pd.DataFrame:
    if not rank_path.exists():
        raise FileNotFoundError(f"Rank file not found: {rank_path}. Run scripts/steps/20_build_rank.py first.")
    rank_df = pd.read_parquet(rank_path)
    required = {"date", "code", "rank"}
    if not required.issubset(rank_df.columns):
        raise RuntimeError(f"Rank file missing columns: {required - set(rank_df.columns)}")
    rank_df["date"] = pd.to_datetime(rank_df["date"])
    rank_df["code"] = rank_df["code"].astype(str).str.zfill(6)
    rank_df["rank"] = rank_df["rank"].astype(int)
    return rank_df.sort_values(["date", "rank", "code"]).reset_index(drop=True)


def _save_curve_plot(curves: pd.DataFrame, out_path: Path, title: str) -> None:
    norm = curves / curves.iloc[0]
    plt.figure(figsize=(12, 6))
    for col in norm.columns:
        plt.plot(norm.index, norm[col], label=col)
    plt.title(title)
    plt.xlabel("Date")
    plt.ylabel("Equity (normalized)")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=200)
    plt.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run project-scoped TopN rebalancing backtest.")
    parser.add_argument("--project", type=str, default="2026Q1_mom")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--rank-path", type=Path, default=None)
    parser.add_argument("--freq", type=str, default=None)
    parser.add_argument("--topn-max", type=int, default=None)
    parser.add_argument("--cash", type=float, default=None)
    parser.add_argument("--commission", type=float, default=None)
    parser.add_argument("--stamp-duty", type=float, default=None)
    parser.add_argument("--slippage", type=float, default=None)
    parser.add_argument("--risk-free-rate", type=float, default=None)
    parser.add_argument("--save", type=str, default="auto")
    parser.add_argument("--no-show", action="store_true")
    args = parser.parse_args()

    cfg, paths = load_config(
        args.project,
        config_path=args.config,
        overrides={
            "freq": args.freq,
            "topn_max": args.topn_max,
            "cash": args.cash,
            "commission": args.commission,
            "stamp_duty": args.stamp_duty,
            "slippage": args.slippage,
            "risk_free_rate": args.risk_free_rate,
        },
    )
    paths.ensure_dirs()

    rank_path = args.rank_path or (paths.signals_dir / f"rank_top{int(cfg['topk'])}.parquet")
    rank_df = _read_rank(rank_path)
    universe = set(load_universe_codes(args.project))
    rank_df = rank_df[rank_df["code"].isin(universe)].copy()
    if rank_df.empty:
        raise RuntimeError("Rank file has no rows after universe filter.")

    start = rank_df["date"].min().strftime("%Y-%m-%d")
    end = rank_df["date"].max().strftime("%Y-%m-%d")
    rank_codes = sorted(rank_df["code"].unique().tolist())
    close, _ = load_close_volume_panel(
        db_path=Path(cfg["db_path"]),
        freq=cfg["freq"],
        codes=rank_codes,
        start=start,
        end=end,
    )
    close = close.reindex(columns=rank_codes)

    bt_cfg = BacktestConfig(
        cash=float(cfg["cash"]),
        commission=float(cfg["commission"]),
        stamp_duty=float(cfg["stamp_duty"]),
        slippage=float(cfg["slippage"]),
        risk_free_rate=float(cfg["risk_free_rate"]),
        risk_overlay=cfg.get("risk_overlay", {}),
    )
    curves, metrics = run_topn_suite(
        close_panel=close,
        rank_df=rank_df,
        cfg=bt_cfg,
        topn_max=int(cfg["topn_max"]),
    )
    metrics = metrics.sort_values("topn").reset_index(drop=True)

    metrics_path = paths.artifacts_dir / "summary_metrics.csv"
    metrics.to_csv(metrics_path, index=False, encoding="utf-8-sig")

    save_plot = str(args.save).strip().lower()
    plot_path = None
    if save_plot == "auto" or (save_plot == "" and args.no_show):
        plot_path = paths.artifacts_dir / "topn_1_5.png"
    elif save_plot not in {"", "none", "false"}:
        candidate = Path(args.save)
        plot_path = candidate if candidate.is_absolute() else (ROOT / candidate)

    if plot_path is not None:
        _save_curve_plot(curves, plot_path, title=f"{args.project}: TopN equity curves")

    candidate_stats = candidate_count_stats(paths.meta_dir / "rank_candidate_count.csv")
    update_run_manifest(
        args.project,
        {
            "rank_path": str(rank_path),
            "summary_metrics_path": str(metrics_path),
            "plot_path": str(plot_path) if plot_path else "",
            "rank_dates": int(rank_df["date"].nunique()),
            "rank_unique_codes": int(rank_df["code"].nunique()),
            "candidate_count_stats": candidate_stats,
            "params": {
                "topn_max": int(cfg["topn_max"]),
                "cash": float(cfg["cash"]),
                "commission": float(cfg["commission"]),
                "stamp_duty": float(cfg["stamp_duty"]),
                "slippage": float(cfg["slippage"]),
            },
            "db_path": str(cfg["db_path"]),
        },
    )

    print(f"[backtest] project={args.project} metrics={metrics_path}")
    if plot_path:
        print(f"[backtest] plot={plot_path}")
    if not args.no_show and plot_path and plot_path.exists():
        image = plt.imread(plot_path)
        plt.figure(figsize=(12, 6))
        plt.imshow(image)
        plt.axis("off")
        plt.tight_layout()
        plt.show()


if __name__ == "__main__":
    main()
