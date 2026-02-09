from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from .project import resolve_project_paths


def _git_commit(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    for encoding in ("utf-8", "utf-8-sig"):
        try:
            with open(path, "r", encoding=encoding) as handle:
                return json.load(handle)
        except Exception:
            continue
    return {}


def _dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def _merge(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def candidate_count_stats(path: Path) -> dict[str, float] | None:
    if not path.exists():
        return None
    df = pd.read_csv(path)
    if df.empty or "candidate_count" not in df.columns:
        return None
    series = pd.to_numeric(df["candidate_count"], errors="coerce").dropna()
    if series.empty:
        return None
    return {
        "min": float(series.min()),
        "median": float(series.median()),
        "p10": float(series.quantile(0.1)),
        "mean": float(series.mean()),
        "max": float(series.max()),
    }


def update_run_manifest(project: str, updates: dict[str, Any] | None = None) -> Path:
    paths = resolve_project_paths(project)
    paths.ensure_dirs()
    manifest_path = paths.meta_dir / "run_manifest.json"
    payload = _load_json(manifest_path)

    base = {
        "project": project,
        "generated_at": datetime.now().isoformat(),
        "git_commit": _git_commit(paths.root),
        "paths": {
            "signals_dir": str(paths.signals_dir),
            "features_dir": str(paths.features_dir),
            "meta_dir": str(paths.meta_dir),
            "artifacts_dir": str(paths.artifacts_dir),
            "db_path": str(paths.db_path),
        },
    }
    payload = _merge(payload, base)

    if paths.universe_path.exists():
        with open(paths.universe_path, "r", encoding="utf-8") as handle:
            universe = [line.strip() for line in handle if line.strip()]
        payload["universe_size"] = len(universe)
        payload["universe_path"] = str(paths.universe_path)

    auto_candidate_stats = candidate_count_stats(paths.meta_dir / "rank_candidate_count.csv")
    if auto_candidate_stats and "candidate_count_stats" not in payload:
        payload["candidate_count_stats"] = auto_candidate_stats

    if updates:
        payload = _merge(payload, updates)

    _dump_json(manifest_path, payload)
    return manifest_path
