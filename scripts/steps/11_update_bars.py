from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quant_mvp.config import load_config
from quant_mvp.data.cleaning import clean_project_bars
from quant_mvp.data.contracts import ProviderFetchRequest
from quant_mvp.data.providers import AkshareDailyProvider
from quant_mvp.data_quality import clean_table_ready
from quant_mvp.db import db_date_range, list_db_codes, upsert_bars
from quant_mvp.manifest import update_run_manifest
from quant_mvp.networking import NetworkRuntimeConfig
from quant_mvp.project import resolve_project_paths
from quant_mvp.universe import load_universe_codes


def _to_yyyymmdd(date_text: str | None) -> str:
    if not date_text:
        return datetime.now().strftime("%Y%m%d")
    text = str(date_text).strip()
    if "-" in text:
        return datetime.strptime(text, "%Y-%m-%d").strftime("%Y%m%d")
    return text


def _friendly_network_error(exc: Exception, network_cfg: NetworkRuntimeConfig) -> str:
    text = str(exc)
    lower = text.lower()
    if "configured endpoints" in lower:
        return text
    if network_cfg.ca_bundle_path and not network_cfg.ca_bundle_exists():
        return f"Missing CA bundle: {network_cfg.ca_bundle_path}"
    if "ssl" in lower or "certificate" in lower or "cert" in lower:
        return "TLS/CA validation failed while requesting AKShare data."
    if "proxy" in lower or "407" in lower:
        return "Proxy connection failed while requesting AKShare data."
    if "timed out" in lower or "timeout" in lower:
        return "AKShare history request timed out."
    return f"AKShare history request failed: {text}"


def _fetch_akshare_daily(
    code: str,
    start_yyyymmdd: str,
    end_yyyymmdd: str,
    freq: str,
    *,
    timeout_seconds: float,
) -> pd.DataFrame:
    provider = AkshareDailyProvider(timeout_seconds=timeout_seconds)
    return provider.fetch_daily_bars(
        ProviderFetchRequest(
            symbol=str(code).zfill(6),
            start_date=start_yyyymmdd,
            end_date=end_yyyymmdd,
            frequency=freq,
        ),
    )


