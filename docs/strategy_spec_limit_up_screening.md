# Limit-Up Screening Strategy Specification

> Original strategy design for the MyQuantJournal project.

## Overview

The **Limit-Up Screening** strategy is a weekly-rebalanced, equal-weight
long-only equity strategy for the China A-share market. It targets stocks with
a strong history of price limit-up events, entering at positions closest to
their breakout origin (start-point), and employs multi-layer risk controls
including per-position stop-loss, take-profit, market-wide stop-loss, and
seasonal no-trade periods.

## Universe

| Filter | Rule |
|--------|------|
| Market scope | Shanghai & Shenzhen mainboard (codes starting with `0` or `6`) |
| Exclude STAR Market | Codes starting with `688` / `689` |
| Exclude ChiNext | Codes starting with `300` / `301` |
| Exclude BSE | Codes starting with `4` / `8` |
| Exclude ST / delisting | Name contains "ST", "*", or delisting tag |
| Exclude new stocks | Listed fewer than 375 calendar days |
| Exclude limit-up/down on rebalance day | Daily return >= 9.5% or <= -9.5% |

## Selection Pipeline (per rebalance date)

1. **Pre-filter**: Apply universe filters; require positive volume.
2. **Initial pool**: Take up to `init_pool_size` (default 1000) from filtered
   universe.
3. **Limit-up history count**: Over the trailing `limit_days_window` (default
   750 trading days, ~3 years), count days where `daily_return >= limit_up_threshold`
   (default 9.5%) as proxy limit-up days. Keep the top `top_pct_limit_up`
   (default 10%) of stocks by count.
4. **Start-point scoring**: For each remaining stock:
   - Find the most recent proxy limit-up day in the window.
   - Scan backward from that day to find the first day where `close < open`.
   - Record that day's `low` as the *start price*.
   - Score = `current_close / start_price` (lower = closer to breakout origin).
5. **Rank**: Sort by start-point score ascending; output top
   `stock_num * topk_multiplier` candidates.

## Rebalance Schedule

- **Frequency**: Weekly, on **Tuesday** (configurable via `rebalance_weekday`).
- **Position count**: `stock_num` (default 6) equal-weight positions.

## Risk Controls

### Per-Position Stop-Loss
- Sell when `price < avg_cost * stoploss_limit` (default 0.91, i.e. ~9% loss).
- After stop-loss, the stock is blacklisted for `loss_black_days` (default 20).

### Per-Position Take-Profit
- Sell when `price >= avg_cost * take_profit_ratio` (default 2.0, i.e. 100% gain).

### Market-Wide Stop-Loss
- Monitor a reference index (configured via `calendar_code`, e.g. `000001`).
- If the index's daily `close / open` ratio falls to or below
  `market_stoploss_ratio` (default 0.93), liquidate all positions immediately.

### No-Trade Months
- During months specified in `no_trade_months` (default: January and April),
  do not open new positions.
- At the end of each no-trade month, all remaining positions are cleared to cash.

## Cost Model

| Parameter | Default | Description |
|-----------|---------|-------------|
| `commission` | 0.0001 (1 bp) | Commission rate per side |
| `stamp_duty` | 0.0005 (5 bp) | Stamp duty on sells only |
| `slippage` | 0.002 (20 bp) | Slippage cost per trade |
| `min_commission` | 5.0 CNY | Minimum commission per side |
| `cash` | 1,000,000 CNY | Initial capital |

## Configuration Reference

All parameters are set via the project JSON config (e.g.
`configs/projects/2026Q1_limit_up.json`). Key fields:

```json
{
  "strategy_mode": "limit_up_screening",
  "stock_num": 6,
  "rebalance_weekday": 1,
  "limit_days_window": 750,
  "top_pct_limit_up": 0.10,
  "limit_up_threshold": 0.095,
  "init_pool_size": 1000,
  "stoploss_limit": 0.91,
  "take_profit_ratio": 2.0,
  "market_stoploss_ratio": 0.93,
  "loss_black_days": 20,
  "no_trade_months": [1, 4],
  "min_commission": 5
}
```

## Known Simplifications

- **Limit-up proxy**: Uses daily return threshold instead of exchange-provided
  `high_limit` price (not available in local OHLCV data).
- **Market cap sorting**: Not implemented in current version (no fundamental
  data in DB). The full filtered pool is used instead of a market-cap-sorted
  top-1000.
- **Industry diversification**: Not implemented (no industry classification
  data in DB). Planned as future enhancement.
- **Defense assets**: No-trade months clear to cash rather than rotating into
  defensive ETFs. Configurable defense assets are a future extension.

## Outputs

- Rank file: `data/projects/<project>/signals/rank_top<N>.parquet`
- Metrics: `artifacts/projects/<project>/summary_metrics.csv`
- Equity curve: `artifacts/projects/<project>/equity_curve.png`
- Run manifest: `data/projects/<project>/meta/run_manifest.json`
