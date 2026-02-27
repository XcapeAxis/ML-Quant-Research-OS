from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

import pandas as pd


def get_conn(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    return conn


def ensure_bars_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bars (
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


def upsert_bars(db_path: Path, bars_df: pd.DataFrame) -> int:
    if bars_df.empty:
        return 0
    cols = ["symbol", "datetime", "freq", "open", "high", "low", "close", "volume"]
    rows = list(bars_df.loc[:, cols].itertuples(index=False, name=None))
    with get_conn(db_path) as conn:
        ensure_bars_table(conn)
        conn.executemany(
            """
            INSERT OR REPLACE INTO bars (symbol, datetime, freq, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
    return len(rows)


def _chunked(items: list[str], size: int) -> Iterable[list[str]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def load_close_volume_panel(
    db_path: Path,
    freq: str,
    codes: list[str],
    start: str | None = None,
    end: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not codes:
        raise ValueError("codes cannot be empty")

    frames: list[pd.DataFrame] = []
    with get_conn(db_path) as conn:
        for chunk in _chunked(codes, 800):
            placeholders = ",".join(["?"] * len(chunk))
            sql = (
                f"SELECT symbol, datetime, close, volume FROM bars "
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
) -> dict[str, pd.DataFrame]:
    """Load OHLCV data as a dictionary of DataFrames.

    Returns a dict with keys: open, high, low, close, volume
    Each value is a DataFrame with dates as index and codes as columns.
    """
    if not codes:
        raise ValueError("codes cannot be empty")

    frames: list[pd.DataFrame] = []
    with get_conn(db_path) as conn:
        for chunk in _chunked(codes, 800):
            placeholders = ",".join(["?"] * len(chunk))
            sql = (
                f"SELECT symbol, datetime, open, high, low, close, volume FROM bars "
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

    result = {}
    for col in ["open", "high", "low", "close", "volume"]:
        pivot = raw.pivot(index="datetime", columns="symbol", values=col).sort_index()
        result[col] = pivot.astype(float)

    return result


def list_db_codes(db_path: Path, freq: str) -> set[str]:
    with get_conn(db_path) as conn:
        rows = conn.execute("SELECT DISTINCT symbol FROM bars WHERE freq=?", (freq,)).fetchall()
    return {str(row[0]).zfill(6) for row in rows}


def db_date_range(db_path: Path, freq: str) -> tuple[str | None, str | None]:
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT MIN(datetime), MAX(datetime) FROM bars WHERE freq=?",
            (freq,),
        ).fetchone()
    if row is None:
        return None, None
    return row[0], row[1]


def coverage_report(db_path: Path, freq: str, codes: list[str]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    with get_conn(db_path) as conn:
        for code in codes:
            result = conn.execute(
                """
                SELECT COUNT(*), MIN(datetime), MAX(datetime)
                FROM bars
                WHERE symbol=? AND freq=?
                """,
                (code, freq),
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
