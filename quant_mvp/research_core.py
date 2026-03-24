from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from .backtest_engine import (
    BacktestConfig,
    StoplossParams,
    rank_targets,
    run_rebalance_backtest_with_stoploss,
    summarize_equity,
)
from .data.validation import build_tradability_mask
from .db import load_close_volume_panel
from .manifest import candidate_count_stats
from .selection import LimitUpScreeningConfig, SelectionResult, build_limit_up_screening_rank
from .strategy_schema import default_limit_up_spec


@dataclass
class LimitUpRankArtifacts:
    selection: SelectionResult
    rank_path: Path
    candidate_count_path: Path | None
    manifest_updates: dict[str, Any]


@dataclass
class LimitUpBacktestArtifacts:
    rank_df: pd.DataFrame
    close_panel: pd.DataFrame
    volume_panel: pd.DataFrame
    tradability_mask: pd.DataFrame
    equity: pd.Series
    metrics_df: pd.DataFrame
    metrics_path: Path
    plot_path: Path | None
    drawdown_path: Path | None
    manifest_updates: dict[str, Any]


def resolve_limit_up_config(cfg: Mapping[str, Any]) -> LimitUpScreeningConfig:
    spec = default_limit_up_spec()
    return LimitUpScreeningConfig(
        stock_num=int(cfg.get("stock_num", spec.stock_num)),
        rebalance_weekday=int(cfg.get("rebalance_weekday", spec.rebalance_weekday)),
        limit_days_window=int(cfg.get("limit_days_window", spec.limit_days_window)),
        top_pct_limit_up=float(cfg.get("top_pct_limit_up", spec.top_pct_limit_up)),
        limit_up_threshold=float(cfg.get("limit_up_threshold", spec.limit_up_threshold)),
        init_pool_size=int(cfg.get("init_pool_size", spec.init_pool_size)),
        min_bars=int(cfg.get("min_bars", spec.min_bars)),
        max_codes_scan=int(cfg.get("max_codes_scan", spec.max_codes_scan)),
        topk_multiplier=int(cfg.get("topk_multiplier", spec.topk_multiplier)),
        require_positive_volume=bool(
            cfg.get("tradability", {}).get("require_positive_volume", spec.require_positive_volume),
        ),
        min_new_listing_days=int(cfg.get("min_new_listing_days", spec.min_new_listing_days)),
    )


def load_index_daily_ratio(
    db_path: Path,
    freq: str,
    calendar_code: str,
    start: str,
    end: str,
) -> pd.Series | None:
    try:
        conn = sqlite3.connect(db_path)
        frame = pd.read_sql(
            "SELECT datetime, open, close FROM bars WHERE symbol=? AND freq=? AND datetime >= ? AND datetime <= ? "
            "ORDER BY datetime",
            conn,
            params=(str(calendar_code).zfill(6), freq, start, end),
        )
        conn.close()
    except Exception:
        return None
    if frame.empty:
        return None
    frame["datetime"] = pd.to_datetime(frame["datetime"])
    frame = frame.set_index("datetime")
    ratio = frame["close"] / frame["open"].replace(0, pd.NA)
    return ratio.dropna()


def estimate_turnover(targets_by_date: Mapping[pd.Timestamp, list[str]]) -> float:
    previous: set[str] = set()
    turnover = 0.0
    dates = sorted(pd.Timestamp(item) for item in targets_by_date.keys())
    for dt in dates:
        current = set(str(code).zfill(6) for code in targets_by_date[dt])
        if previous:
            entering = len(current - previous)
            exiting = len(previous - current)
            base = max(len(current), len(previous), 1)
            turnover += (entering + exiting) / base
        else:
            turnover += 1.0 if current else 0.0
        previous = current
    return float(turnover / max(len(dates), 1))


