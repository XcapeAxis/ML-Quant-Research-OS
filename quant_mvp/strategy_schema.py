from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


WEEKDAY_NAMES = {
    0: "Monday",
    1: "Tuesday",
    2: "Wednesday",
    3: "Thursday",
    4: "Friday",
}


@dataclass(frozen=True)
class LimitUpScreeningSpec:
    """Single source of truth for the audited phase-1 strategy."""

    strategy_id: str = "limit_up_screening"
    version: str = "2026.03"
    market: str = "CN-A"
    supported_frequencies: tuple[str, ...] = ("1d", "1w")
    rebalance_weekday: int = 1
    stock_num: int = 6
    limit_days_window: int = 250
    top_pct_limit_up: float = 0.10
    limit_up_threshold: float = 0.095
    init_pool_size: int = 1000
    min_bars: int = 160
    max_codes_scan: int = 4000
    topk_multiplier: int = 2
    require_positive_volume: bool = True
    min_new_listing_days: int = 375
    stoploss_limit: float = 0.91
    take_profit_ratio: float = 2.0
    market_stoploss_ratio: float = 0.93
    loss_black_days: int = 20
    no_trade_months: tuple[int, ...] = (1, 4)
    min_commission: float = 5.0
    max_drawdown_limit: float = 0.30
    reference_index_code: str = "000001"
    research_hypothesis: str = (
        "Repeated historical limit-up behaviour may surface stocks that are re-accumulating "
        "near a prior breakout origin, but the signal is only research-grade after strict "
        "tradability, leakage, and robustness checks."
    )
    execution_assumption: str = (
        "Signals are formed on the rebalance close and evaluated against next-trading-day "
        "returns; same-day close is used only for end-of-day ranking and tradability filters."
    )

    def validate(self) -> None:
        if self.rebalance_weekday not in WEEKDAY_NAMES:
            raise ValueError("rebalance_weekday must be between 0 (Mon) and 4 (Fri)")
        if self.stock_num <= 0:
            raise ValueError("stock_num must be positive")
        if self.limit_days_window <= 0:
            raise ValueError("limit_days_window must be positive")
        if not 0.0 < self.top_pct_limit_up <= 1.0:
            raise ValueError("top_pct_limit_up must be in (0, 1]")
        if self.limit_up_threshold <= 0:
            raise ValueError("limit_up_threshold must be positive")
        if self.max_drawdown_limit <= 0 or self.max_drawdown_limit >= 1:
            raise ValueError("max_drawdown_limit must be in (0, 1)")

    @property
    def rebalance_weekday_name(self) -> str:
        return WEEKDAY_NAMES[self.rebalance_weekday]

    def to_defaults(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["supported_frequencies"] = list(self.supported_frequencies)
        payload["no_trade_months"] = list(self.no_trade_months)
        return payload


def default_limit_up_spec() -> LimitUpScreeningSpec:
    spec = LimitUpScreeningSpec()
    spec.validate()
    return spec


def strategy_defaults() -> dict[str, Any]:
    return default_limit_up_spec().to_defaults()
