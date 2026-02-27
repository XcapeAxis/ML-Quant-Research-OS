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
    min_commission: float | None = None


@dataclass
class StoplossParams:
    """Optional params for run_rebalance_backtest_with_stoploss (original strategy design)."""

    stoploss_limit: float = 0.91  # sell when price < cost * this (~9% loss)
    take_profit_ratio: float = 2.0  # sell when price >= cost * this (100% gain)
    market_stoploss_ratio: float = 0.93  # clear all when index daily close/open <= this
    loss_black_days: int = 20  # do not buy a code for this many days after stop-loss sell
    no_trade_months: tuple[int, ...] = (1, 4)  # Jan, Apr: no new buys; clear to cash at month end
    min_commission: float | None = 5.0  # per-side minimum commission; None = proportional only


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


def _commission_fee(notional: float, rate: float, min_comm: float | None) -> float:
    """Apply proportional commission with optional minimum per side."""
    fee = notional * rate
    if min_comm is not None and fee < min_comm:
        return min_comm
    return fee


def run_rebalance_backtest_with_stoploss(
    close_panel: pd.DataFrame,
    targets_by_date: Mapping[pd.Timestamp, list[str]],
    cfg: BacktestConfig,
    stoploss_params: StoplossParams | None = None,
    index_daily_ratio: pd.Series | None = None,
) -> pd.Series:
    """
    Rebalance backtest with per-position stop-loss, take-profit, market stop-loss,
    blacklist after stop-loss, and no-trade months (clear to cash at month end).
    Tracks average cost per position for stop-loss/take-profit checks.
    """
    if close_panel.empty:
        raise RuntimeError("close panel is empty")
    params = stoploss_params or StoplossParams()
    close = close_panel.sort_index()
    returns = close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    codes = list(close.columns)
    weights = pd.Series(0.0, index=codes, dtype=float)
    avg_cost = pd.Series(np.nan, index=codes, dtype=float)
    blacklist: dict[str, pd.Timestamp] = {}
    dates = list(close.index)
    value = float(cfg.cash)
    equity: dict[pd.Timestamp, float] = {pd.Timestamp(dates[0]): value}
    daily_ret_hist: list[float] = []
    min_comm = params.min_commission if params.min_commission is not None else getattr(cfg, "min_commission", None)

    for i, dt in enumerate(dates):
        ts = pd.Timestamp(dt)
        month = ts.month
        is_last_day_of_month = (i + 1 >= len(dates)) or (pd.Timestamp(dates[i + 1]).month != month)

        # 1) No-trade month: clear to cash at end of month
        if month in params.no_trade_months and is_last_day_of_month:
            sell_notional = float(weights.sum()) * value
            if sell_notional > 0:
                fee = _commission_fee(sell_notional, cfg.commission + cfg.slippage, min_comm) + sell_notional * cfg.stamp_duty
                value = max(0.0, value - fee)
            weights = pd.Series(0.0, index=codes, dtype=float)
            avg_cost = pd.Series(np.nan, index=codes, dtype=float)

        # 2) Market stop-loss: index close/open <= threshold
        if index_daily_ratio is not None and not index_daily_ratio.empty and ts in index_daily_ratio.index:
            ratio = float(index_daily_ratio.loc[ts])
            if ratio <= params.market_stoploss_ratio:
                sold = [c for c in codes if weights[c] > 0]
                if sold:
                    sell_notional = float(weights[sold].sum()) * value
                    fee = _commission_fee(sell_notional, cfg.commission + cfg.slippage, min_comm) + sell_notional * cfg.stamp_duty
                    value = max(0.0, value - fee)
                    for c in sold:
                        blacklist[c] = ts
                    weights = pd.Series(0.0, index=codes, dtype=float)
                    avg_cost = pd.Series(np.nan, index=codes, dtype=float)

        # 3) Per-position stop-loss and take-profit
        if not (month in params.no_trade_months and is_last_day_of_month):
            for c in codes:
                if weights[c] <= 0 or pd.isna(avg_cost[c]):
                    continue
                try:
                    pr = float(close.loc[ts, c])
                except (KeyError, TypeError):
                    continue
                if pd.isna(pr) or pr <= 0:
                    continue
                cost = float(avg_cost[c])
                if cost <= 0:
                    continue
                if pr < cost * params.stoploss_limit or pr >= cost * params.take_profit_ratio:
                    w = float(weights[c])
                    sell_notional = w * value
                    fee = _commission_fee(sell_notional, cfg.commission + cfg.slippage, min_comm) + sell_notional * cfg.stamp_duty
                    value = max(0.0, value - fee)
                    weights[c] = 0.0
                    avg_cost[c] = np.nan
                    blacklist[c] = ts

        # 4) Rebalance (if not in no-trade month)
        if ts in targets_by_date and month not in params.no_trade_months:
            target_codes_raw = [c for c in targets_by_date[ts] if c in close.columns]
            target_codes = [
                c for c in target_codes_raw
                if c not in blacklist or (ts - blacklist[c]).days > params.loss_black_days
            ]
            tradable = [c for c in target_codes if pd.notna(close.loc[ts, c]) and float(close.loc[ts, c]) > 0]
            target = pd.Series(0.0, index=codes, dtype=float)
            if tradable:
                target.loc[tradable] = 1.0 / len(tradable)
                for c in tradable:
                    avg_cost[c] = float(close.loc[ts, c])
            delta = target - weights
            buy_notional = float(delta[delta > 0].sum()) * value
            sell_notional = float((-delta[delta < 0]).sum()) * value
            trading_notional = buy_notional + sell_notional
            fee_buy = _commission_fee(buy_notional, cfg.commission + cfg.slippage, min_comm)
            fee_sell = _commission_fee(sell_notional, cfg.commission + cfg.slippage, min_comm) + sell_notional * cfg.stamp_duty
            value = max(0.0, value - fee_buy - fee_sell)
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
