#!/usr/bin/env python3
"""
Original Strategy Implementation - JQ Style

This module implements the original momentum + stop-loss strategy with:
- Tuesday-only rebalancing
- Stop-loss at 0.91 (~9% loss)
- Take-profit at 2.0x (100% gain)
- Market stop-loss at 0.93 (index close/open <= 0.93)
- No-trade months: January and April (hold cash)
- 20-day blacklist after stop-loss

All comments and documentation are in English as per project requirements.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from quant_mvp.backtest_engine import (
    BacktestConfig,
    StoplossConfig,
    run_rebalance_backtest_with_stoploss,
    summarize_equity,
)
from quant_mvp.db import load_close_volume_panel, load_ohlcv_panel, list_db_codes
from quant_mvp.project import resolve_project_paths
from quant_mvp.selection import (
    SelectionConfig,
    build_jq_selection,
    rank_targets_jq,
)


# Default configuration matching the original strategy
DEFAULT_CONFIG = {
    "stock_num": 6,
    "rebalance_weekday": 1,  # Tuesday
    "lookback": 60,
    "topk_multiplier": 2,
    "min_bars": 20,
    "max_codes_scan": 1000,
    "require_positive_volume": True,
    "stoploss_limit": 0.91,  # ~9% loss stop-loss
    "take_profit_ratio": 2.0,  # 100% gain take-profit
    "market_stoploss_ratio": 0.93,  # Market trend stop-loss
    "loss_black_days": 20,
    "no_trade_months": [1, 4],  # January and April
    "cash": 1000000.0,
    "commission": 0.0001,
    "stamp_duty": 0.0005,
    "slippage": 0.002,
    "min_commission": 5.0,
    "risk_free_rate": 0.03,
    "benchmark_code": "399101",  # Shenzhen Component Index
}


def load_strategy_config(project_dir: Path, overrides: dict | None = None) -> dict:
    """Load strategy configuration with optional overrides.

    Args:
        project_dir: Project directory path
        overrides: Optional configuration overrides

    Returns:
        Merged configuration dictionary
    """
    config = DEFAULT_CONFIG.copy()

    # Try to load from project config file
    config_file = project_dir / "config.json"
    if config_file.exists():
        with open(config_file, encoding="utf-8") as f:
            file_config = json.load(f)
            config.update(file_config)

    # Apply overrides
    if overrides:
        config.update(overrides)

    return config


def save_artifacts(
    project_dir: Path,
    rank_df: pd.DataFrame,
    equity: pd.Series,
    metrics: dict,
    config: dict,
) -> None:
    """Save strategy artifacts to project directory.

    Args:
        project_dir: Project directory path
        rank_df: Rank DataFrame
        equity: Equity curve series
        metrics: Performance metrics dictionary
        config: Strategy configuration
    """
    artifacts_dir = project_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    # Save rank DataFrame
    rank_file = artifacts_dir / "rank_jq.parquet"
    rank_df.to_parquet(rank_file, index=False)
    print(f"Saved rank data to {rank_file}")

    # Save equity curve
    equity_file = artifacts_dir / "equity_jq.csv"
    equity.to_csv(equity_file)
    print(f"Saved equity curve to {equity_file}")

    # Save metrics
    metrics_file = artifacts_dir / "metrics_jq.json"
    with open(metrics_file, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, default=str)
    print(f"Saved metrics to {metrics_file}")

    # Save config
    config_file = artifacts_dir / "config_jq.json"
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    print(f"Saved config to {config_file}")


def run_strategy(
    project_name: str,
    data_dir: Path | None = None,
    overrides: dict | None = None,
) -> dict:
    """Run the complete strategy pipeline.

    Args:
        project_name: Name of the project
        data_dir: Optional data directory override
        overrides: Optional configuration overrides

    Returns:
        Dictionary containing results and metrics
    """
    print(f"Running JQ Strategy for project: {project_name}")

    # Resolve paths
    paths = resolve_project_paths(project_name, data_dir)
    project_dir = paths.project_data_dir
    db_path = paths.db_path

    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    # Load configuration
    config = load_strategy_config(project_dir, overrides)
    print(f"Configuration: {json.dumps(config, indent=2)}")

    # Get universe codes from database
    all_codes = sorted(list_db_codes(db_path, config.get("freq", "1d")))
    print(f"Found {len(all_codes)} codes in database")

    if len(all_codes) < config["stock_num"] * config["topk_multiplier"]:
        raise ValueError(f"Not enough codes in universe. Need at least {config['stock_num'] * config['topk_multiplier']}")

    # Build selection configuration
    sel_cfg = SelectionConfig(
        stock_num=config["stock_num"],
        rebalance_weekday=config["rebalance_weekday"],
        lookback=config["lookback"],
        topk_multiplier=config["topk_multiplier"],
        min_bars=config["min_bars"],
        max_codes_scan=config["max_codes_scan"],
        require_positive_volume=config["require_positive_volume"],
    )

    # Run selection
    print("Building stock selection...")
    selection = build_jq_selection(
        db_path=db_path,
        freq=config.get("freq", "1d"),
        universe_codes=all_codes,
        cfg=sel_cfg,
    )
    print(f"Generated {len(selection.rank_df)} rank entries across {len(selection.rebalance_dates)} rebalance dates")

    # Load price data for backtest
    print("Loading price data for backtest...")
    used_codes = selection.used_codes[:config["max_codes_scan"]]
    ohlcv = load_ohlcv_panel(
        db_path=db_path,
        freq=config.get("freq", "1d"),
        codes=used_codes,
    )
    close_panel = ohlcv["close"]
    open_panel = ohlcv["open"]

    # Prepare targets
    targets_by_date = rank_targets_jq(selection.rank_df, config["stock_num"])

    # Build backtest configurations
    bt_cfg = BacktestConfig(
        cash=config["cash"],
        commission=config["commission"],
        stamp_duty=config["stamp_duty"],
        slippage=config["slippage"],
        risk_free_rate=config["risk_free_rate"],
        min_commission=config["min_commission"],
    )

    stop_cfg = StoplossConfig(
        stoploss_limit=config["stoploss_limit"],
        take_profit_ratio=config["take_profit_ratio"],
        market_stoploss_ratio=config["market_stoploss_ratio"],
        loss_black_days=config["loss_black_days"],
        no_trade_months=config["no_trade_months"],
        enable_stoploss=True,
        enable_take_profit=True,
        enable_market_stoploss=True,
    )

    # Load benchmark data for market stop-loss (if available)
    benchmark_close = None
    benchmark_open = None
    try:
        bench_ohlcv = load_ohlcv_panel(
            db_path=db_path,
            freq=config.get("freq", "1d"),
            codes=[config["benchmark_code"]],
        )
        benchmark_close = bench_ohlcv["close"][config["benchmark_code"]]
        benchmark_open = bench_ohlcv["open"][config["benchmark_code"]]
        print(f"Loaded benchmark data for {config['benchmark_code']}")
    except Exception as e:
        print(f"Warning: Could not load benchmark data: {e}")
        print("Market stop-loss will be disabled")
        stop_cfg.enable_market_stoploss = False

    # Run backtest with stop-loss
    print("Running backtest with stop-loss...")
    equity = run_rebalance_backtest_with_stoploss(
        close_panel=close_panel,
        open_panel=open_panel,
        targets_by_date=targets_by_date,
        cfg=bt_cfg,
        stop_cfg=stop_cfg,
        benchmark_close=benchmark_close,
        benchmark_open=benchmark_open,
    )

    # Calculate metrics
    metrics = summarize_equity(equity, bt_cfg)
    print(f"\nBacktest Results:")
    print(f"  Total Return: {metrics['total_return']:.2%}")
    print(f"  Annualized Return: {metrics['annualized_return']:.2%}")
    print(f"  Annualized Volatility: {metrics['annualized_volatility']:.2%}")
    print(f"  Max Drawdown: {metrics['max_drawdown']:.2%}")
    print(f"  Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
    print(f"  Final Equity: {metrics['final_equity']:,.2f}")

    # Save artifacts
    save_artifacts(project_dir, selection.rank_df, equity, metrics, config)

    return {
        "rank_df": selection.rank_df,
        "equity": equity,
        "metrics": metrics,
        "config": config,
    }


def main():
    """Main entry point for the strategy script."""
    parser = argparse.ArgumentParser(
        description="Run JQ-style momentum + stop-loss strategy",
    )
    parser.add_argument(
        "--project",
        type=str,
        required=True,
        help="Project name (e.g., 2026Q1_jq)",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default=None,
        help="Data directory override",
    )
    parser.add_argument(
        "--stock-num",
        type=int,
        default=None,
        help="Number of stocks to hold",
    )
    parser.add_argument(
        "--cash",
        type=float,
        default=None,
        help="Initial cash amount",
    )

    args = parser.parse_args()

    # Build overrides from command line
    overrides = {}
    if args.stock_num is not None:
        overrides["stock_num"] = args.stock_num
    if args.cash is not None:
        overrides["cash"] = args.cash

    data_dir = Path(args.data_dir) if args.data_dir else None

    try:
        results = run_strategy(
            project_name=args.project,
            data_dir=data_dir,
            overrides=overrides if overrides else None,
        )
        print("\nStrategy completed successfully!")
        return 0
    except Exception as e:
        print(f"\nStrategy failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
