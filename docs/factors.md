# Factor Library (Initial Set)

All factors are generated through the unified interface:

- `build_factor(name, close, volume)`
- output path: `data/projects/<project>/features/<factor>.parquet`

## Included Factors

1. `mom20`
- definition: `close[t] / close[t-20] - 1`
- intuition: medium-term momentum continuation

2. `rev5`
- definition: `-(close[t] / close[t-5] - 1)`
- intuition: short-term reversal

3. `vol20`
- definition: rolling 20-day standard deviation of daily returns
- intuition: recent volatility regime

4. `range`
- definition: rolling 20-day mean of absolute daily returns
- intuition: price movement amplitude

5. `vol_surge`
- definition: `volume / rolling_mean(volume, 20) - 1`
- intuition: unusual trading activity

6. `ma_gap`
- definition: `close / MA20 - 1`
- intuition: trend distance from moving average

## Usage

- script:
  - `python scripts/steps/34_build_factors.py --project as_share_research_v1`
- unified CLI:
  - `python -m quant_mvp run --project as_share_research_v1 --task factors`
