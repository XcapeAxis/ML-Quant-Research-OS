# src/quant_core/data/bars.py
import pandas as pd
from .db import get_conn, init_db

def upsert_bars(
    df: pd.DataFrame,
    symbol: str,
    freq: str,
):
    """
    df columns must include:
    datetime, open, high, low, close, volume, adj_factor (optional)
    """
    init_db()

    df = df.copy()
    df["symbol"] = symbol
    df["freq"] = freq

    with get_conn() as conn:
        df.to_sql(
            "bars",
            conn,
            if_exists="append",
            index=False,
        )

def load_bars(
    symbol: str,
    freq: str,
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    init_db()

    sql = """
    SELECT
        datetime,
        open,
        high,
        low,
        close,
        volume,
        adj_factor
    FROM bars
    WHERE symbol = ?
      AND freq = ?
    """
    params = [symbol, freq]

    if start:
        sql += " AND datetime >= ?"
        params.append(start)
    if end:
        sql += " AND datetime <= ?"
        params.append(end)

    sql += " ORDER BY datetime"

    with get_conn() as conn:
        return pd.read_sql(
            sql,
            conn,
            params=params,
            parse_dates=["datetime"],
        )
