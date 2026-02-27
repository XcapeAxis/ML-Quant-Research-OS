"""Run project-scoped rebalancing backtest.

Supports two strategy modes via the ``strategy_mode`` config key:
  * ``"momentum"``            -- TopN sweep with plain rebalance engine.
  * ``"limit_up_screening"``  -- single-N backtest with stop-loss, take-profit,
                                  market stop-loss, no-trade months, and blacklist.
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quant_mvp.backtest_engine import (
    BacktestConfig,
    StoplossParams,
    rank_targets,
    run_rebalance_backtest_with_stoploss,
    run_topn_suite,
    summarize_equity,
)
from quant_mvp.config import load_config
from quant_mvp.db import load_close_volume_panel
from quant_mvp.manifest import candidate_count_stats, update_run_manifest
from quant_mvp.universe import load_universe_codes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_rank(rank_path: Path) -> pd.DataFrame:
    if not rank_path.exists():
        raise FileNotFoundError(f"Rank file not found: {rank_path}. Run 20_build_rank.py first.")
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


def _save_single_curve_plot(equity: pd.Series, out_path: Path, title: str, label: str) -> None:
    norm = equity / equity.iloc[0] if len(equity) > 0 else equity
    plt.figure(figsize=(12, 6))
    plt.plot(norm.index, norm.values, label=label)
    plt.title(title)
    plt.xlabel("Date")
    plt.ylabel("Equity (normalized)")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=200)
    plt.close()


def _index_daily_ratio(db_path: Path, freq: str, calendar_code: str, start: str, end: str) -> pd.Series | None:
    """Load index close/open ratio per day for market stop-loss."""
    try:
        conn = sqlite3.connect(db_path)
        df = pd.read_sql(
            "SELECT datetime, open, close FROM bars WHERE symbol=? AND freq=? "
            "AND datetime >= ? AND datetime <= ? ORDER BY datetime",
            conn,
            params=(calendar_code, freq, start, end),
        )
        conn.close()
        if df.empty:
            return None
        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.set_index("datetime")
        ratio = df["close"] / df["open"].replace(0, np.nan)
        return ratio.dropna()
    except Exception:
        return None


def _resolve_plot_path(args, paths, default_name: str) -> Path | None:
    save_plot = str(args.save).strip().lower()
    if save_plot == "auto" or (save_plot == "" and args.no_show):
        return paths.artifacts_dir / default_name
    if save_plot not in {"", "none", "false"}:
        candidate = Path(args.save)
        return candidate if candidate.is_absolute() else (ROOT / candidate)
    return None


# ---------------------------------------------------------------------------
# Momentum mode
# ---------------------------------------------------------------------------

def _run_momentum(args, cfg: dict, paths) -> None:
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
        db_path=Path(cfg["db_path"]), freq=cfg["freq"], codes=rank_codes, start=start, end=end,
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
    curves, metrics = run_topn_suite(close_panel=close, rank_df=rank_df, cfg=bt_cfg, topn_max=int(cfg["topn_max"]))
    metrics = metrics.sort_values("topn").reset_index(drop=True)

    metrics_path = paths.artifacts_dir / "summary_metrics.csv"
    metrics.to_csv(metrics_path, index=False, encoding="utf-8-sig")

    plot_path = _resolve_plot_path(args, paths, "topn_1_5.png")
    if plot_path is not None:
        _save_curve_plot(curves, plot_path, title=f"{args.project}: TopN equity curves")

    candidate_stats = candidate_count_stats(paths.meta_dir / "rank_candidate_count.csv")
    update_run_manifest(args.project, {
        "strategy_mode": "momentum",
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
    })
    print(f"[backtest] mode=momentum project={args.project} metrics={metrics_path}")
    if plot_path:
        print(f"[backtest] plot={plot_path}")


# ---------------------------------------------------------------------------
# Limit-up screening mode
# ---------------------------------------------------------------------------

def _run_limit_up_screening(args, cfg: dict, paths) -> None:
    stock_num = int(cfg.get("stock_num", 6))
    rank_path = args.rank_path or (paths.signals_dir / f"rank_top{stock_num}.parquet")
    rank_df = _read_rank(rank_path)
    universe = set(load_universe_codes(args.project))
    rank_df = rank_df[rank_df["code"].isin(universe)].copy()
    if rank_df.empty:
        raise RuntimeError("Rank file has no rows after universe filter.")

    start = rank_df["date"].min().strftime("%Y-%m-%d")
    end = rank_df["date"].max().strftime("%Y-%m-%d")
    rank_codes = sorted(rank_df["code"].unique().tolist())
    close, _ = load_close_volume_panel(
        db_path=Path(cfg["db_path"]), freq=cfg["freq"], codes=rank_codes, start=start, end=end,
    )
    close = close.reindex(columns=rank_codes)

    calendar_code = str(cfg.get("calendar_code", "000001")).zfill(6)
    index_ratio = _index_daily_ratio(Path(cfg["db_path"]), cfg["freq"], calendar_code, start, end)

    bt_cfg = BacktestConfig(
        cash=float(cfg["cash"]),
        commission=float(cfg.get("commission", 0.0001)),
        stamp_duty=float(cfg.get("stamp_duty", 0.0005)),
        slippage=float(cfg.get("slippage", 0.002)),
        risk_free_rate=float(cfg.get("risk_free_rate", 0.03)),
        risk_overlay=cfg.get("risk_overlay"),
        min_commission=float(cfg["min_commission"]) if cfg.get("min_commission") is not None else None,
    )
    stoploss_params = StoplossParams(
        stoploss_limit=float(cfg.get("stoploss_limit", 0.91)),
        take_profit_ratio=float(cfg.get("take_profit_ratio", 2.0)),
        market_stoploss_ratio=float(cfg.get("market_stoploss_ratio", 0.93)),
        loss_black_days=int(cfg.get("loss_black_days", 20)),
        no_trade_months=tuple(int(m) for m in cfg.get("no_trade_months", [1, 4])),
        min_commission=float(cfg["min_commission"]) if cfg.get("min_commission") is not None else None,
    )

    targets = rank_targets(rank_df, topn=stock_num)
    equity = run_rebalance_backtest_with_stoploss(
        close_panel=close,
        targets_by_date=targets,
        cfg=bt_cfg,
        stoploss_params=stoploss_params,
        index_daily_ratio=index_ratio,
    )
    metrics_row = summarize_equity(equity, bt_cfg)
    metrics_row["topn"] = stock_num
    metrics_df = pd.DataFrame([metrics_row])

    metrics_path = paths.artifacts_dir / "summary_metrics.csv"
    metrics_df.to_csv(metrics_path, index=False, encoding="utf-8-sig")

    plot_path = _resolve_plot_path(args, paths, "equity_curve.png")
    if plot_path is not None:
        _save_single_curve_plot(equity, plot_path, f"{args.project}: Strategy equity curve", f"Top{stock_num}")

    update_run_manifest(args.project, {
        "strategy_mode": "limit_up_screening",
        "rank_path": str(rank_path),
        "summary_metrics_path": str(metrics_path),
        "plot_path": str(plot_path) if plot_path else "",
        "rank_dates": int(rank_df["date"].nunique()),
        "rank_unique_codes": int(rank_df["code"].nunique()),
        "db_path": str(cfg["db_path"]),
        "params": {
            "stock_num": stock_num,
            "stoploss_limit": cfg.get("stoploss_limit", 0.91),
            "no_trade_months": cfg.get("no_trade_months", [1, 4]),
            "market_stoploss_ratio": cfg.get("market_stoploss_ratio", 0.93),
        },
    })
    print(f"[backtest] mode=limit_up_screening project={args.project} metrics={metrics_path}")
    if plot_path:
        print(f"[backtest] plot={plot_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Run project-scoped rebalancing backtest.")
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

    mode = str(cfg.get("strategy_mode", "momentum"))
    if mode == "limit_up_screening":
        _run_limit_up_screening(args, cfg, paths)
    else:
        _run_momentum(args, cfg, paths)


if __name__ == "__main__":
    main()
