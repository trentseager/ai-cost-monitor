import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent / "usage.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL DEFAULT (datetime('now')),
    user_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    tokens_in INTEGER NOT NULL DEFAULT 0,
    tokens_out INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL NOT NULL DEFAULT 0,
    blocked INTEGER NOT NULL DEFAULT 0,
    pricing_known INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS limits (
    user_id TEXT PRIMARY KEY,
    daily_limit_usd REAL NOT NULL
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
        conn.executescript(SCHEMA)


def log_request(user_id: str, provider: str, model: str, tokens_in: int, tokens_out: int,
                 cost_usd: float, blocked: bool, pricing_known: bool):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO requests (user_id, provider, model, tokens_in, tokens_out, cost_usd, blocked, pricing_known)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, provider, model, tokens_in, tokens_out, cost_usd, int(blocked), int(pricing_known)),
        )


def get_limit(user_id: str) -> float | None:
    with get_conn() as conn:
        row = conn.execute("SELECT daily_limit_usd FROM limits WHERE user_id = ?", (user_id,)).fetchone()
        return row["daily_limit_usd"] if row else None


def set_limit(user_id: str, daily_limit_usd: float):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO limits (user_id, daily_limit_usd) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET daily_limit_usd = excluded.daily_limit_usd
            """,
            (user_id, daily_limit_usd),
        )


def today_cost_for_user(user_id: str) -> float:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(cost_usd), 0) AS total FROM requests
            WHERE user_id = ? AND blocked = 0 AND date(ts) = date('now')
            """,
            (user_id,),
        ).fetchone()
        return row["total"]


def user_summaries_today() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT l.user_id AS user_id, l.daily_limit_usd AS daily_limit_usd,
                   COALESCE((
                       SELECT SUM(r.cost_usd) FROM requests r
                       WHERE r.user_id = l.user_id AND r.blocked = 0 AND date(r.ts) = date('now')
                   ), 0) AS spent_today
            FROM limits l
            ORDER BY spent_today DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def daily_totals() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT date(ts) AS date, SUM(cost_usd) AS cost_usd,
                   SUM(tokens_in) AS tokens_in, SUM(tokens_out) AS tokens_out
            FROM requests
            WHERE blocked = 0
            GROUP BY date(ts)
            ORDER BY date
            """
        ).fetchall()
        return [dict(r) for r in rows]
