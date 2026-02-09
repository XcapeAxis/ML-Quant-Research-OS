from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np
import pandas as pd


@dataclass
class BacktestConfig:
    cash: float
    commission: float
    stamp_duty: float
    slippage: float
    risk_free_rate: float = 0.03
    risk_overlay: dict | None = None


def max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    dd = (equity / peak) - 1.0
    return float(dd.min()) if not dd.empty else 0.0


def annualized_return(daily_returns: pd.Series) -> float:
    if daily_returns.empty:
        return 0.0
    total = float((1.0 + daily_returns).prod() - 1.0)
    return float((1.0 + total) ** (252.0 / max(len(daily_returns), 1)) - 1.0)


def annualized_volatility(daily_returns: pd.Series) -> float:
    if daily_returns.empty:
        return 0.0
    return float(daily_returns.std(ddof=0) * np.sqrt(252.0))


def sharpe_ratio(daily_returns: pd.Series, risk_free_rate: float) -> float:
    vol = annualized_volatility(daily_returns)
    if vol <= 0:
        return 0.0
    ret = annualized_return(daily_returns)
    return float((ret - risk_free_rate) / vol)


def summarize_equity(equity: pd.Series, cfg: BacktestConfig) -> dict[str, float]:
    daily_returns = equity.pct_change().fillna(0.0)
    return {
        "total_return": float(equity.iloc[-1] / equity.iloc[0] - 1.0) if len(equity) > 1 else 0.0,
        "annualized_return": annualized_return(daily_returns),
        "annualized_volatility": annualized_volatility(daily_returns),
        "max_drawdown": max_drawdown(equity),
        "sharpe_ratio": sharpe_ratio(daily_returns, cfg.risk_free_rate),
        "days": float(len(equity)),
        "final_equity": float(equity.iloc[-1]) if not equity.empty else float(cfg.cash),
    }


def rank_targets(rank_df: pd.DataFrame, topn: int) -> dict[pd.Timestamp, list[str]]:
    out: dict[pd.Timestamp, list[str]] = {}
    for dt, group in rank_df.groupby("date"):
        chosen = group[group["rank"] <= topn]["code"].astype(str).str.zfill(6).tolist()
        out[pd.Timestamp(dt)] = chosen
    return out


def equal_weight_targets(
    calendar: pd.DatetimeIndex,
    codes: list[str],
    rebalance_every: int,
) -> dict[pd.Timestamp, list[str]]:
    out: dict[pd.Timestamp, list[str]] = {}
    for dt in calendar[::rebalance_every]:
        out[pd.Timestamp(dt)] = list(codes)
    return out


def _apply_risk_overlay(
    daily_returns: list[float],
    raw_portfolio_return: float,
    overlay: dict | None,
) -> float:
    if not overlay or not overlay.get("enabled", False):
        return raw_portfolio_return

    rolling_days = int(overlay.get("rolling_days", 20))
    vol_target = float(overlay.get("vol_target", 0.18))
    max_leverage = float(overlay.get("max_leverage", 1.0))

    history = pd.Series(daily_returns[-rolling_days:])
    realized = history.std(ddof=0) * np.sqrt(252.0) if not history.empty else 0.0
    if realized <= 1e-10:
        scale = 1.0
    else:
        scale = min(max_leverage, max(0.0, vol_target / realized))
    return raw_portfolio_return * scale


def run_rebalance_backtest(
    close_panel: pd.DataFrame,
    targets_by_date: Mapping[pd.Timestamp, list[str]],
    cfg: BacktestConfig,
) -> pd.Series:
    if close_panel.empty:
        raise RuntimeError("close panel is empty")

    close = close_panel.sort_index()
    returns = close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    codes = list(close.columns)
    weights = pd.Series(0.0, index=codes, dtype=float)

    dates = list(close.index)
    value = float(cfg.cash)
    equity: dict[pd.Timestamp, float] = {pd.Timestamp(dates[0]): value}
    daily_ret_hist: list[float] = []

    for i, dt in enumerate(dates):
        ts = pd.Timestamp(dt)
        if ts in targets_by_date:
            target_codes = [c for c in targets_by_date[ts] if c in close.columns]
            tradable = [c for c in target_codes if pd.notna(close.loc[ts, c])]
            target = pd.Series(0.0, index=codes, dtype=float)
            if tradable:
                target.loc[tradable] = 1.0 / len(tradable)
            delta = target - weights
            buy_notional = float(delta[delta > 0].sum()) * value
            sell_notional = float((-delta[delta < 0]).sum()) * value
            trading_notional = buy_notional + sell_notional
            fee = trading_notional * (cfg.commission + cfg.slippage) + sell_notional * cfg.stamp_duty
            value = max(0.0, value - fee)
            weights = target

        if i + 1 >= len(dates):
            break

        nxt = pd.Timestamp(dates[i + 1])
        day_returns = returns.loc[nxt].reindex(codes).fillna(0.0)
        raw_ret = float((weights * day_returns).sum())
        applied_ret = _apply_risk_overlay(daily_ret_hist, raw_ret, cfg.risk_overlay)
        value *= 1.0 + applied_ret
        daily_ret_hist.append(applied_ret)
        equity[nxt] = value

    series = pd.Series(equity).sort_index()
    series.name = "equity"
    return series


def run_topn_suite(
    close_panel: pd.DataFrame,
    rank_df: pd.DataFrame,
    cfg: BacktestConfig,
    topn_max: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    equities: list[pd.Series] = []
    metrics_rows: list[dict[str, float]] = []
    for topn in range(1, topn_max + 1):
        targets = rank_targets(rank_df, topn=topn)
        equity = run_rebalance_backtest(close_panel=close_panel, targets_by_date=targets, cfg=cfg)
        equity.name = f"Top{topn}"
        equities.append(equity)
        row = summarize_equity(equity, cfg)
        row["topn"] = float(topn)
        metrics_rows.append(row)
    curves = pd.concat(equities, axis=1).sort_index()
    metrics = pd.DataFrame(metrics_rows)
    metrics["topn"] = metrics["topn"].astype(int)
    return curves, metrics
