from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

from .db import (
    CLEAN_BARS_TABLE,
    ISSUES_TABLE,
    RAW_BARS_TABLE,
    delete_bar_issues,
    delete_bars,
    ensure_bar_issues_table,
    ensure_bars_table,
    get_conn,
    list_db_codes,
    table_exists,
    upsert_bar_issues,
    upsert_bars,
)


DEFAULT_RULES: dict[str, Any] = {
    "enabled": True,
    "auto_clean_after_update": True,
    "source_table": RAW_BARS_TABLE,
    "clean_table": CLEAN_BARS_TABLE,
    "issues_table": ISSUES_TABLE,
    "default_data_mode": "auto",
    "drop_zero_or_negative_volume": True,
    "repair_ohlc_envelope": True,
    "warn_abs_daily_return": 0.20,
    "hard_abs_daily_return": 0.30,
    "warn_open_gap": 0.20,
    "hard_open_gap": 0.30,
    "warn_intraday_range": 0.25,
    "hard_intraday_range": 0.35,
    "warn_volume_spike_mult": 50.0,
}


def _merge_rules(rules: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(DEFAULT_RULES)
    if rules:
        merged.update(rules)
    return merged


def _issue_row(
    *,
    symbol: str,
    datetime_text: str,
    freq: str,
    issue_code: str,
    severity: str,
    action: str,
    detail: dict[str, Any] | None = None,
) -> dict[str, str]:
    return {
        "symbol": str(symbol).zfill(6),
        "datetime": str(datetime_text),
        "freq": freq,
        "issue_code": issue_code,
        "severity": severity,
        "action": action,
        "detail": json.dumps(detail or {}, ensure_ascii=False, sort_keys=True),
    }


def _empty_bars() -> pd.DataFrame:
    return pd.DataFrame(columns=["symbol", "datetime", "freq", "open", "high", "low", "close", "volume"])


def _empty_issues() -> pd.DataFrame:
    return pd.DataFrame(columns=["symbol", "datetime", "freq", "issue_code", "severity", "action", "detail"])


def summarize_quality_issues(issues_df: pd.DataFrame) -> dict[str, Any]:
    if issues_df.empty:
        return {
            "issue_counts_by_type": {},
            "issue_counts_by_code": {},
            "dropped_by_reason": {},
            "warned_by_reason": {},
            "repaired_by_reason": {},
        }
    by_type = Counter(issues_df["issue_code"].astype(str))
    by_code = Counter(issues_df["symbol"].astype(str).str.zfill(6))
    dropped = Counter(issues_df.loc[issues_df["action"] == "dropped", "issue_code"].astype(str))
    warned = Counter(issues_df.loc[issues_df["severity"] == "warn", "issue_code"].astype(str))
    repaired = Counter(issues_df.loc[issues_df["action"] == "repaired", "issue_code"].astype(str))
    return {
        "issue_counts_by_type": dict(sorted(by_type.items())),
        "issue_counts_by_code": dict(sorted(by_code.items())),
        "dropped_by_reason": dict(sorted(dropped.items())),
        "warned_by_reason": dict(sorted(warned.items())),
        "repaired_by_reason": dict(sorted(repaired.items())),
    }


def clean_symbol_bars(
    raw_df: pd.DataFrame,
    rules: dict[str, Any] | None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    cfg = _merge_rules(rules)
    if raw_df.empty:
        return _empty_bars(), _empty_issues(), {
            "symbol": "",
            "scanned_rows": 0,
            "kept_rows": 0,
            "dropped_rows": 0,
            "repaired_rows": 0,
            "warned_rows": 0,
            "affected": False,
            "clean_date_range": {"min": None, "max": None},
        }

    required = ["symbol", "datetime", "freq", "open", "high", "low", "close", "volume"]
    df = raw_df.loc[:, required].copy()
    df["symbol"] = df["symbol"].astype(str).str.zfill(6)
    df["datetime_raw"] = df["datetime"].astype(str)
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    df["freq"] = df["freq"].astype(str)
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.sort_values(["datetime", "datetime_raw"]).reset_index(drop=True)

    symbol = str(df["symbol"].iloc[0]).zfill(6)
    freq = str(df["freq"].iloc[0])
    issues: list[dict[str, str]] = []
    scanned_rows = int(len(df))

    invalid_dt_mask = df["datetime"].isna()
    if invalid_dt_mask.any():
        for _, row in df.loc[invalid_dt_mask].iterrows():
            issues.append(
                _issue_row(
                    symbol=symbol,
                    datetime_text=str(row["datetime_raw"]),
                    freq=freq,
                    issue_code="invalid_datetime",
                    severity="error",
                    action="dropped",
                ),
            )
    df = df.loc[~invalid_dt_mask].copy()

    dup_mask = df.duplicated(subset=["symbol", "datetime", "freq"], keep="last")
    if dup_mask.any():
        for _, row in df.loc[dup_mask].iterrows():
            issues.append(
                _issue_row(
                    symbol=symbol,
                    datetime_text=row["datetime"].strftime("%Y-%m-%d"),
                    freq=freq,
                    issue_code="duplicate_bar",
                    severity="error",
                    action="dropped",
                ),
            )
    df = df.loc[~dup_mask].copy()

    invalid_price_mask = (
        df[["open", "high", "low", "close"]].isna().any(axis=1)
        | (df[["open", "high", "low", "close"]] <= 0).any(axis=1)
    )
    if invalid_price_mask.any():
        for _, row in df.loc[invalid_price_mask].iterrows():
            issues.append(
                _issue_row(
                    symbol=symbol,
                    datetime_text=row["datetime"].strftime("%Y-%m-%d"),
                    freq=freq,
                    issue_code="invalid_price",
                    severity="error",
                    action="dropped",
                ),
            )
    df = df.loc[~invalid_price_mask].copy()

    if cfg.get("drop_zero_or_negative_volume", True):
        invalid_volume_mask = df["volume"].isna() | (df["volume"] <= 0)
        if invalid_volume_mask.any():
            for _, row in df.loc[invalid_volume_mask].iterrows():
                issues.append(
                    _issue_row(
                        symbol=symbol,
                        datetime_text=row["datetime"].strftime("%Y-%m-%d"),
                        freq=freq,
                        issue_code="invalid_volume",
                        severity="error",
                        action="dropped",
                    ),
                )
        df = df.loc[~invalid_volume_mask].copy()

    repaired_dates: set[str] = set()
    if cfg.get("repair_ohlc_envelope", True) and not df.empty:
        for idx, row in df.iterrows():
            dt_text = row["datetime"].strftime("%Y-%m-%d")
            target_high = max(float(row["high"]), float(row["open"]), float(row["close"]))
            target_low = min(float(row["low"]), float(row["open"]), float(row["close"]))
            if target_high != float(row["high"]):
                df.at[idx, "high"] = target_high
                repaired_dates.add(dt_text)
                issues.append(
                    _issue_row(
                        symbol=symbol,
                        datetime_text=dt_text,
                        freq=freq,
                        issue_code="repair_high",
                        severity="info",
                        action="repaired",
                        detail={"new_high": target_high},
                    ),
                )
            if target_low != float(row["low"]):
                df.at[idx, "low"] = target_low
                repaired_dates.add(dt_text)
                issues.append(
                    _issue_row(
                        symbol=symbol,
                        datetime_text=dt_text,
                        freq=freq,
                        issue_code="repair_low",
                        severity="info",
                        action="repaired",
                        detail={"new_low": target_low},
                    ),
                )

    invalid_envelope_mask = (
        (df["high"] < df[["open", "close"]].max(axis=1))
        | (df["low"] > df[["open", "close"]].min(axis=1))
        | (df["high"] < df["low"])
    )
    if invalid_envelope_mask.any():
        for _, row in df.loc[invalid_envelope_mask].iterrows():
            issues.append(
                _issue_row(
                    symbol=symbol,
                    datetime_text=row["datetime"].strftime("%Y-%m-%d"),
                    freq=freq,
                    issue_code="invalid_envelope",
                    severity="error",
                    action="dropped",
                ),
            )
    df = df.loc[~invalid_envelope_mask].copy()
    df = df.sort_values("datetime").reset_index(drop=True)

    clean_rows: list[dict[str, object]] = []
    recent_volumes: list[float] = []
    prev_clean_close: float | None = None
    warned_dates: set[str] = set()

    for _, row in df.iterrows():
        dt_text = row["datetime"].strftime("%Y-%m-%d")
        hard_drop = False
        row_volume = float(row["volume"])

        if prev_clean_close is not None and prev_clean_close > 0:
            close_ret = abs(float(row["close"]) / prev_clean_close - 1.0)
            if close_ret > float(cfg["hard_abs_daily_return"]):
                issues.append(
                    _issue_row(
                        symbol=symbol,
                        datetime_text=dt_text,
                        freq=freq,
                        issue_code="hard_daily_return",
                        severity="error",
                        action="dropped",
                        detail={"abs_daily_return": close_ret, "prev_close": prev_clean_close},
                    ),
                )
                hard_drop = True
            elif close_ret > float(cfg["warn_abs_daily_return"]):
                warned_dates.add(dt_text)
                issues.append(
                    _issue_row(
                        symbol=symbol,
                        datetime_text=dt_text,
                        freq=freq,
                        issue_code="warn_daily_return",
                        severity="warn",
                        action="kept",
                        detail={"abs_daily_return": close_ret, "prev_close": prev_clean_close},
                    ),
                )

            open_gap = abs(float(row["open"]) / prev_clean_close - 1.0)
            if open_gap > float(cfg["hard_open_gap"]):
                issues.append(
                    _issue_row(
                        symbol=symbol,
                        datetime_text=dt_text,
                        freq=freq,
                        issue_code="hard_open_gap",
                        severity="error",
                        action="dropped",
                        detail={"abs_open_gap": open_gap, "prev_close": prev_clean_close},
                    ),
                )
                hard_drop = True
            elif open_gap > float(cfg["warn_open_gap"]):
                warned_dates.add(dt_text)
                issues.append(
                    _issue_row(
                        symbol=symbol,
                        datetime_text=dt_text,
                        freq=freq,
                        issue_code="warn_open_gap",
                        severity="warn",
                        action="kept",
                        detail={"abs_open_gap": open_gap, "prev_close": prev_clean_close},
                    ),
                )

        intraday_range = float(row["high"]) / float(row["low"]) - 1.0
        if intraday_range > float(cfg["hard_intraday_range"]):
            issues.append(
                _issue_row(
                    symbol=symbol,
                    datetime_text=dt_text,
                    freq=freq,
                    issue_code="hard_intraday_range",
                    severity="error",
                    action="dropped",
                    detail={"intraday_range": intraday_range},
                ),
            )
            hard_drop = True
        elif intraday_range > float(cfg["warn_intraday_range"]):
            warned_dates.add(dt_text)
            issues.append(
                _issue_row(
                    symbol=symbol,
                    datetime_text=dt_text,
                    freq=freq,
                    issue_code="warn_intraday_range",
                    severity="warn",
                    action="kept",
                    detail={"intraday_range": intraday_range},
                ),
            )

        if recent_volumes:
            volume_median = float(pd.Series(recent_volumes[-20:]).median())
            if volume_median > 0:
                spike = row_volume / volume_median
                if spike > float(cfg["warn_volume_spike_mult"]):
                    warned_dates.add(dt_text)
                    issues.append(
                        _issue_row(
                            symbol=symbol,
                            datetime_text=dt_text,
                            freq=freq,
                            issue_code="warn_volume_spike",
                            severity="warn",
                            action="kept",
                            detail={"volume_spike_mult": spike, "median_20": volume_median},
                        ),
                    )

        if hard_drop:
            continue

        clean_rows.append(
            {
                "symbol": symbol,
                "datetime": dt_text,
                "freq": freq,
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": row_volume,
            },
        )
        prev_clean_close = float(row["close"])
        recent_volumes.append(row_volume)

    clean_df = pd.DataFrame(clean_rows, columns=["symbol", "datetime", "freq", "open", "high", "low", "close", "volume"])
    issues_df = pd.DataFrame(issues, columns=["symbol", "datetime", "freq", "issue_code", "severity", "action", "detail"])
    if issues_df.empty:
        issues_df = _empty_issues()

    summary = summarize_quality_issues(issues_df)
    kept_rows = int(len(clean_df))
    dropped_rows = int(scanned_rows - kept_rows)
    clean_min = clean_df["datetime"].min() if not clean_df.empty else None
    clean_max = clean_df["datetime"].max() if not clean_df.empty else None
    stats = {
        "symbol": symbol,
        "scanned_rows": scanned_rows,
        "kept_rows": kept_rows,
        "dropped_rows": dropped_rows,
        "repaired_rows": int(len(repaired_dates)),
        "warned_rows": int(len(warned_dates)),
        "affected": bool(not issues_df.empty),
        "clean_date_range": {"min": clean_min, "max": clean_max},
        **summary,
    }
    return clean_df, issues_df, stats


def _load_raw_symbol_bars(
    db_path: Path,
    *,
    freq: str,
    symbol: str,
    table_name: str,
) -> pd.DataFrame:
    table = str(table_name)
    with get_conn(db_path) as conn:
        ensure_bars_table(conn, table)
        df = pd.read_sql(
            f"""
            SELECT symbol, datetime, freq, open, high, low, close, volume
            FROM {table}
            WHERE symbol=? AND freq=?
            ORDER BY datetime
            """,
            conn,
            params=(str(symbol).zfill(6), freq),
        )
    return df


def rebuild_clean_bars(
    db_path: Path,
    freq: str,
    codes: list[str],
    full_refresh: bool = False,
    data_quality_cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = _merge_rules(data_quality_cfg)
    source_table = str(cfg.get("source_table", RAW_BARS_TABLE))
    clean_table = str(cfg.get("clean_table", CLEAN_BARS_TABLE))
    issues_table = str(cfg.get("issues_table", ISSUES_TABLE))

    raw_codes = sorted({str(code).zfill(6) for code in codes if str(code).strip()})
    if full_refresh and not raw_codes:
        raw_codes = sorted(list_db_codes(db_path, freq=freq, data_mode="raw"))
    if not raw_codes:
        return {
            "source_table": source_table,
            "clean_table": clean_table,
            "issues_table": issues_table,
            "updated_codes": [],
            "scanned_rows": 0,
            "kept_rows": 0,
            "dropped_rows": 0,
            "repaired_rows": 0,
            "warned_rows": 0,
            "issue_counts_by_code": {},
            "issue_counts_by_type": {},
            "dropped_by_reason": {},
            "warned_by_reason": {},
            "affected_symbols": 0,
            "clean_date_range": {"min": None, "max": None},
            "source_rows": 0,
            "clean_rows": 0,
            "drop_ratio": 0.0,
            "symbol_stats": [],
        }

    with get_conn(db_path) as conn:
        ensure_bars_table(conn, clean_table)
        ensure_bar_issues_table(conn, issues_table)

    delete_bars(db_path, table_name=clean_table, freq=freq, codes=raw_codes)
    delete_bar_issues(db_path, table_name=issues_table, freq=freq, codes=raw_codes)

    all_clean_frames: list[pd.DataFrame] = []
    all_issue_frames: list[pd.DataFrame] = []
    symbol_stats: list[dict[str, Any]] = []
    total_source_rows = 0

    for code in raw_codes:
        raw_df = _load_raw_symbol_bars(db_path, freq=freq, symbol=code, table_name=source_table)
        total_source_rows += int(len(raw_df))
        clean_df, issues_df, stats = clean_symbol_bars(raw_df, cfg)
        symbol_stats.append(stats)
        if not clean_df.empty:
            all_clean_frames.append(clean_df)
        if not issues_df.empty:
            all_issue_frames.append(issues_df)

    merged_clean = pd.concat(all_clean_frames, ignore_index=True) if all_clean_frames else _empty_bars()
    merged_issues = pd.concat(all_issue_frames, ignore_index=True) if all_issue_frames else _empty_issues()
    upsert_bars(db_path, merged_clean, table_name=clean_table)
    upsert_bar_issues(db_path, merged_issues, table_name=issues_table)

    summary = summarize_quality_issues(merged_issues)
    clean_min = merged_clean["datetime"].min() if not merged_clean.empty else None
    clean_max = merged_clean["datetime"].max() if not merged_clean.empty else None
    kept_rows = int(len(merged_clean))
    scanned_rows = int(total_source_rows)
    dropped_rows = int(scanned_rows - kept_rows)
    repaired_rows = int(sum(int(item["repaired_rows"]) for item in symbol_stats))
    warned_rows = int(sum(int(item["warned_rows"]) for item in symbol_stats))
    affected_symbols = int(sum(1 for item in symbol_stats if item["affected"]))

    return {
        "source_table": source_table,
        "clean_table": clean_table,
        "issues_table": issues_table,
        "updated_codes": raw_codes,
        "scanned_rows": scanned_rows,
        "kept_rows": kept_rows,
        "dropped_rows": dropped_rows,
        "repaired_rows": repaired_rows,
        "warned_rows": warned_rows,
        "issue_counts_by_code": summary["issue_counts_by_code"],
        "issue_counts_by_type": summary["issue_counts_by_type"],
        "dropped_by_reason": summary["dropped_by_reason"],
        "warned_by_reason": summary["warned_by_reason"],
        "affected_symbols": affected_symbols,
        "clean_date_range": {"min": clean_min, "max": clean_max},
        "source_rows": scanned_rows,
        "clean_rows": kept_rows,
        "drop_ratio": float(dropped_rows / scanned_rows) if scanned_rows > 0 else 0.0,
        "symbol_stats": symbol_stats,
    }


def write_quality_outputs(
    *,
    project: str,
    freq: str,
    meta_dir: Path,
    stats: dict[str, Any],
) -> tuple[Path, Path]:
    meta_dir.mkdir(parents=True, exist_ok=True)
    summary_path = meta_dir / "data_quality_summary.json"
    by_symbol_path = meta_dir / "data_quality_by_symbol.csv"

    summary_payload = {
        "project": project,
        "freq": freq,
        "source_rows": stats.get("source_rows", 0),
        "clean_rows": stats.get("clean_rows", 0),
        "drop_ratio": stats.get("drop_ratio", 0.0),
        "repaired_rows": stats.get("repaired_rows", 0),
        "warned_rows": stats.get("warned_rows", 0),
        "dropped_by_reason": stats.get("dropped_by_reason", {}),
        "warned_by_reason": stats.get("warned_by_reason", {}),
        "affected_symbols": stats.get("affected_symbols", 0),
        "clean_date_range": stats.get("clean_date_range", {"min": None, "max": None}),
    }
    with open(summary_path, "w", encoding="utf-8") as handle:
        json.dump(summary_payload, handle, ensure_ascii=False, indent=2)

    pd.DataFrame(stats.get("symbol_stats", [])).to_csv(by_symbol_path, index=False, encoding="utf-8-sig")
    return summary_path, by_symbol_path


def clean_table_ready(
    db_path: Path,
    *,
    freq: str,
    clean_table: str = CLEAN_BARS_TABLE,
    codes: list[str] | None = None,
) -> bool:
    requested_codes = None
    if codes is not None:
        requested_codes = {str(code).strip().zfill(6) for code in codes if str(code).strip()}
        if not requested_codes:
            return False

    with get_conn(db_path) as conn:
        if not table_exists(conn, clean_table):
            return False
        raw_rows = conn.execute(
            f"SELECT DISTINCT symbol FROM {RAW_BARS_TABLE} WHERE freq=?",
            (freq,),
        ).fetchall()
        raw_codes = {str(row[0]).zfill(6) for row in raw_rows}
        clean_rows = conn.execute(
            f"SELECT DISTINCT symbol FROM {clean_table} WHERE freq=?",
            (freq,),
        ).fetchall()
        clean_codes = {str(row[0]).zfill(6) for row in clean_rows}

    if requested_codes is not None:
        target_codes = requested_codes
    elif raw_codes:
        target_codes = raw_codes
    else:
        target_codes = set()

    if target_codes:
        return target_codes.issubset(clean_codes)
    return bool(clean_codes)
