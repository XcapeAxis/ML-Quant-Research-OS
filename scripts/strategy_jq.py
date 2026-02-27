"""
Original strategy: Tuesday rebalance, equal-weight N names, stop-loss / take-profit /
market stop-loss, no-trade months (cash), blacklist after stop-loss.
Standalone runnable script; uses quant_mvp and project config.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quant_mvp.backtest_engine import (
    BacktestConfig,
    StoplossParams,
    rank_targets,
    run_rebalance_backtest_with_stoploss,
    summarize_equity,
)
from quant_mvp.config import load_config
from quant_mvp.db import load_close_volume_panel
from quant_mvp.manifest import update_run_manifest
from quant_mvp.ranking import build_rank_tuesday_momentum
from quant_mvp.universe import load_universe_codes


def _default_strategy_config(cfg: dict) -> dict:
    """Fill strategy-specific keys from config or defaults (original design)."""
    out = dict(cfg)
    if "stock_num" not in out:
        out["stock_num"] = 6
    if "no_trade_months" not in out:
        out["no_trade_months"] = [1, 4]
    if "stoploss_limit" not in out:
        out["stoploss_limit"] = 0.91
    if "take_profit_ratio" not in out:
        out["take_profit_ratio"] = 2.0
    if "market_stoploss_ratio" not in out:
        out["market_stoploss_ratio"] = 0.93
    if "loss_black_days" not in out:
        out["loss_black_days"] = 20
    if "min_commission" not in out:
        out["min_commission"] = 5.0
    return out


def _index_daily_ratio(db_path: Path, freq: str, calendar_code: str, start: str, end: str) -> pd.Series | None:
    """Index close/open ratio per day for market stop-loss. Returns None if not available."""
    try:
        close, _ = load_close_volume_panel(db_path, freq, [calendar_code], start=start, end=end)
        if close.empty or calendar_code not in close.columns:
            return None
        # We need open; db has open in bars. Load open from db.
        import sqlite3
        conn = sqlite3.connect(db_path)
        df = pd.read_sql(
            "SELECT datetime, open, close FROM bars WHERE symbol=? AND freq=? AND datetime >= ? AND datetime <= ? ORDER BY datetime",
            conn,
            params=(calendar_code, freq, start, end),
        )
        conn.close()
        if df.empty or "open" not in df.columns or "close" not in df.columns:
            return None
        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.set_index("datetime")
        ratio = df["close"] / df["open"].replace(0, np.nan)
        return ratio.dropna()
    except Exception:
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Run original strategy: Tuesday rebalance, stop-loss, no-trade months.")
    parser.add_argument("--project", type=str, default="2026Q1_jq")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--save", type=str, default="auto")
    parser.add_argument("--no-show", action="store_true")
    args = parser.parse_args()

    cfg, paths = load_config(args.project, config_path=args.config)
    cfg = _default_strategy_config(cfg)
    paths.ensure_dirs()

    db_path = Path(cfg["db_path"])
    freq = str(cfg["freq"])
    stock_num = int(cfg["stock_num"])
    lookback = int(cfg.get("lookback", 20))
    min_bars = int(cfg.get("min_bars", 160))
    max_codes_scan = int(cfg.get("max_codes_scan", 4000))
    tradability = cfg.get("tradability", {})
    require_positive_volume = bool(tradability.get("require_positive_volume", False))
    min_volume = float(tradability.get("min_volume", 0))

    universe = load_universe_codes(args.project)
    rank_result = build_rank_tuesday_momentum(
        db_path=db_path,
        freq=freq,
        universe_codes=universe,
        lookback=lookback,
        topk=stock_num,
        min_bars=min_bars,
        max_codes_scan=max_codes_scan,
        require_positive_volume=require_positive_volume,
        min_volume=min_volume,
    )
    rank_df = rank_result.rank_df
    rank_path = paths.signals_dir / f"rank_top{stock_num}.parquet"
    rank_df.to_parquet(rank_path, index=False)

    start = rank_df["date"].min().strftime("%Y-%m-%d")
    end = rank_df["date"].max().strftime("%Y-%m-%d")
    rank_codes = sorted(rank_df["code"].unique().tolist())
    close, _ = load_close_volume_panel(db_path, freq, rank_codes, start=start, end=end)
    close = close.reindex(columns=rank_codes)

    calendar_code = str(cfg.get("calendar_code", "000001")).zfill(6)
    index_ratio = _index_daily_ratio(db_path, freq, calendar_code, start, end)

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
        stoploss_limit=float(cfg["stoploss_limit"]),
        take_profit_ratio=float(cfg["take_profit_ratio"]),
        market_stoploss_ratio=float(cfg["market_stoploss_ratio"]),
        loss_black_days=int(cfg["loss_black_days"]),
        no_trade_months=tuple(int(m) for m in cfg["no_trade_months"]),
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

    save_plot = str(args.save).strip().lower()
    plot_path = None
    if save_plot == "auto" or (save_plot == "" and args.no_show):
        plot_path = paths.artifacts_dir / "topn_1_5.png"
    elif save_plot not in {"", "none", "false"}:
        candidate = Path(args.save)
        plot_path = candidate if candidate.is_absolute() else (ROOT / candidate)

    if plot_path is not None:
        plot_path.parent.mkdir(parents=True, exist_ok=True)
        norm = equity / equity.iloc[0] if len(equity) > 0 else equity
        plt.figure(figsize=(12, 6))
        plt.plot(norm.index, norm.values, label=f"Top{stock_num}")
        plt.title(f"{args.project}: Strategy equity curve")
        plt.xlabel("Date")
        plt.ylabel("Equity (normalized)")
        plt.grid(True)
        plt.legend()
        plt.tight_layout()
        plt.savefig(plot_path, dpi=200)
        plt.close()

    update_run_manifest(
        args.project,
        {
            "rank_path": str(rank_path),
            "summary_metrics_path": str(metrics_path),
            "plot_path": str(plot_path) if plot_path else "",
            "rank_dates": int(rank_df["date"].nunique()),
            "rank_unique_codes": int(rank_df["code"].nunique()),
            "db_path": str(cfg["db_path"]),
            "params": {
                "stock_num": stock_num,
                "stoploss_limit": cfg["stoploss_limit"],
                "no_trade_months": cfg["no_trade_months"],
            },
        },
    )

    print(f"[strategy_jq] project={args.project} metrics={metrics_path}")
    if plot_path:
        print(f"[strategy_jq] plot={plot_path}")


if __name__ == "__main__":
    main()
