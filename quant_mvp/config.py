from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .project import ProjectPaths, resolve_project_paths


DEFAULT_CONFIG: dict[str, Any] = {
    "db_path": None,
    "freq": "1d",
    "lookback": 20,
    "rebalance_every": 5,
    "topk": 5,
    "topn_max": 5,
    "min_bars": 160,
    "max_codes_scan": 4000,
    "cash": 1_000_000.0,
    "commission": 0.0003,
    "stamp_duty": 0.001,
    "slippage": 0.0005,
    "calendar_code": "000001",
    "start_date": "2016-01-01",
    "end_date": None,
    "universe_size_target": None,
    "risk_free_rate": 0.03,
    "baselines": {
        "benchmark_code": "000001",
        "enable_equal_weight": True,
        "random_trials": 200,
        "random_seed": 42,
    },
    "cost_sweep": {
        "commission_grid": [0.0001, 0.0002, 0.0003, 0.0005, 0.001],
        "slippage_grid": [0.0001, 0.0003, 0.0005, 0.001, 0.002],
    },
    "walk_forward": {
        "windows": [
            {"name": "2016-2019", "start": "2016-01-01", "end": "2019-12-31"},
            {"name": "2020-2022", "start": "2020-01-01", "end": "2022-12-31"},
            {"name": "2023-2025", "start": "2023-01-01", "end": "2025-12-31"},
        ],
    },
    "report": {
        "format": "md",
        "include_sections": ["overview", "metrics", "coverage", "baselines", "cost", "walk_forward"],
    },
    "tradability": {
        "require_positive_volume": False,
        "min_volume": 0,
    },
    "risk_overlay": {
        "enabled": False,
        "vol_target": 0.18,
        "rolling_days": 20,
        "max_leverage": 1.0,
    },
}


def _deep_merge(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_json(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _strip_none(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in payload.items():
        if value is None:
            continue
        if isinstance(value, dict):
            nested = _strip_none(value)
            if nested:
                out[key] = nested
        else:
            out[key] = value
    return out


def load_config(
    project: str,
    config_path: Path | None = None,
    overrides: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], ProjectPaths]:
    paths = resolve_project_paths(project)
    cfg_path = config_path or paths.config_path
    if not cfg_path.exists():
        raise FileNotFoundError(f"Project config not found: {cfg_path}")
    file_config = _load_json(cfg_path)
    cfg = _deep_merge(DEFAULT_CONFIG, file_config)
    if overrides:
        clean_overrides = _strip_none(overrides)
        cfg = _deep_merge(cfg, clean_overrides)
    if cfg.get("db_path") in (None, ""):
        cfg["db_path"] = str(paths.db_path)
    return cfg, paths