def _resolve_plot_paths(
    *,
    save_value: str,
    no_show: bool,
    artifacts_dir: Path,
) -> tuple[Path | None, Path | None]:
    save_text = str(save_value).strip().lower()
    if save_text == "auto" or (save_text == "" and no_show):
        return artifacts_dir / "equity_curve.png", artifacts_dir / "drawdown_curve.png"
    if save_text in {"", "none", "false"}:
        return None, None
    candidate = Path(save_value)
    plot_path = candidate if candidate.is_absolute() else (artifacts_dir.parents[2] / candidate)
    return plot_path, None


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


def _save_drawdown_plot(equity: pd.Series, out_path: Path, title: str) -> None:
    if len(equity) < 2:
        return
    peak = equity.cummax()
    drawdown = (equity / peak) - 1.0
    plt.figure(figsize=(12, 5))
    plt.fill_between(drawdown.index, drawdown.values, 0, alpha=0.4, color="coral")
    plt.plot(drawdown.index, drawdown.values, color="darkred", linewidth=0.8)
    plt.title(title)
    plt.xlabel("Date")
    plt.ylabel("Drawdown")
    plt.grid(True)
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=200)
    plt.close()


def build_limit_up_rank_artifacts(
    *,
    cfg: Mapping[str, Any],
    paths,
    universe_codes: list[str],
) -> LimitUpRankArtifacts:
    sel_cfg = resolve_limit_up_config(cfg)
    result = build_limit_up_screening_rank(
        db_path=Path(str(cfg["db_path"])),
        freq=str(cfg["freq"]),
        universe_codes=universe_codes,
        cfg=sel_cfg,
        start_date=cfg.get("start_date"),
        end_date=cfg.get("end_date"),
    )

    rank_path = paths.signals_dir / f"rank_top{sel_cfg.stock_num}.parquet"
    result.rank_df.to_parquet(rank_path, index=False)

    candidate_count_path: Path | None = None
    if not result.candidate_count_df.empty:
        candidate_count_path = paths.meta_dir / "rank_candidate_count.csv"
        result.candidate_count_df.to_csv(candidate_count_path, index=False, encoding="utf-8-sig")

    manifest_updates = {
        "strategy_mode": "limit_up_screening",
        "freq": cfg["freq"],
        "db_path": str(cfg["db_path"]),
        "rank_path": str(rank_path),
        "rank_dates": int(result.rank_df["date"].nunique()),
        "rank_unique_codes": int(result.rank_df["code"].nunique()),
        "candidate_count_stats": (
            candidate_count_stats(candidate_count_path)
            if candidate_count_path is not None
            else None
        ),
        "params": {
            "stock_num": sel_cfg.stock_num,
            "limit_days_window": sel_cfg.limit_days_window,
            "top_pct_limit_up": sel_cfg.top_pct_limit_up,
            "limit_up_threshold": sel_cfg.limit_up_threshold,
            "rebalance_weekday": sel_cfg.rebalance_weekday,
            "topk_multiplier": sel_cfg.topk_multiplier,
            "require_positive_volume": sel_cfg.require_positive_volume,
        },
    }
    return LimitUpRankArtifacts(
        selection=result,
        rank_path=rank_path,
        candidate_count_path=candidate_count_path,
        manifest_updates=manifest_updates,
    )


