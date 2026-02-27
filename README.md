# Quant ML MVP

A-share momentum and stock-selection research platform using SQLite bars and reproducible, project-scoped experiments.

## Features

- **Data**: Local SQLite storage with AkShare integration for A-share market data
- **Universe**: Configurable stock universe with filtering (ST, new stocks, STAR Market, etc.)
- **Selection**: Multiple ranking strategies including momentum and combined momentum + start-point
- **Backtest**: Equal-weight rebalancing with cost modeling, stop-loss, take-profit, and market stop-loss
- **Reporting**: Automated performance reports and metrics

## Quickstart

### Basic Momentum Strategy

1. Build and freeze universe, then update bars:
   ```bash
   python scripts/steps/10_symbols.py --project 2026Q1_mom
   python scripts/steps/11_update_bars.py --project 2026Q1_mom --mode incremental
   ```

2. Build rank and candidate stats:
   ```bash
   python scripts/steps/20_build_rank.py --project 2026Q1_mom
   ```

3. Backtest and generate report:
   ```bash
   python scripts/steps/30_bt_rebalance.py --project 2026Q1_mom --no-show --save auto
   python scripts/audit_db.py --project 2026Q1_mom
   python scripts/steps/40_make_report.py --project 2026Q1_mom
   ```

### Original Strategy (Momentum + Stop-Loss)

Run the complete strategy with a single command:

```bash
python scripts/strategy_jq.py --project 2026Q1_jq
```

This implements the original design with:
- Tuesday-only rebalancing
- Stop-loss at 0.91 (~9% loss threshold)
- Take-profit at 2.0x (100% gain)
- Market stop-loss at 0.93 (index close/open ratio)
- No-trade months: January and April (hold cash)
- 20-day blacklist after stop-loss triggers

## Strategy Details

### Original Design (scripts/strategy_jq.py)

The original strategy is an original design featuring:

| Parameter | Value | Description |
|-----------|-------|-------------|
| `stock_num` | 6 | Number of stocks to hold |
| `rebalance_weekday` | 1 (Tuesday) | Rebalance only on Tuesdays |
| `stoploss_limit` | 0.91 | Sell when price < cost * 0.91 (~9% loss) |
| `take_profit_ratio` | 2.0 | Sell when price >= cost * 2.0 (100% gain) |
| `market_stoploss_ratio` | 0.93 | Clear all when index close/open <= 0.93 |
| `loss_black_days` | 20 | Days to blacklist after stop-loss |
| `no_trade_months` | [1, 4] | January and April: hold cash |
| `commission` | 0.0001 | Commission rate |
| `stamp_duty` | 0.0005 | Stamp duty on sells |
| `slippage` | 0.002 | Slippage cost |
| `min_commission` | 5.0 | Minimum commission per trade |

**Simplifications due to data availability:**
- Market cap and industry data not used in ranking (using momentum + start-point instead)
- Limit up/down approximated by daily return thresholds
- No-trade months implemented as cash holding (no defense ETFs)

## Results

Main artifacts for momentum strategy:
- `artifacts/projects/2026Q1_mom/topn_1_5.png`
- `artifacts/projects/2026Q1_mom/summary_metrics.csv`
- `artifacts/projects/2026Q1_mom/report.md`

Main artifacts for original strategy:
- `artifacts/projects/2026Q1_jq/rank_jq.parquet`
- `artifacts/projects/2026Q1_jq/equity_jq.csv`
- `artifacts/projects/2026Q1_jq/metrics_jq.json`

## Reproducibility

Each run is reproducible through:
- Project config: `configs/projects/<project>.json`
- Frozen universe: `data/projects/<project>/meta/universe_codes.txt`
- Run manifest: `data/projects/<project>/meta/run_manifest.json`
- Generated reports and metrics under `artifacts/projects/<project>/`

## Project Structure

```
.
├── quant_mvp/              # Core library modules
│   ├── backtest_engine.py  # Backtesting with stop-loss support
│   ├── selection.py        # Stock selection and ranking
│   ├── ranking.py          # Momentum ranking utilities
│   ├── db.py               # SQLite database operations
│   ├── universe.py         # Universe building
│   ├── reporting.py        # Report generation
│   └── ...
├── scripts/
│   ├── strategy_jq.py      # Main strategy entry point
│   ├── steps/              # Pipeline stages
│   │   ├── 10_symbols.py
│   │   ├── 11_update_bars.py
│   │   ├── 20_build_rank.py
│   │   ├── 30_bt_rebalance.py
│   │   └── ...
│   └── audit_db.py         # Database coverage audit
├── configs/projects/       # Project configurations
├── data/projects/          # Project data and metadata
├── artifacts/projects/     # Generated outputs
├── docs/                   # Documentation
│   ├── factors.md          # Factor library
│   └── projects/           # Project notes
└── tests/                  # Unit and smoke tests
```

## Configuration

Example configuration for the original strategy (`configs/projects/2026Q1_jq.json`):

```json
{
  "name": "2026Q1_jq",
  "strategy": "jq",
  "stock_num": 6,
  "rebalance_weekday": 1,
  "lookback": 60,
  "stoploss_limit": 0.91,
  "take_profit_ratio": 2.0,
  "market_stoploss_ratio": 0.93,
  "loss_black_days": 20,
  "no_trade_months": [1, 4],
  "commission": 0.0001,
  "stamp_duty": 0.0005,
  "slippage": 0.002,
  "min_commission": 5.0
}
```

## Unified CLI

Run any task with one entrypoint:
```bash
python -m quant_mvp run --project 2026Q1_mom --task rank
python -m quant_mvp run --project 2026Q1_mom --task backtest -- --no-show --save auto
```

## Data Flow

1. **Universe Definition** (`10_symbols.py`): Define and freeze the stock universe
2. **Data Update** (`11_update_bars.py`): Fetch and store price data in SQLite
3. **Selection** (`strategy_jq.py` or `20_build_rank.py`): Generate stock rankings
4. **Backtest** (`strategy_jq.py` or `30_bt_rebalance.py`): Run backtest with costs
5. **Reporting** (`40_make_report.py`): Generate performance reports

## Syncing to GitHub

To commit and push changes:

```bash
# Check status
git status

# Add all changes
git add .

# Commit with descriptive message
git commit -m "feat: implement original strategy with stop-loss"

# Push to origin
git push origin main
```

To configure remote (if not set):
```bash
git remote add origin https://github.com/username/repo.git
```

## Development

Run tests:
```bash
python -m pytest tests/ -v
```

Check database coverage:
```bash
python scripts/audit_db.py --project 2026Q1_jq
```

## License and Disclaimer

This project is for research and educational purposes only. It is not financial advice and should not be used for actual trading without proper validation and risk management.

## Recent Updates

- **2026-02-28**: Added original strategy implementation with stop-loss, take-profit, and market stop-loss
  - New module: `quant_mvp/selection.py` for Tuesday-only rebalance calendar and momentum + start-point ranking
  - New module: `quant_mvp/backtest_engine.py` extensions for stop-loss support
  - New script: `scripts/strategy_jq.py` as main strategy entry point
  - New config: `configs/projects/2026Q1_jq.json`

- **2026-02-08**: Fixed AkShare Chinese-column compatibility
  - Updated `scripts/steps/11_update_bars.py` (`_fetch_akshare_daily`)
  - Updated `scripts/steps/10_symbols.py` (`build_symbols`, `_is_st`)
  - Added offline regression tests in `tests/test_akshare_column_mapping.py`
