from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Iterable, Literal

import pandas as pd


DataMode = Literal["auto", "clean", "raw"]

RAW_BARS_TABLE = "bars"
CLEAN_BARS_TABLE = "bars_clean"
ISSUES_TABLE = "bar_issues"

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _validate_identifier(name: str) -> str:
    value = str(name or "").strip()
    if not _IDENT_RE.fullmatch(value):
        raise ValueError(f"Invalid SQLite identifier: {name!r}")
    return value


def _normalize_codes(codes: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for code in codes:
        raw = str(code or "").strip()
        if not raw:
            continue
        value = raw.zfill(6)
        if value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


def get_conn(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    return conn


def ensure_bars_table(conn: sqlite3.Connection, table_name: str = RAW_BARS_TABLE) -> None:
    table = _validate_identifier(table_name)
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {table} (
            symbol TEXT NOT NULL,
            datetime TEXT NOT NULL,
            freq TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            PRIMARY KEY (symbol, datetime, freq)
        )
        """,
    )


def ensure_bar_issues_table(conn: sqlite3.Connection, table_name: str = ISSUES_TABLE) -> None:
    table = _validate_identifier(table_name)
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {table} (
            symbol TEXT NOT NULL,
            datetime TEXT NOT NULL,
            freq TEXT NOT NULL,
            issue_code TEXT NOT NULL,
            severity TEXT NOT NULL,
            action TEXT NOT NULL,
            detail TEXT,
            PRIMARY KEY (symbol, datetime, freq, issue_code, action)
        )
        """,
    )


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    table = _validate_identifier(table_name)
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def table_row_count(
    db_path: Path,
    table_name: str,
    *,
    freq: str | None = None,
    codes: list[str] | None = None,
) -> int:
    table = _validate_identifier(table_name)
    if codes is not None and not codes:
        return 0
    normalized_codes = _normalize_codes(codes or [])
    if codes is not None and not normalized_codes:
        return 0
    with get_conn(db_path) as conn:
        if not table_exists(conn, table):
            return 0
        sql = f"SELECT COUNT(*) FROM {table}"
        params: list[str] = []
        clauses: list[str] = []
        if freq is not None:
            clauses.append("freq=?")
            params.append(freq)
        if normalized_codes:
            placeholders = ",".join(["?"] * len(normalized_codes))
            clauses.append(f"symbol IN ({placeholders})")
            params.extend(normalized_codes)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        row = conn.execute(sql, params).fetchone()
    return int(row[0] or 0) if row else 0


def _codes_in_table(
    conn: sqlite3.Connection,
    table_name: str,
    freq: str,
    codes: list[str] | None = None,
) -> set[str]:
    table = _validate_identifier(table_name)
    if not table_exists(conn, table):
        return set()

    if codes is None:
        rows = conn.execute(
            f"SELECT DISTINCT symbol FROM {table} WHERE freq=?",
            (freq,),
        ).fetchall()
        return {str(row[0]).zfill(6) for row in rows}

    normalized_codes = _normalize_codes(codes)
    if not normalized_codes:
        return set()

    discovered: set[str] = set()
    for chunk in _chunked(normalized_codes, 800):
        placeholders = ",".join(["?"] * len(chunk))
        rows = conn.execute(
            f"SELECT DISTINCT symbol FROM {table} WHERE freq=? AND symbol IN ({placeholders})",
            [freq, *chunk],
        ).fetchall()
        discovered.update(str(row[0]).zfill(6) for row in rows)
    return discovered


def _clean_table_covers_codes(
    conn: sqlite3.Connection,
    freq: str,
    codes: list[str] | None = None,
) -> bool:
    if codes is None:
        target_codes = _codes_in_table(conn, RAW_BARS_TABLE, freq)
        if not target_codes:
            return bool(_codes_in_table(conn, CLEAN_BARS_TABLE, freq))
    else:
        target_codes = set(_normalize_codes(codes))
        if not target_codes:
            return False

    clean_codes = _codes_in_table(conn, CLEAN_BARS_TABLE, freq, list(target_codes))
    return target_codes.issubset(clean_codes)


def _build_read_plan(
    conn: sqlite3.Connection,
    *,
    data_mode: DataMode,
    freq: str,
    codes: list[str],
) -> list[tuple[str, list[str]]]:
    normalized_codes = _normalize_codes(codes)
    if not normalized_codes:
        return []

    if data_mode == "raw":
        return [(RAW_BARS_TABLE, normalized_codes)]
    if data_mode == "clean":
        return [(CLEAN_BARS_TABLE, normalized_codes)]

    clean_codes = _codes_in_table(conn, CLEAN_BARS_TABLE, freq, normalized_codes)
    clean_subset = [code for code in normalized_codes if code in clean_codes]
    raw_subset = [code for code in normalized_codes if code not in clean_codes]

    plan: list[tuple[str, list[str]]] = []
    if clean_subset:
        plan.append((CLEAN_BARS_TABLE, clean_subset))
    if raw_subset:
        plan.append((RAW_BARS_TABLE, raw_subset))
    return plan


def _resolve_read_table(
    conn: sqlite3.Connection,
    data_mode: DataMode,
    freq: str,
) -> str:
    if data_mode == "raw":
        return RAW_BARS_TABLE
    if data_mode == "clean":
        return CLEAN_BARS_TABLE
    if not table_exists(conn, CLEAN_BARS_TABLE):
        return RAW_BARS_TABLE
    return CLEAN_BARS_TABLE if _clean_table_covers_codes(conn, freq) else RAW_BARS_TABLE


def upsert_bars(
    db_path: Path,
    bars_df: pd.DataFrame,
    *,
    table_name: str = RAW_BARS_TABLE,
) -> int:
    if bars_df.empty:
        return 0
    cols = ["symbol", "datetime", "freq", "open", "high", "low", "close", "volume"]
    rows = list(bars_df.loc[:, cols].itertuples(index=False, name=None))
    table = _validate_identifier(table_name)
    with get_conn(db_path) as conn:
        ensure_bars_table(conn, table)
        conn.executemany(
            f"""
            INSERT OR REPLACE INTO {table} (symbol, datetime, freq, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
    return len(rows)


def upsert_bar_issues(
    db_path: Path,
    issues_df: pd.DataFrame,
    *,
    table_name: str = ISSUES_TABLE,
) -> int:
    if issues_df.empty:
        return 0
    cols = ["symbol", "datetime", "freq", "issue_code", "severity", "action", "detail"]
    rows = list(issues_df.loc[:, cols].itertuples(index=False, name=None))
    table = _validate_identifier(table_name)
    with get_conn(db_path) as conn:
        ensure_bar_issues_table(conn, table)
        conn.executemany(
            f"""
            INSERT OR REPLACE INTO {table} (symbol, datetime, freq, issue_code, severity, action, detail)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
    return len(rows)


def delete_bars(
    db_path: Path,
    *,
    table_name: str,
    freq: str,
    codes: list[str],
) -> int:
    if not codes:
        return 0
    table = _validate_identifier(table_name)
    deleted = 0
    with get_conn(db_path) as conn:
        if not table_exists(conn, table):
            return 0
        for chunk in _chunked([str(code).zfill(6) for code in codes], 800):
            placeholders = ",".join(["?"] * len(chunk))
            cur = conn.execute(
                f"DELETE FROM {table} WHERE freq=? AND symbol IN ({placeholders})",
                [freq, *chunk],
            )
            deleted += int(cur.rowcount or 0)
        conn.commit()
    return deleted


def delete_bar_issues(
    db_path: Path,
    *,
    table_name: str,
    freq: str,
    codes: list[str],
) -> int:
    if not codes:
        return 0
    table = _validate_identifier(table_name)
    deleted = 0
    with get_conn(db_path) as conn:
        if not table_exists(conn, table):
            return 0
        for chunk in _chunked([str(code).zfill(6) for code in codes], 800):
            placeholders = ",".join(["?"] * len(chunk))
            cur = conn.execute(
                f"DELETE FROM {table} WHERE freq=? AND symbol IN ({placeholders})",
                [freq, *chunk],
            )
            deleted += int(cur.rowcount or 0)
        conn.commit()
    return deleted


def _chunked(items: list[str], size: int) -> Iterable[list[str]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def load_close_volume_panel(
    db_path: Path,
    freq: str,
    codes: list[str],
    start: str | None = None,
    end: str | None = None,
    data_mode: DataMode = "auto",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not codes:
        raise ValueError("codes cannot be empty")

    frames: list[pd.DataFrame] = []
    with get_conn(db_path) as conn:
        for table, table_codes in _build_read_plan(conn, data_mode=data_mode, freq=freq, codes=codes):
            if not table_exists(conn, table):
                continue
            for chunk in _chunked(table_codes, 800):
                placeholders = ",".join(["?"] * len(chunk))
                sql = (
                    f"SELECT symbol, datetime, close, volume FROM {table} "
                    f"WHERE freq=? AND symbol IN ({placeholders})"
                )
                params: list[str] = [freq, *chunk]
                if start:
                    sql += " AND datetime >= ?"
                    params.append(start)
                if end:
                    sql += " AND datetime <= ?"
                    params.append(end)
                sql += " ORDER BY datetime, symbol"
                df = pd.read_sql(sql, conn, params=params)
                if not df.empty:
                    frames.append(df)

    if not frames:
        raise RuntimeError("No bars found for requested codes.")

    raw = pd.concat(frames, ignore_index=True)
    raw["datetime"] = pd.to_datetime(raw["datetime"])
    raw["symbol"] = raw["symbol"].astype(str).str.zfill(6)
    close = raw.pivot(index="datetime", columns="symbol", values="close").sort_index()
    volume = raw.pivot(index="datetime", columns="symbol", values="volume").sort_index()
    close = close.astype(float)
    volume = volume.astype(float)
    return close, volume


def load_ohlcv_panel(
    db_path: Path,
    freq: str,
    codes: list[str],
    start: str | None = None,
    end: str | None = None,
    data_mode: DataMode = "auto",
) -> dict[str, pd.DataFrame]:
    if not codes:
        raise ValueError("codes cannot be empty")

    frames: list[pd.DataFrame] = []
    with get_conn(db_path) as conn:
        for table, table_codes in _build_read_plan(conn, data_mode=data_mode, freq=freq, codes=codes):
            if not table_exists(conn, table):
                continue
            for chunk in _chunked(table_codes, 800):
                placeholders = ",".join(["?"] * len(chunk))
                sql = (
                    f"SELECT symbol, datetime, open, high, low, close, volume FROM {table} "
                    f"WHERE freq=? AND symbol IN ({placeholders})"
                )
                params: list[str] = [freq, *chunk]
                if start:
                    sql += " AND datetime >= ?"
                    params.append(start)
                if end:
                    sql += " AND datetime <= ?"
                    params.append(end)
                sql += " ORDER BY datetime, symbol"
                df = pd.read_sql(sql, conn, params=params)
                if not df.empty:
                    frames.append(df)

    if not frames:
        raise RuntimeError("No bars found for requested codes.")

    raw = pd.concat(frames, ignore_index=True)
    raw["datetime"] = pd.to_datetime(raw["datetime"])
    raw["symbol"] = raw["symbol"].astype(str).str.zfill(6)

    result: dict[str, pd.DataFrame] = {}
    for col in ["open", "high", "low", "close", "volume"]:
        pivot = raw.pivot(index="datetime", columns="symbol", values=col).sort_index()
        result[col] = pivot.astype(float)
    return result


def list_db_codes(
    db_path: Path,
    freq: str,
    data_mode: DataMode = "raw",
) -> set[str]:
    with get_conn(db_path) as conn:
        if data_mode == "auto":
            return _codes_in_table(conn, RAW_BARS_TABLE, freq) | _codes_in_table(conn, CLEAN_BARS_TABLE, freq)
        table = CLEAN_BARS_TABLE if data_mode == "clean" else RAW_BARS_TABLE
        return _codes_in_table(conn, table, freq)


def db_date_range(
    db_path: Path,
    freq: str,
    data_mode: DataMode = "auto",
) -> tuple[str | None, str | None]:
    with get_conn(db_path) as conn:
        table = _resolve_read_table(conn, data_mode=data_mode, freq=freq)
        if not table_exists(conn, table):
            return None, None
        row = conn.execute(
            f"SELECT MIN(datetime), MAX(datetime) FROM {table} WHERE freq=?",
            (freq,),
        ).fetchone()
    if row is None:
        return None, None
    return row[0], row[1]


def coverage_report(
    db_path: Path,
    freq: str,
    codes: list[str],
    data_mode: DataMode = "auto",
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    normalized_codes = _normalize_codes(codes)
    with get_conn(db_path) as conn:
        clean_codes = _codes_in_table(conn, CLEAN_BARS_TABLE, freq, normalized_codes) if data_mode == "auto" else set()
        for code in normalized_codes:
            if data_mode == "clean":
                table = CLEAN_BARS_TABLE
            elif data_mode == "raw":
                table = RAW_BARS_TABLE
            else:
                table = CLEAN_BARS_TABLE if code in clean_codes else RAW_BARS_TABLE
            if not table_exists(conn, table):
                count, first_date, last_date = 0, None, None
                rows.append(
                    {
                        "code": code,
                        "bars_count": count,
                        "first_date": first_date,
                        "last_date": last_date,
                    },
                )
                continue
            result = conn.execute(
                f"""
                SELECT COUNT(*), MIN(datetime), MAX(datetime)
                FROM {table}
                WHERE symbol=? AND freq=?
                {"AND datetime >= ?" if start else ""}
                {"AND datetime <= ?" if end else ""}
                """,
                tuple(
                    value
                    for value in [str(code).zfill(6), freq, start, end]
                    if value is not None
                ),
            ).fetchone()
            count, first_date, last_date = result if result else (0, None, None)
            rows.append(
                {
                    "code": code,
                    "bars_count": int(count or 0),
                    "first_date": first_date,
                    "last_date": last_date,
                },
            )
    return pd.DataFrame(rows)
