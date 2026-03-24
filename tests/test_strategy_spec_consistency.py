from __future__ import annotations

import json

from quant_mvp.config import DEFAULT_CONFIG
from quant_mvp.research_core import resolve_limit_up_config
from quant_mvp.strategy_schema import default_limit_up_spec


def test_strategy_spec_consistency(limit_up_project) -> None:
    spec = default_limit_up_spec()
    cfg = json.loads(limit_up_project["config_path"].read_text(encoding="utf-8"))
    resolved = resolve_limit_up_config(cfg)

    assert spec.limit_days_window == 250
    assert DEFAULT_CONFIG["limit_days_window"] == spec.limit_days_window
    assert DEFAULT_CONFIG["rebalance_weekday"] == spec.rebalance_weekday
    assert cfg["limit_days_window"] == 60
    assert resolved.limit_days_window == 60
    assert resolved.rebalance_weekday == cfg["rebalance_weekday"]
    assert resolved.top_pct_limit_up == cfg["top_pct_limit_up"]
