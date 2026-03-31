from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from typing import Any

from .strategy_schema import default_limit_up_spec


def _to_dict(value: Any) -> Any:
    if is_dataclass(value):
        return {
            item.name: _to_dict(getattr(value, item.name))
            for item in fields(value)
        }
    if isinstance(value, tuple):
        return [_to_dict(item) for item in value]
    if isinstance(value, list):
        return [_to_dict(item) for item in value]
    if isinstance(value, dict):
        return {key: _to_dict(item) for key, item in value.items()}
    return value


@dataclass(frozen=True)
class BaselineConfig:
    benchmark_code: str = "000001"
    enable_equal_weight: bool = True
    random_trials: int = 200
    random_seed: int = 42


@dataclass(frozen=True)
class CostSweepConfig:
    commission_grid: tuple[float, ...] = (0.0001, 0.0002, 0.0003, 0.0005, 0.001)
    slippage_grid: tuple[float, ...] = (0.0005, 0.001, 0.002)


@dataclass(frozen=True)
class WalkForwardWindow:
    name: str
    start: str
    end: str


@dataclass(frozen=True)
class WalkForwardConfig:
    windows: tuple[WalkForwardWindow, ...] = (
        WalkForwardWindow(name="2016-2019", start="2016-01-01", end="2019-12-31"),
        WalkForwardWindow(name="2020-2022", start="2020-01-01", end="2022-12-31"),
        WalkForwardWindow(name="2023-2025", start="2023-01-01", end="2025-12-31"),
    )


@dataclass(frozen=True)
class ReportConfig:
    format: str = "md"
    include_sections: tuple[str, ...] = (
        "overview",
        "metrics",
        "coverage",
        "baselines",
        "cost",
        "walk_forward",
        "promotion_gate",
    )


@dataclass(frozen=True)
class TradabilityConfig:
    require_positive_volume: bool = True
    min_volume: float = 0.0
    exclude_limit_locked: bool = True
    exclude_suspended: bool = True


@dataclass(frozen=True)
class RiskOverlayConfig:
    enabled: bool = False
    vol_target: float = 0.18
    rolling_days: int = 20
    max_leverage: float = 1.0


@dataclass(frozen=True)
class DataQualityConfig:
    enabled: bool = True
    auto_clean_after_update: bool = True
    source_table: str = "bars"
    clean_table: str = "bars_clean"
    issues_table: str = "bar_issues"
    default_data_mode: str = "auto"
    drop_zero_or_negative_volume: bool = True
    repair_ohlc_envelope: bool = True
    warn_abs_daily_return: float = 0.20
    hard_abs_daily_return: float = 0.30
    warn_open_gap: float = 0.20
    hard_open_gap: float = 0.30
    warn_intraday_range: float = 0.25
    hard_intraday_range: float = 0.35
    warn_volume_spike_mult: float = 50.0


@dataclass(frozen=True)
class DataProviderConfig:
    provider: str = "akshare"
    market: str = "CN-A"
    raw_layer: str = "raw"
    cleaned_layer: str = "cleaned"
    validated_layer: str = "validated"
    symbol_format: str = "six_digit_a_share"


@dataclass(frozen=True)
class ResearchValidationConfig:
    enabled: bool = True
    forward_horizon_days: int = 1
    max_drawdown_limit: float = 0.30
    min_walk_forward_windows_alive: int = 2
    max_cost_sensitivity_drawdown_delta: float = 0.10
    min_cost_sensitivity_return_ratio: float = 0.50
    require_economic_rationale: bool = True
    require_parameter_robustness: bool = True
    parameter_perturbations: tuple[dict[str, float], ...] = (
        {"limit_days_window": -0.20},
        {"limit_days_window": 0.20},
        {"top_pct_limit_up": -0.20},
        {"top_pct_limit_up": 0.20},
    )


@dataclass(frozen=True)
class MemoryWritebackConfig:
    enabled: bool = True
    append_only_experiment_ledger: bool = True
    project_state_file: str = "PROJECT_STATE.md"
    research_memory_file: str = "RESEARCH_MEMORY.md"
    hypothesis_queue_file: str = "HYPOTHESIS_QUEUE.md"
    postmortems_file: str = "POSTMORTEMS.md"
    experiment_ledger_file: str = "EXPERIMENT_LEDGER.jsonl"


@dataclass(frozen=True)
class AgentConfig:
    default_backend: str = "dry_run"
    allow_live_execution: bool = False
    max_cycles_per_run: int = 1
    require_promotion_gate: bool = True
    default_tool_allowlist_path: str = "configs/tool_allowlist.yaml"


@dataclass(frozen=True)
class FactorModelConfig:
    profile: str = "f1_elasticnet_v1"
    feature_names: tuple[str, ...] = (
        "mom20",
        "rev5",
        "vol20",
        "range",
        "vol_surge",
        "ma_gap",
        "adv20",
        "amihud20",
    )
    label_horizon_days: int = 5
    refit_frequency: str = "monthly"
    training_window_days: int = 756
    min_train_days: int = 504
    winsorize_quantile: float = 0.01
    standardization: str = "cross_sectional_zscore"
    alpha: float = 0.001
    l1_ratio: float = 0.2
    max_iter: int = 5000


