from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ExecutionMode(str, Enum):
    serial = "serial"
    parallel = "parallel"


class PipelineName(str, Enum):
    data_refresh = "data_refresh"
    signal_build = "signal_build"
    backtest_only = "backtest_only"
    full_analysis_pack = "full_analysis_pack"


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelling = "cancelling"
    cancelled = "cancelled"


class BaselinesPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    benchmark_code: str | None = None
    enable_equal_weight: bool | None = None
    random_trials: int | None = None
    random_seed: int | None = None


class CostSweepPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    commission_grid: list[float] | None = None
    slippage_grid: list[float] | None = None


class WalkWindowPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str | None = None
    start: str | None = None
    end: str | None = None


class WalkForwardPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    windows: list[WalkWindowPayload] | None = None


class ReportPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    format: str | None = None
    include_sections: list[str] | None = None


class TradabilityPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    require_positive_volume: bool | None = None
    min_volume: float | None = None


class RiskOverlayPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    enabled: bool | None = None
    vol_target: float | None = None
    rolling_days: int | None = None
    max_leverage: float | None = None


class DataQualityPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    enabled: bool | None = None
    auto_clean_after_update: bool | None = None
    source_table: str | None = None
    clean_table: str | None = None
    issues_table: str | None = None
    default_data_mode: str | None = None
    drop_zero_or_negative_volume: bool | None = None
    repair_ohlc_envelope: bool | None = None
    warn_abs_daily_return: float | None = None
    hard_abs_daily_return: float | None = None
    warn_open_gap: float | None = None
    hard_open_gap: float | None = None
    warn_intraday_range: float | None = None
    hard_intraday_range: float | None = None
    warn_volume_spike_mult: float | None = None


class ProjectConfigPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    db_path: str | None = None
    freq: str | None = None
    strategy_mode: str | None = None
    lookback: int | None = None
    rebalance_every: int | None = None
    topk: int | None = None
    topn_max: int | None = None
    min_bars: int | None = None
    max_codes_scan: int | None = None
    cash: float | None = None
    commission: float | None = None
    stamp_duty: float | None = None
    slippage: float | None = None
    calendar_code: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    universe_size_target: int | None = None
    risk_free_rate: float | None = None
    stock_num: int | None = None
    limit_days_window: int | None = None
    top_pct_limit_up: float | None = None
    limit_up_threshold: float | None = None
    init_pool_size: int | None = None
    rebalance_weekday: int | None = None
    stoploss_limit: float | None = None
    take_profit_ratio: float | None = None
    market_stoploss_ratio: float | None = None
    loss_black_days: int | None = None
    no_trade_months: list[int] | None = None
    min_commission: float | None = None
    baselines: BaselinesPayload | None = None
    cost_sweep: CostSweepPayload | None = None
    walk_forward: WalkForwardPayload | None = None
    report: ReportPayload | None = None
    tradability: TradabilityPayload | None = None
    risk_overlay: RiskOverlayPayload | None = None
    data_quality: DataQualityPayload | None = None


class JobCreateRequest(BaseModel):
    project: str
    pipeline: PipelineName
    execution_mode: ExecutionMode = Field(default=ExecutionMode.parallel)
