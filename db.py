import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent / "usage.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    date TEXT NOT NULL,
    model TEXT NOT NULL,
    tokens_in INTEGER NOT NULL DEFAULT 0,
    tokens_out INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL NOT NULL DEFAULT 0,
    fetched_at TEXT NOT NULL,
    UNIQUE(provider, date, model)
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.execute(SCHEMA)


def upsert_usage(provider: str, date: str, model: str, tokens_in: int, tokens_out: int, cost_usd: float, fetched_at: str):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO usage (provider, date, model, tokens_in, tokens_out, cost_usd, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(provider, date, model) DO UPDATE SET
                tokens_in=excluded.tokens_in,
                tokens_out=excluded.tokens_out,
                cost_usd=excluded.cost_usd,
                fetched_at=excluded.fetched_at
            """,
            (provider, date, model, tokens_in, tokens_out, cost_usd, fetched_at),
        )


def all_usage():
    with get_conn() as conn:
        rows = conn.execute("SELECT provider, date, model, tokens_in, tokens_out, cost_usd, fetched_at FROM usage ORDER BY date").fetchall()
        return [dict(row) for row in rows]
