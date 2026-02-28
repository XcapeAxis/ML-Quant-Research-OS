# MyQuantJournal

A reproducible, project-scoped **China A-share quantitative research platform**
built on local SQLite market data and a modular Python pipeline. It implements
an original **Limit-Up Screening** strategy as the main research workflow.

---

## Table of Contents

- [Design Philosophy](#design-philosophy)
- [Features](#features)
- [Quickstart](#quickstart)
- [Strategy Overview](#strategy-overview)
- [Strategy Parameters](#strategy-parameters)
- [Repository Structure](#repository-structure)
- [Configuration](#configuration)
- [Reproducibility](#reproducibility)
- [Results & Artifacts](#results--artifacts)
- [Unified CLI](#unified-cli)
- [Data Flow](#data-flow)
- [Development](#development)
- [Roadmap & Future Work](#roadmap--future-work)
- [License & Disclaimer](#license--disclaimer)

---

## Design Philosophy

1. **Reproducibility first** -- every experiment is pinned to a frozen universe,
   a JSON config, and a run manifest recording git commit, timestamps, and
   parameter snapshots.
2. **Local-first data** -- all market data lives in a single SQLite file
   (`data/market.db`); no cloud dependency at runtime.
3. **Modular pipeline** -- universe construction, bar updates, ranking,
   backtesting, and reporting are independent steps that compose via shared
   file conventions.
4. **Strategy as code** -- the primary Limit-Up Screening strategy is fully
   implemented in Python with clear separation between selection logic
   (`quant_mvp/selection.py`), backtest engine (`quant_mvp/backtest_engine.py`),
   and pipeline scripts.

---

## Features

| Area | Capability |
|------|-----------|
| **Data** | AkShare integration for A-share daily OHLCV; incremental & backfill modes; SQLite WAL storage |
| **Universe** | Configurable filters: mainboard only, exclude STAR/ChiNext/BSE/ST/new stocks; frozen universe file |
| **Selection** | Limit-up history screening, start-point scoring, Tuesday rebalance calendar |
| **Backtest** | Equal-weight rebalance engine with transaction costs (commission, stamp duty, slippage, min commission) |
| **Risk Controls** | Per-position stop-loss & take-profit, market-wide stop-loss (index close/open), no-trade months, post-stop-loss blacklist |
| **Analysis** | Cost sensitivity sweep (5x5 grid), walk-forward validation, baseline & random controls |
| **Reporting** | Auto-generated Markdown reports with equity curves, metrics tables, coverage stats |
| **Dashboard** | Streamlit app for interactive project browsing |
| **Factor Library** | Six built-in factors: mom20, rev5, vol20, range, vol_surge, ma_gap |
| **CLI** | Unified `python -m quant_mvp run` entry point for all tasks |

---

## Quickstart

### Prerequisites

- Python 3.10+
- Install dependencies:
  ```bash
  pip install -r requirements.txt
  ```

### Quickstart: Limit-Up Screening Strategy

```bash
# 1. Build and freeze universe
python scripts/steps/10_symbols.py --project 2026Q1_limit_up

# 2. Fetch daily bars into SQLite
python scripts/steps/11_update_bars.py --project 2026Q1_limit_up --mode incremental

# 3. Build rank (limit-up screening + start-point)
python scripts/steps/20_build_rank.py --project 2026Q1_limit_up

# 4. Run backtest with stop-loss, take-profit, market stop-loss
python scripts/steps/30_bt_rebalance.py --project 2026Q1_limit_up --no-show --save auto

# 5. Audit data coverage
python scripts/audit_db.py --project 2026Q1_limit_up

# 6. Generate report
python scripts/steps/40_make_report.py --project 2026Q1_limit_up
```

Or run the full strategy as a single script:
```bash
python scripts/run_limit_up_screening.py --project 2026Q1_limit_up --no-show --save auto
```

---

## Strategy Overview

### Limit-Up Screening (primary)

An original strategy that identifies A-share stocks with strong historical
limit-up activity, enters positions near their breakout origin, and manages
risk through multi-layer controls.

**Selection pipeline (per Tuesday rebalance):**

1. Apply universe filters (exclude STAR/ChiNext/BSE/ST/new/limit-locked stocks).
2. Take initial pool (up to 1000 stocks).
3. Count proxy limit-up days in trailing 750-day window (daily return >= 9.5%).
4. Keep top 10% by limit-up count.
5. Score by **start-point bias**: find most recent limit-up day, scan backward
   for first bearish candle (`close < open`), use its low as start price.
   `score = current_close / start_price` (lower = preferred).
6. Rank ascending by score; select top `stock_num * 2` candidates.

**Risk controls:**

- **Stop-loss**: sell when `price < cost * 0.91` (~9% loss)
- **Take-profit**: sell when `price >= cost * 2.0` (100% gain)
- **Market stop-loss**: clear all when index `close/open <= 0.93`
- **No-trade months**: January & April -- clear to cash at month end
- **Blacklist**: 20-day cool-off after any stop-loss trigger

---

## Strategy Parameters

### Limit-Up Screening

| Parameter | Default | Description |
|-----------|---------|-------------|
| `strategy_mode` | `"limit_up_screening"` | Strategy selector |
| `stock_num` | 6 | Number of positions |
| `rebalance_weekday` | 1 (Tuesday) | Rebalance day of week |
| `limit_days_window` | 750 | Trailing window for limit-up counting (~3 years) |
| `top_pct_limit_up` | 0.10 | Keep top 10% by limit-up count |
| `limit_up_threshold` | 0.095 | Daily return threshold for proxy limit-up |
| `init_pool_size` | 1000 | Pre-filter pool size |
| `stoploss_limit` | 0.91 | Stop-loss trigger (price / cost) |
| `take_profit_ratio` | 2.0 | Take-profit trigger (price / cost) |
| `market_stoploss_ratio` | 0.93 | Market-wide stop-loss (index close/open) |
| `loss_black_days` | 20 | Blacklist duration after stop-loss |
| `no_trade_months` | [1, 4] | January & April |
| `commission` | 0.0001 | Commission per side |
| `stamp_duty` | 0.0005 | Stamp duty on sells |
| `slippage` | 0.002 | Slippage per trade |
| `min_commission` | 5.0 | Minimum commission (CNY) |
| `cash` | 1,000,000 | Initial capital (CNY) |

---

## Repository Structure

```
MyQuantJournal/
├── quant_mvp/                  Core library
│   ├── __init__.py
│   ├── __main__.py             Unified CLI entry
│   ├── cli.py                  CLI task routing
│   ├── config.py               Config loading & defaults
│   ├── project.py              Project path resolution
│   ├── db.py                   SQLite OHLCV storage
│   ├── universe.py             Universe load/save
│   ├── manifest.py             Run manifest tracking
│   ├── selection.py            Limit-up screening strategy logic
│   ├── ranking.py              Ranking (limit-up screening)
│   ├── backtest_engine.py      Backtest engines (plain & stop-loss)
│   ├── factors.py              Factor library
│   └── reporting.py            Report generation
├── scripts/
│   ├── run_limit_up_screening.py   Standalone strategy entry point
│   ├── steps/
│   │   ├── 10_symbols.py           Universe construction
│   │   ├── 11_update_bars.py       Bar data fetch & update
│   │   ├── 20_build_rank.py        Ranking (limit-up screening)
│   │   ├── 30_bt_rebalance.py      Backtest (with stop-loss)
│   │   ├── 31_bt_baselines.py      Baseline & random controls
│   │   ├── 32_cost_sweep.py        Cost sensitivity analysis
│   │   ├── 33_walk_forward.py      Walk-forward validation
│   │   ├── 34_build_factors.py     Factor generation
│   │   └── 40_make_report.py       Report generation
│   ├── audit_db.py                 Database coverage audit
│   └── tools/                      Optional utilities
├── configs/projects/               Project JSON configs
│   └── 2026Q1_limit_up.json        Limit-up screening config
├── data/
│   ├── market.db                   SQLite OHLCV database
│   └── projects/<name>/
│       ├── meta/                   universe_codes.txt, run_manifest.json
│       ├── signals/                rank_topK.parquet
│       └── features/               Factor parquets
├── artifacts/projects/<name>/      Metrics CSV, equity plots, reports
├── docs/
│   ├── strategy_spec_limit_up_screening.md   Strategy specification
│   ├── factors.md                            Factor definitions
│   ├── projects/                             Per-project notes
│   └── DECISIONS.md                          Architecture decisions
├── dashboard/app.py               Streamlit dashboard
├── tests/                         Unit & smoke tests
├── requirements.txt
├── pyproject.toml
└── README.md
```

---

## Configuration

Each project is driven by a JSON config under `configs/projects/`. Example
for the limit-up screening strategy:

```json
{
  "freq": "1d",
  "strategy_mode": "limit_up_screening",
  "calendar_code": "000001",
  "start_date": "2016-01-01",
  "stock_num": 6,
  "rebalance_weekday": 1,
  "limit_days_window": 750,
  "top_pct_limit_up": 0.10,
  "limit_up_threshold": 0.095,
  "stoploss_limit": 0.91,
  "take_profit_ratio": 2.0,
  "market_stoploss_ratio": 0.93,
  "loss_black_days": 20,
  "no_trade_months": [1, 4],
  "commission": 0.0001,
  "stamp_duty": 0.0005,
  "slippage": 0.002,
  "min_commission": 5,
  "cash": 1000000
}
```

CLI overrides take precedence over file config, which takes precedence over
built-in defaults (see `quant_mvp/config.py`).

---

## Reproducibility

Every run is reproducible through:

| Artifact | Path |
|----------|------|
| Project config | `configs/projects/<project>.json` |
| Frozen universe | `data/projects/<project>/meta/universe_codes.txt` |
| Run manifest | `data/projects/<project>/meta/run_manifest.json` |
| Rank signals | `data/projects/<project>/signals/rank_top<N>.parquet` |
| Metrics & plots | `artifacts/projects/<project>/` |

The run manifest records the git commit hash, timestamp, universe size,
parameter snapshot, and paths to all generated artifacts.

---

## Results & Artifacts

After running the pipeline, key outputs are:

- **Metrics**: `artifacts/projects/<project>/summary_metrics.csv`
- **Equity curve**: `artifacts/projects/<project>/equity_curve.png`
- **Report**: `artifacts/projects/<project>/report.md`
- **Baseline comparison**: `artifacts/projects/<project>/baseline_metrics.csv`
- **Cost sweep**: `artifacts/projects/<project>/cost_sweep_metrics.csv`
- **Walk-forward**: `artifacts/projects/<project>/walk_forward_metrics.csv`

---

## Unified CLI

Run any pipeline task with a single entry point:

```bash
# Build rank
python -m quant_mvp run --project 2026Q1_limit_up --task rank

# Run backtest
python -m quant_mvp run --project 2026Q1_limit_up --task backtest -- --no-show --save auto

# Run standalone strategy
python -m quant_mvp run --project 2026Q1_limit_up --task strategy

# Build factors
python -m quant_mvp run --project 2026Q1_limit_up --task factors
```

Available tasks: `universe`, `update`, `rank`, `backtest`, `strategy`,
`baselines`, `cost`, `walk_forward`, `audit`, `report`, `factors`.

---

## Data Flow

```
Universe Definition (10_symbols.py)
        │
        ▼
Data Update (11_update_bars.py)  ──▶  SQLite market.db
        │
        ▼
Stock Ranking (20_build_rank.py)  ── limit_up_screening rank
        │
        ▼
Backtest (30_bt_rebalance.py)  ── run_rebalance_backtest_with_stoploss
        │
        ▼
Reporting (40_make_report.py)  ──▶  Markdown report + artifacts
```

---

## Development

### Running Tests

```bash
python -m pytest tests/ -v
```

### Database Audit

```bash
python scripts/audit_db.py --project 2026Q1_limit_up
```

### Streamlit Dashboard

```bash
streamlit run dashboard/app.py
```

### Code Quality

- Pre-commit hooks configured in `.pre-commit-config.yaml`
- CI workflow in `.github/workflows/ci.yml`

---

## Roadmap & Future Work

- [ ] Add market capitalization data (AkShare fundamentals) for small-cap sort
- [ ] Add Shenwan L2 industry classification for cross-industry diversification
- [ ] Implement defense asset rotation (ETFs) during no-trade months
- [ ] Add turnover monitoring and volume-based exit signals
- [ ] Multi-factor composite scoring (limit-up + momentum + volatility)
- [ ] Live/paper trading integration

---

## License & Disclaimer

This project is for **research and educational purposes only**. It is not
financial advice and should not be used for actual trading without proper
validation and risk management. Past backtest performance does not guarantee
future results.
