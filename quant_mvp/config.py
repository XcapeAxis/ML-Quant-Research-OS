from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .config_schema import ProjectConfig
from .project import ProjectPaths, resolve_project_paths


DEFAULT_CONFIG: dict[str, Any] = ProjectConfig.default().to_dict()


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
