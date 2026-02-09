import sqlite3
from pathlib import Path

DB_PATH = Path("data/market.db")

def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS bars (
            symbol TEXT NOT NULL,
            freq TEXT NOT NULL,
            datetime TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            adj_factor REAL,
            PRIMARY KEY (symbol, freq, datetime)
        )
        """
    )
    conn.commit()
    conn.close()