@dataclass(frozen=True)
class RegimeControlConfig:
    profile: str = "r1_predictive_error_overlay_v1"
    ic_window_rebalances: int = 6
    shortfall_window_rebalances: int = 6
    min_history_rebalances: int = 6
    caution_ic_threshold: float = 0.00
    defensive_ic_threshold: float = -0.03
    caution_shortfall_threshold: float = -0.005
    defensive_shortfall_threshold: float = -0.015
    caution_exposure: float = 0.5
    defensive_exposure: float = 0.25
    cooldown_rebalances: int = 2


@dataclass(frozen=True)
class DeepFactorModelConfig:
    profile: str = "f2_structured_latent_factor_v1"
    base_feature_names: tuple[str, ...] = (
        "mom20",
        "rev5",
        "vol20",
        "range",
        "vol_surge",
        "ma_gap",
        "adv20",
        "amihud20",
    )
    group_features: bool = True
    latent_dim: int = 4
    hidden_sizes: tuple[int, ...] = (12, 4)
    activation: str = "relu"
    alpha: float = 0.0001
    learning_rate_init: float = 0.001
    max_iter: int = 300
    early_stopping: bool = True
    validation_fraction: float = 0.1
    random_state: int = 42
    label_horizon_days: int = 5
    refit_frequency: str = "monthly"
    training_window_days: int = 756
    min_train_days: int = 504
    winsorize_quantile: float = 0.01
    standardization: str = "cross_sectional_zscore"


@dataclass(frozen=True)
class ProjectConfig:
    db_path: str | None = None
    freq: str = "1d"
    strategy_mode: str = "momentum"
    lookback: int = 20
    rebalance_every: int = 5
    topk: int = 6
    topn_max: int = 6
    min_bars: int = 160
    max_codes_scan: int = 4000
    cash: float = 1_000_000.0
    commission: float = 0.0001
    stamp_duty: float = 0.0005
    slippage: float = 0.002
    calendar_code: str = "000001"
    start_date: str = "2016-01-01"
    end_date: str | None = None
    universe_size_target: int | None = None
    risk_free_rate: float = 0.03
    stock_num: int = field(default_factory=lambda: default_limit_up_spec().stock_num)
    limit_days_window: int = field(default_factory=lambda: default_limit_up_spec().limit_days_window)
    top_pct_limit_up: float = field(default_factory=lambda: default_limit_up_spec().top_pct_limit_up)
    limit_up_threshold: float = field(default_factory=lambda: default_limit_up_spec().limit_up_threshold)
    init_pool_size: int = field(default_factory=lambda: default_limit_up_spec().init_pool_size)
    rebalance_weekday: int = field(default_factory=lambda: default_limit_up_spec().rebalance_weekday)
    topk_multiplier: int = field(default_factory=lambda: default_limit_up_spec().topk_multiplier)
    stoploss_limit: float = field(default_factory=lambda: default_limit_up_spec().stoploss_limit)
    take_profit_ratio: float = field(default_factory=lambda: default_limit_up_spec().take_profit_ratio)
    market_stoploss_ratio: float = field(default_factory=lambda: default_limit_up_spec().market_stoploss_ratio)
    loss_black_days: int = field(default_factory=lambda: default_limit_up_spec().loss_black_days)
    no_trade_months: tuple[int, ...] = field(default_factory=lambda: default_limit_up_spec().no_trade_months)
    min_commission: float = field(default_factory=lambda: default_limit_up_spec().min_commission)
    baselines: BaselineConfig = field(default_factory=BaselineConfig)
    cost_sweep: CostSweepConfig = field(default_factory=CostSweepConfig)
    walk_forward: WalkForwardConfig = field(default_factory=WalkForwardConfig)
    report: ReportConfig = field(default_factory=ReportConfig)
    tradability: TradabilityConfig = field(default_factory=TradabilityConfig)
    risk_overlay: RiskOverlayConfig = field(default_factory=RiskOverlayConfig)
    data_quality: DataQualityConfig = field(default_factory=DataQualityConfig)
    data_provider: DataProviderConfig = field(default_factory=DataProviderConfig)
    research_validation: ResearchValidationConfig = field(default_factory=ResearchValidationConfig)
    memory_writeback: MemoryWritebackConfig = field(default_factory=MemoryWritebackConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    factor_model: FactorModelConfig = field(default_factory=FactorModelConfig)
    regime_control: RegimeControlConfig = field(default_factory=RegimeControlConfig)
    deep_factor_model: DeepFactorModelConfig = field(default_factory=DeepFactorModelConfig)

    @classmethod
    def default(cls) -> "ProjectConfig":
        return cls()

    def to_dict(self) -> dict[str, Any]:
        payload = _to_dict(self)
        if isinstance(payload.get("no_trade_months"), list):
            payload["no_trade_months"] = [int(item) for item in payload["no_trade_months"]]
        return payload
