# Limit-Up Screening Strategy Spec

## Scope
- Market: China A-share mainboard only
- Frequency: daily / weekly research
- Phase boundary: research only, no live trading promises

## Canonical Defaults
- `stock_num`: 6
- `rebalance_weekday`: 1 (`Tuesday`)
- `limit_days_window`: 250
- `top_pct_limit_up`: 0.10
- `limit_up_threshold`: 0.095
- `init_pool_size`: 1000
- `min_bars`: 160
- `topk_multiplier`: 2
- `stoploss_limit`: 0.91
- `take_profit_ratio`: 2.0
- `market_stoploss_ratio`: 0.93
- `loss_black_days`: 20
- `no_trade_months`: `[1, 4]`
- `max_drawdown_limit`: 0.30

## Selection Contract
1. Freeze a project universe before ranking.
2. Keep only mainboard A-share symbols; exclude STAR, ChiNext, BSE, ST, delisting-risk, and too-new listings.
3. Exclude stocks with zero volume or proxy limit-locks on the rebalance day.
4. Count proxy limit-up days over the trailing window.
5. Keep the top fraction by limit-up count.
6. Score survivors by distance to the most recent breakout origin.
7. Sort ascending by score and output `stock_num * topk_multiplier` candidates.

## Rebalance Contract
- Rebalance only on Tuesday.
- Rank dates must be trading days and must have a next trading day for forward returns.
- Contract tests must fail if Tuesday drifts to any other weekday.

## Evaluation Contract
- Promotion requires no obvious leakage, walk-forward survival, cost sensitivity resilience, and `max_drawdown <= 30%`.
- Tradability, turnover, suspension proxies, and price-limit proxies must be included in evaluation outputs.
