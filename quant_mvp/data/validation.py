from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from ..db import coverage_report, get_conn, table_exists
from .contracts import DataFinding, DataQualityReport


def build_tradability_mask(
    close: pd.DataFrame,
    volume: pd.DataFrame,
    *,
    limit_threshold: float = 0.095,
    min_volume: float = 0.0,
) -> pd.DataFrame:
    prev_close = close.shift(1)
    daily_ret = close.divide(prev_close).subtract(1.0)
    volume_ok = volume.fillna(0.0) > float(min_volume)
    price_ok = daily_ret.abs().lt(limit_threshold) | daily_ret.isna()
    close_ok = close.notna() & close.gt(0.0)
    return volume_ok & price_ok & close_ok


def _table_count(conn, table_name: str, freq: str) -> int:
    if not table_exists(conn, table_name):
        return 0
    row = conn.execute(
        f"SELECT COUNT(*) FROM {table_name} WHERE freq=?",
        (freq,),
    ).fetchone()
    return int(row[0] or 0) if row else 0


def _duplicate_count(conn, table_name: str, freq: str) -> int:
    if not table_exists(conn, table_name):
        return 0
    row = conn.execute(
        f"""
        SELECT COUNT(*) FROM (
            SELECT symbol, datetime, freq, COUNT(*) AS n
            FROM {table_name}
            WHERE freq=?
            GROUP BY symbol, datetime, freq
            HAVING COUNT(*) > 1
        )
        """,
        (freq,),
    ).fetchone()
    return int(row[0] or 0) if row else 0


def validate_project_data(
    *,
    project: str,
    db_path: Path,
    freq: str,
    universe_codes: list[str],
    provider_name: str,
    data_quality_cfg: dict[str, Any] | None,
    limit_threshold: float = 0.095,
) -> DataQualityReport:
    rules = data_quality_cfg or {}
    raw_table = str(rules.get("source_table", "bars"))
    clean_table = str(rules.get("clean_table", "bars_clean"))
    validated_table = clean_table

    coverage = coverage_report(
        db_path=db_path,
        freq=freq,
        codes=universe_codes,
        data_mode="auto",
    )

    missing_rows = int((coverage["bars_count"] <= 0).sum()) if not coverage.empty else 0
    raw_rows = 0
    cleaned_rows = 0
    validated_rows = 0
    duplicate_rows = 0
    zero_volume_rows = 0
    limit_locked_rows = 0
    suspended_rows = 0

    with get_conn(db_path) as conn:
        raw_rows = _table_count(conn, raw_table, freq)
        cleaned_rows = _table_count(conn, clean_table, freq)
        validated_rows = _table_count(conn, validated_table, freq)
        duplicate_rows = _duplicate_count(conn, raw_table, freq)

        if table_exists(conn, clean_table):
            zero_volume_rows = int(
                conn.execute(
                    f"SELECT COUNT(*) FROM {clean_table} WHERE freq=? AND (volume IS NULL OR volume <= 0)",
                    (freq,),
                ).fetchone()[0]
                or 0,
            )
            suspended_rows = zero_volume_rows
            frame = pd.read_sql(
                f"SELECT datetime, symbol, close, volume FROM {clean_table} WHERE freq=? ORDER BY datetime, symbol",
                conn,
                params=(freq,),
            )
            if not frame.empty:
                frame["datetime"] = pd.to_datetime(frame["datetime"])
                frame["symbol"] = frame["symbol"].astype(str).str.zfill(6)
                close = frame.pivot(index="datetime", columns="symbol", values="close").sort_index()
                volume = frame.pivot(index="datetime", columns="symbol", values="volume").sort_index()
                tradable = build_tradability_mask(
                    close.astype(float),
                    volume.astype(float),
                    limit_threshold=limit_threshold,
                )
                limit_locked_rows = int((~tradable & volume.fillna(0.0).gt(0.0)).sum().sum())

    findings: list[DataFinding] = []
    if missing_rows:
        findings.append(DataFinding(code="coverage_gap", severity="warn", message="Universe members without bars", count=missing_rows))
    if duplicate_rows:
        findings.append(DataFinding(code="duplicate_rows", severity="error", message="Duplicate raw bars detected", count=duplicate_rows))
    if zero_volume_rows:
        findings.append(DataFinding(code="zero_volume_rows", severity="warn", message="Rows with zero or missing volume", count=zero_volume_rows))
    if limit_locked_rows:
        findings.append(DataFinding(code="limit_locked_rows", severity="info", message="Rows flagged as limit-locked proxies", count=limit_locked_rows))

    notes = [
        "Data quality is layered as raw -> cleaned -> validated. Validated currently reuses the cleaned table plus explicit validation reports.",
        "Tradability uses daily close-to-close limit proxies and positive-volume checks; future paid providers can replace this with exchange flags.",
    ]

    coverage_ratio = float((coverage["bars_count"] > 0).mean()) if not coverage.empty else 0.0
    return DataQualityReport(
        project=project,
        frequency=freq,
        source_provider=provider_name,
        coverage_ratio=coverage_ratio,
        raw_rows=raw_rows,
        cleaned_rows=cleaned_rows,
        validated_rows=validated_rows,
        duplicate_rows=duplicate_rows,
        missing_rows=missing_rows,
        zero_volume_rows=zero_volume_rows,
        limit_locked_rows=limit_locked_rows,
        suspended_rows=suspended_rows,
        findings=findings,
        notes=notes,
    )
