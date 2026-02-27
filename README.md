# Quant ML MVP

A-share momentum and stock-selection research platform with an original strategy design. Uses SQLite for bars, project-scoped configs, and reproducible backtests.

---

## Features

| Area | Description |
|------|-------------|
| **Data** | AkShare for A-share symbols and daily bars; SQLite (`data/market.db`) for storage |
| **Universe** | Mainboard filter (Shanghai/Shenzhen), ST and board exclusions; frozen universe per project |
| **Selection** | Momentum rank (e.g. 20-day) and optional Tuesday-only rebalance calendar |
| **Backtest** | Equal-weight rebalance, commission/slippage/stamp duty; optional stop-loss, take-profit, market stop-loss, no-trade months, blacklist |
| **Reporting** | Markdown report, summary metrics CSV, equity curve plots, run manifest |

---

## Strategy (Original Design)

The main strategy is implemented in `scripts/strategy_jq.py`. It is an original design with the following logic:

- **Rebalance**: Tuesdays only; equal weight over the top `stock_num` names (default 6).
- **Stoploss**: Sell when price &lt; cost × 0.91 (about 9% loss).
- **Take-profit**: Sell when price ≥ cost × 2 (100% gain).
- **Market stop-loss**: Clear all positions when the benchmark index daily close/open ratio ≤ 0.93 (broad market down about 7% or more that day).
- **No-trade months**: January and April: no new buys; clear to cash at month end.
- **Blacklist**: After a stop-loss sell, the code is not bought again for 20 days.

Simplifications when data is limited: no market-cap or industry sort; no-trade months implemented as cash; limit up/down approximated by daily return when needed.

---

## Quickstart

**Requirements**: Python 3.10+, `pip install -r requirements.txt` (includes pandas, matplotlib, akshare, pyarrow).

1. **Build universe and update bars**
   ```bash
   python scripts/steps/10_symbols.py --project 2026Q1_mom
   python scripts/steps/11_update_bars.py --project 2026Q1_mom --mode incremental
   ```

2. **Run the original strategy** (Tuesday rebalance, stop-loss, no-trade months)
   ```bash
   python scripts/strategy_jq.py --project 2026Q1_jq --no-show --save auto
   ```
   Or via CLI:
   ```bash
   python -m quant_mvp run --project 2026Q1_jq --task strategy -- --no-show --save auto
   ```

3. **Or run the plain momentum pipeline**
   ```bash
   python scripts/steps/20_build_rank.py --project 2026Q1_mom
   python scripts/steps/30_bt_rebalance.py --project 2026Q1_mom --no-show --save auto
   python scripts/audit_db.py --project 2026Q1_mom
   python scripts/steps/40_make_report.py --project 2026Q1_mom
   ```

4. **Outputs**
   - Strategy: `artifacts/projects/2026Q1_jq/summary_metrics.csv`, `topn_1_5.png`
   - Momentum pipeline: `artifacts/projects/2026Q1_mom/summary_metrics.csv`, `topn_1_5.png`, `report.md`

---

## Project Structure

```
configs/projects/     Project JSON configs (e.g. 2026Q1_mom.json, 2026Q1_jq.json)
data/
  market.db           SQLite bars (symbol, datetime, freq, open, high, low, close, volume)
  projects/<name>/
    meta/             universe_codes.txt, run_manifest.json, db_coverage_*
    signals/          rank_topK.parquet, rank_candidates.parquet
    features/         Factor parquets (e.g. mom20.parquet)
artifacts/projects/   summary_metrics.csv, topn_1_5.png, report.md
quant_mvp/            Config, db, universe, manifest, ranking, backtest_engine, reporting
scripts/
  strategy_jq.py      Main strategy entry (Tuesday rebalance, stop-loss, no-trade months)
  steps/              10_symbols, 11_update_bars, 20_build_rank, 30_bt_rebalance, 31–34, 40_make_report
  audit_db.py         Database coverage audit
  tools/              Optional utilities
docs/                 Methodology and factor notes
tests/                Unit and smoke tests
dashboard/            Streamlit dashboard (optional)
```

---

## Configuration (Strategy-Relevant Fields)

| Key | Description | Example |
|-----|-------------|---------|
| `stock_num` | Number of names in the portfolio | 6 |
| `no_trade_months` | Months to hold cash (no new buys; clear at month end) | [1, 4] |
| `stoploss_limit` | Sell when price &lt; cost × this | 0.91 |
| `take_profit_ratio` | Sell when price ≥ cost × this | 2.0 |
| `market_stoploss_ratio` | Clear all when index close/open ≤ this | 0.93 |
| `loss_black_days` | Days to exclude a code after stop-loss sell | 20 |
| `min_commission` | Minimum commission per side (currency units) | 5 |
| `commission`, `stamp_duty`, `slippage` | Cost assumptions | e.g. 0.0001, 0.0005, 0.002 |
| `calendar_code` | Benchmark index for market stop-loss | "000001" |

---

## Data Flow and Reproducibility

1. **Universe** → `scripts/steps/10_symbols.py` → `data/projects/<project>/meta/universe_codes.txt`
2. **Bars** → `scripts/steps/11_update_bars.py` → `data/market.db`
3. **Rank** → `scripts/steps/20_build_rank.py` or `scripts/strategy_jq.py` (Tuesday rank) → `signals/rank_topK.parquet`
4. **Backtest** → `scripts/steps/30_bt_rebalance.py` or `scripts/strategy_jq.py` → `artifacts/projects/<project>/summary_metrics.csv`, `topn_1_5.png`
5. **Report** → `scripts/steps/40_make_report.py` → `artifacts/projects/<project>/report.md`

To reproduce a run, keep the project config, `universe_codes.txt`, and (if desired) `run_manifest.json`; re-run the same commands.

**Verify**
```bash
python -m pytest -q
```

---

## Syncing to GitHub

1. Ensure remote is set: `git remote -v` (if missing: `git remote add origin <url>`).
2. Commit and push:
   ```bash
   git add .
   git status
   git commit -m "Your message"
   git push origin main
   ```

---

## License and Disclaimer

This project is for research and education only. It is not investment advice. Use at your own risk.