def _load_registry(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _save_registry(path: Path, payload: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def _update_one(
    code: str,
    mode: str,
    start_date: str,
    end_date: str,
    freq: str,
    db_path: Path,
    last_updated: str | None,
    *,
    timeout_seconds: float,
) -> tuple[str, int, str | None]:
    if mode == "incremental" and last_updated:
        start_dt = datetime.strptime(last_updated, "%Y%m%d") + timedelta(days=1)
        start = start_dt.strftime("%Y%m%d")
    else:
        start = start_date

    if start > end_date:
        return code, 0, last_updated

    bars = _fetch_akshare_daily(
        code=code,
        start_yyyymmdd=start,
        end_yyyymmdd=end_date,
        freq=freq,
        timeout_seconds=timeout_seconds,
    )
    if bars.empty:
        return code, 0, last_updated

    rows = upsert_bars(db_path=db_path, bars_df=bars)
    return code, rows, end_date


def _prepare_network_runtime() -> NetworkRuntimeConfig:
    network_cfg = NetworkRuntimeConfig.from_sources()
    issues = network_cfg.validation_issues()
    if issues:
        raise RuntimeError(f"Invalid network configuration: {issues[0]}")
    network_cfg.apply_to_process()
    return network_cfg


def run_update(
    project: str,
    mode: str,
    freq: str,
    start_date: str,
    end_date: str,
    workers: int,
    max_codes_scan: int,
    db_path: Path,
    data_quality_cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    network_cfg = _prepare_network_runtime()
    paths = resolve_project_paths(project)
    paths.ensure_dirs()

    codes = load_universe_codes(project)[:max_codes_scan]
    if not codes:
        raise RuntimeError("Universe is empty; run the symbols step before updating bars.")

    registry_path = paths.meta_dir / "bars_registry.json"
    registry = _load_registry(registry_path)
    stats = {
        "total_codes": len(codes),
        "updated_codes": 0,
        "total_rows": 0,
        "failed_codes": [],
        "updated_code_list": [],
        "failure_reason_counts": {},
        "sample_failures": [],
    }

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {
            pool.submit(
                _update_one,
                code,
                mode,
                start_date,
                end_date,
                freq,
                db_path,
                registry.get(code),
                timeout_seconds=network_cfg.read_timeout_seconds,
            ): code
            for code in codes
        }
        for future in as_completed(futures):
            code = futures[future]
            try:
                _, rows, last = future.result()
                stats["total_rows"] += rows
                if rows > 0:
                    stats["updated_codes"] += 1
                    stats["updated_code_list"].append(code)
                if last:
                    registry[code] = last
            except Exception as exc:
                stats["failed_codes"].append(code)
                reason = _friendly_network_error(exc, network_cfg)
                stats["failure_reason_counts"][reason] = int(stats["failure_reason_counts"].get(reason, 0)) + 1
                if len(stats["sample_failures"]) < 5:
                    stats["sample_failures"].append(f"{code}: {reason}")

    _save_registry(registry_path, registry)

    quality_stats = None
    if data_quality_cfg and data_quality_cfg.get("enabled", True) and data_quality_cfg.get("auto_clean_after_update", True):
        target_codes = sorted(set(stats["updated_code_list"]))
        bootstrap_all = False
        if not clean_table_ready(
            db_path,
            freq=freq,
            clean_table=str(data_quality_cfg.get("clean_table", "bars_clean")),
        ):
            target_codes = sorted(list_db_codes(db_path, freq=freq, data_mode="raw"))
            bootstrap_all = True
        if target_codes:
            quality_stats = clean_project_bars(
                project=project,
                db_path=db_path,
                freq=freq,
                codes=target_codes,
                meta_dir=paths.meta_dir,
                data_quality_cfg=data_quality_cfg,
                full_refresh=bootstrap_all,
            )

    min_date, max_date = db_date_range(db_path, freq=freq, data_mode="raw")
    updates: dict[str, Any] = {
        "bars_update": {
            "mode": mode,
            "start_date": start_date,
            "end_date": end_date,
            "workers": workers,
            "stats": {
                "total_codes": stats["total_codes"],
                "updated_codes": stats["updated_codes"],
                "total_rows": stats["total_rows"],
                "failed_codes": stats["failed_codes"],
                "failure_reason_counts": stats["failure_reason_counts"],
                "sample_failures": stats["sample_failures"],
            },
        },
        "freq": freq,
        "db_path": str(db_path),
        "data_provider": {
            "provider": "akshare",
            "normalized_symbol_format": "six_digit_a_share",
        },
        "data_date_range": {"min": min_date, "max": max_date},
    }
    if quality_stats is not None:
        updates["data_quality"] = {
            "source_table": quality_stats["source_table"],
            "clean_table": quality_stats["clean_table"],
            "updated_codes": len(quality_stats["updated_codes"]),
            "scanned_rows": quality_stats["scanned_rows"],
            "kept_rows": quality_stats["kept_rows"],
            "dropped_rows": quality_stats["dropped_rows"],
            "repaired_rows": quality_stats["repaired_rows"],
            "warned_rows": quality_stats["warned_rows"],
            "issue_counts_by_code": quality_stats["issue_counts_by_code"],
            "issue_counts_by_type": quality_stats["issue_counts_by_type"],
            "summary_path": quality_stats.get("summary_path", ""),
            "by_symbol_path": quality_stats.get("by_symbol_path", ""),
        }
    update_run_manifest(project, updates)
    if quality_stats is not None:
        stats["data_quality"] = quality_stats
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Update project bars into SQLite.")
    parser.add_argument("--project", type=str, default="2026Q1_limit_up")
    parser.add_argument("--config", type=Path, default=None, help="Optional config path override.")
    parser.add_argument("--mode", type=str, default="incremental", choices=["incremental", "backfill"])
    parser.add_argument("--freq", type=str, default=None)
    parser.add_argument("--start-date", type=str, default=None)
    parser.add_argument("--end-date", type=str, default=None)
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--max-codes-scan", type=int, default=None)
    args = parser.parse_args()

    cfg, _ = load_config(args.project, config_path=args.config)
    freq = args.freq or cfg["freq"]
    start_date = _to_yyyymmdd(args.start_date or cfg.get("start_date"))
    end_date = _to_yyyymmdd(args.end_date or cfg.get("end_date"))
    db_path = Path(cfg["db_path"])
    workers = int(args.workers if args.workers is not None else 4)
    max_codes_scan = int(args.max_codes_scan if args.max_codes_scan is not None else cfg["max_codes_scan"])

    try:
        stats = run_update(
            project=args.project,
            mode=args.mode,
            freq=freq,
            start_date=start_date,
            end_date=end_date,
            workers=workers,
            max_codes_scan=max_codes_scan,
            db_path=db_path,
            data_quality_cfg=cfg.get("data_quality"),
        )
    except Exception as exc:
        raise RuntimeError(_friendly_network_error(exc, NetworkRuntimeConfig.from_sources())) from exc

    print(
        f"[update_bars] project={args.project} updated_codes={stats['updated_codes']} "
        f"total_rows={stats['total_rows']} failed={len(stats['failed_codes'])}",
    )


if __name__ == "__main__":
    main()