def run_limit_up_backtest_artifacts(
    *,
    cfg: Mapping[str, Any],
    paths,
    rank_df: pd.DataFrame,
    save: str = "auto",
    no_show: bool = False,
) -> LimitUpBacktestArtifacts:
    if rank_df.empty:
        raise RuntimeError("rank_df is empty")

    stock_num = int(cfg.get("stock_num", default_limit_up_spec().stock_num))
    start = rank_df["date"].min().strftime("%Y-%m-%d")
    end = rank_df["date"].max().strftime("%Y-%m-%d")
    panel_end = (pd.Timestamp(rank_df["date"].max()) + pd.Timedelta(days=7)).strftime("%Y-%m-%d")
    rank_codes = sorted(rank_df["code"].astype(str).str.zfill(6).unique().tolist())
    close, volume = load_close_volume_panel(
        db_path=Path(str(cfg["db_path"])),
        freq=str(cfg["freq"]),
        codes=rank_codes,
        start=start,
        end=panel_end,
    )
    close = close.reindex(columns=rank_codes).astype(float)
    volume = volume.reindex(columns=rank_codes).astype(float)

    tradability_cfg = cfg.get("tradability", {})
    tradability_mask = build_tradability_mask(
        close,
        volume,
        limit_threshold=float(cfg.get("limit_up_threshold", default_limit_up_spec().limit_up_threshold)),
        min_volume=float(tradability_cfg.get("min_volume", 0.0)),
    )

    calendar_code = str(cfg.get("calendar_code", default_limit_up_spec().reference_index_code)).zfill(6)
    index_ratio = load_index_daily_ratio(
        Path(str(cfg["db_path"])),
        str(cfg["freq"]),
        calendar_code,
        start,
        panel_end,
    )

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
        stoploss_limit=float(cfg.get("stoploss_limit", default_limit_up_spec().stoploss_limit)),
        take_profit_ratio=float(cfg.get("take_profit_ratio", default_limit_up_spec().take_profit_ratio)),
        market_stoploss_ratio=float(
            cfg.get("market_stoploss_ratio", default_limit_up_spec().market_stoploss_ratio),
        ),
        loss_black_days=int(cfg.get("loss_black_days", default_limit_up_spec().loss_black_days)),
        no_trade_months=tuple(int(item) for item in cfg.get("no_trade_months", default_limit_up_spec().no_trade_months)),
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
    metrics_row["turnover_estimate"] = estimate_turnover(targets)
    tradable_rows = []
    for dt, codes in targets.items():
        if dt not in tradability_mask.index:
            continue
        row = tradability_mask.loc[dt]
        tradable_rows.extend(bool(row.get(code, False)) for code in codes)
    metrics_row["tradability_pass_rate"] = float(sum(tradable_rows) / len(tradable_rows)) if tradable_rows else 0.0
    metrics_df = pd.DataFrame([metrics_row])

    metrics_path = paths.artifacts_dir / "summary_metrics.csv"
    metrics_df.to_csv(metrics_path, index=False, encoding="utf-8-sig")

    plot_path, drawdown_path = _resolve_plot_paths(
        save_value=save,
        no_show=no_show,
        artifacts_dir=paths.artifacts_dir,
    )
    if plot_path is not None:
        _save_single_curve_plot(equity, plot_path, f"{paths.project}: Strategy equity curve", f"Top{stock_num}")
    if drawdown_path is not None:
        _save_drawdown_plot(equity, drawdown_path, f"{paths.project}: Drawdown from peak")

    manifest_updates = {
        "strategy_mode": "limit_up_screening",
        "rank_path": str(paths.signals_dir / f"rank_top{stock_num}.parquet"),
        "summary_metrics_path": str(metrics_path),
        "plot_path": str(plot_path) if plot_path else "",
        "drawdown_path": str(drawdown_path) if drawdown_path else "",
        "rank_dates": int(rank_df["date"].nunique()),
        "rank_unique_codes": int(rank_df["code"].nunique()),
        "db_path": str(cfg["db_path"]),
        "params": {
            "stock_num": stock_num,
            "stoploss_limit": cfg.get("stoploss_limit", default_limit_up_spec().stoploss_limit),
            "no_trade_months": list(cfg.get("no_trade_months", default_limit_up_spec().no_trade_months)),
            "market_stoploss_ratio": cfg.get(
                "market_stoploss_ratio",
                default_limit_up_spec().market_stoploss_ratio,
            ),
        },
    }

    return LimitUpBacktestArtifacts(
        rank_df=rank_df,
        close_panel=close,
        volume_panel=volume,
        tradability_mask=tradability_mask,
        equity=equity,
        metrics_df=metrics_df,
        metrics_path=metrics_path,
        plot_path=plot_path,
        drawdown_path=drawdown_path,
        manifest_updates=manifest_updates,
    )
