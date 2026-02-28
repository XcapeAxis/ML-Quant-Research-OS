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
from quant_mvp.db import db_date_range, upsert_bars
from quant_mvp.manifest import update_run_manifest
from quant_mvp.project import resolve_project_paths
from quant_mvp.universe import load_universe_codes


def _to_yyyymmdd(date_text: str | None) -> str:
    if not date_text:
        return datetime.now().strftime("%Y%m%d")
    text = str(date_text).strip()
    if "-" in text:
        return datetime.strptime(text, "%Y-%m-%d").strftime("%Y%m%d")
    return text


def _fetch_akshare_daily(code: str, start_yyyymmdd: str, end_yyyymmdd: str, freq: str) -> pd.DataFrame:
    try:
        import akshare as ak
    except ImportError as exc:
        raise RuntimeError("akshare is required for bars update. Install requirements first.") from exc

    df = ak.stock_zh_a_hist(
        symbol=str(code).zfill(6),
        period="daily",
        start_date=start_yyyymmdd,
        end_date=end_yyyymmdd,
        adjust="qfq",
    )
    if df is None or df.empty:
        return pd.DataFrame()

    aliases: dict[str, set[str]] = {
        "datetime": {"日期", "date", "datetime", "time"},
        "open": {"开盘", "open"},
        "high": {"最高", "high"},
        "low": {"最低", "low"},
        "close": {"收盘", "close"},
        "volume": {"成交量", "volume"},
    }
    rename_map: dict[str, str] = {}
    for col in df.columns:
        col_text = str(col).strip()
        low = col_text.lower()
        for target, names in aliases.items():
            if col_text in names or low in names:
                rename_map[col] = target
                break

    df = df.rename(columns=rename_map)
    required = {"datetime", "open", "high", "low", "close"}
    if not required.issubset(df.columns):
        return pd.DataFrame()
    if "volume" not in df.columns:
        df["volume"] = 0.0

    out = df[["datetime", "open", "high", "low", "close", "volume"]].copy()
    out["datetime"] = pd.to_datetime(out["datetime"]).dt.strftime("%Y-%m-%d")
    out["symbol"] = str(code).zfill(6)
    out["freq"] = freq
    for col in ["open", "high", "low", "close", "volume"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna(subset=["datetime", "open", "high", "low", "close"])
    return out


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
) -> tuple[str, int, str | None]:
    if mode == "incremental" and last_updated:
        start_dt = datetime.strptime(last_updated, "%Y%m%d") + timedelta(days=1)
        start = start_dt.strftime("%Y%m%d")
    else:
        start = start_date

    if start > end_date:
        return code, 0, last_updated

    bars = _fetch_akshare_daily(code=code, start_yyyymmdd=start, end_yyyymmdd=end_date, freq=freq)
    if bars.empty:
        return code, 0, last_updated

    rows = upsert_bars(db_path=db_path, bars_df=bars)
    return code, rows, end_date


def run_update(
    project: str,
    mode: str,
    freq: str,
    start_date: str,
    end_date: str,
    workers: int,
    max_codes_scan: int,
    db_path: Path,
) -> dict[str, Any]:
    paths = resolve_project_paths(project)
    paths.ensure_dirs()

    codes = load_universe_codes(project)[:max_codes_scan]
    if not codes:
        raise RuntimeError("Universe is empty.")

    registry_path = paths.meta_dir / "bars_registry.json"
    registry = _load_registry(registry_path)

    stats = {"total_codes": len(codes), "updated_codes": 0, "total_rows": 0, "failed_codes": []}

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
                if last:
                    registry[code] = last
            except Exception:
                stats["failed_codes"].append(code)

    _save_registry(registry_path, registry)
    min_date, max_date = db_date_range(db_path, freq=freq)
    update_run_manifest(
        project,
        {
            "bars_update": {
                "mode": mode,
                "start_date": start_date,
                "end_date": end_date,
                "workers": workers,
                "stats": stats,
            },
            "freq": freq,
            "db_path": str(db_path),
            "data_date_range": {"min": min_date, "max": max_date},
        },
    )
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Update bars into SQLite (project-scoped).")
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

    stats = run_update(
        project=args.project,
        mode=args.mode,
        freq=freq,
        start_date=start_date,
        end_date=end_date,
        workers=workers,
        max_codes_scan=max_codes_scan,
        db_path=db_path,
    )
    print(
        f"[update_bars] project={args.project} updated_codes={stats['updated_codes']} "
        f"total_rows={stats['total_rows']} failed={len(stats['failed_codes'])}",
    )


if __name__ == "__main__":
    main()
