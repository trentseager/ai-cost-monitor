import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
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

CREATE TABLE IF NOT EXISTS credit_balances (
    user_id TEXT PRIMARY KEY,
    balance_usd REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS reservations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL DEFAULT (datetime('now')),
    user_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    reserved_usd REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS rate_limit_configs (
    user_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    limit_type TEXT NOT NULL,
    limit_value INTEGER NOT NULL,
    window_seconds INTEGER NOT NULL,
    PRIMARY KEY (user_id, provider)
);

CREATE TABLE IF NOT EXISTS rate_limit_windows (
    user_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    window_start TEXT NOT NULL,
    used_value INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, provider, window_start)
);

CREATE TABLE IF NOT EXISTS user_labels (
    user_id TEXT PRIMARY KEY,
    label TEXT NOT NULL DEFAULT ''
);
"""


@contextmanager
def get_conn():
    # timeout=30: the sqlite3 default (5s) isn't enough headroom under real
    # concurrent write bursts — see docs/credit-reserve-settle.md's load-test
    # findings, where the default caused "database is locked" errors.
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        # WAL persists in the DB file's header once set — no need to
        # re-issue on every connection, just here at startup.
        conn.execute("PRAGMA journal_mode=WAL")
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


def has_credit_metering(user_id: str) -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT 1 FROM credit_balances WHERE user_id = ?", (user_id,)).fetchone()
        return row is not None


def add_credit(user_id: str, amount_usd: float):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO credit_balances (user_id, balance_usd) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET balance_usd = balance_usd + excluded.balance_usd
            """,
            (user_id, amount_usd),
        )


def _release_stale_reservations(conn, user_id: str, older_than_minutes: int = 30):
    rows = conn.execute(
        "SELECT id, reserved_usd FROM reservations "
        "WHERE user_id = ? AND status = 'pending' AND ts < datetime('now', ?)",
        (user_id, f"-{older_than_minutes} minutes"),
    ).fetchall()
    for r in rows:
        conn.execute("UPDATE credit_balances SET balance_usd = balance_usd + ? WHERE user_id = ?",
                     (r["reserved_usd"], user_id))
        conn.execute("UPDATE reservations SET status = 'released' WHERE id = ?", (r["id"],))


def reserve_credit(user_id: str, provider: str, reserved_usd: float) -> int | None:
    """Atomically reserve `reserved_usd` against the user's balance.
    Returns the reservation id, or None if the balance is insufficient."""
    with get_conn() as conn:
        _release_stale_reservations(conn, user_id)
        cur = conn.execute(
            "UPDATE credit_balances SET balance_usd = balance_usd - ? WHERE user_id = ? AND balance_usd >= ?",
            (reserved_usd, user_id, reserved_usd),
        )
        if cur.rowcount == 0:
            return None
        ins = conn.execute(
            "INSERT INTO reservations (user_id, provider, reserved_usd, status) VALUES (?, ?, ?, 'pending')",
            (user_id, provider, reserved_usd),
        )
        return ins.lastrowid


def settle_reservation(reservation_id: int, actual_cost_usd: float):
    """Release the reservation, deduct the actual cost, and refund the difference."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT user_id, reserved_usd FROM reservations WHERE id = ? AND status = 'pending'",
            (reservation_id,),
        ).fetchone()
        if row is None:
            return
        refund = row["reserved_usd"] - actual_cost_usd
        conn.execute("UPDATE credit_balances SET balance_usd = balance_usd + ? WHERE user_id = ?",
                     (refund, row["user_id"]))
        conn.execute("UPDATE reservations SET status = 'settled' WHERE id = ?", (reservation_id,))


def release_reservation(reservation_id: int):
    """Refund a reservation in full (used when the upstream call produced no billable usage)."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT user_id, reserved_usd FROM reservations WHERE id = ? AND status = 'pending'",
            (reservation_id,),
        ).fetchone()
        if row is None:
            return
        conn.execute("UPDATE credit_balances SET balance_usd = balance_usd + ? WHERE user_id = ?",
                     (row["reserved_usd"], row["user_id"]))
        conn.execute("UPDATE reservations SET status = 'released' WHERE id = ?", (reservation_id,))


def credit_summaries() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT cb.user_id AS user_id, cb.balance_usd AS balance_usd,
                   COALESCE((
                       SELECT SUM(r.reserved_usd) FROM reservations r
                       WHERE r.user_id = cb.user_id AND r.status = 'pending'
                   ), 0) AS pending_reserved_usd
            FROM credit_balances cb
            ORDER BY cb.balance_usd ASC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def _window_start(window_seconds: int) -> str:
    """Fixed-window bucket start, floored to the nearest `window_seconds`
    boundary. Computed in Python because SQLite's datetime() can't cleanly
    floor to an arbitrary N-second bucket the way date('now') does for
    whole days elsewhere in this file."""
    bucket_epoch = (int(time.time()) // window_seconds) * window_seconds
    return datetime.fromtimestamp(bucket_epoch, tz=timezone.utc).isoformat()


def get_rate_limit_config(user_id: str, provider: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT limit_type, limit_value, window_seconds FROM rate_limit_configs "
            "WHERE user_id = ? AND provider = ?",
            (user_id, provider),
        ).fetchone()
        return dict(row) if row else None


def set_rate_limit(user_id: str, provider: str, limit_type: str, limit_value: int, window_seconds: int):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO rate_limit_configs (user_id, provider, limit_type, limit_value, window_seconds)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, provider) DO UPDATE SET
                limit_type = excluded.limit_type,
                limit_value = excluded.limit_value,
                window_seconds = excluded.window_seconds
            """,
            (user_id, provider, limit_type, limit_value, window_seconds),
        )


def reserve_rate_limit(user_id: str, provider: str, config: dict, amount: int) -> dict | None:
    """Atomically reserve `amount` units against the current fixed window's
    budget. Returns {"window_start", "reserved_amount"} on success, or None
    if that would exceed limit_value."""
    window_start = _window_start(config["window_seconds"])
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO rate_limit_windows (user_id, provider, window_start, used_value) "
            "VALUES (?, ?, ?, 0) ON CONFLICT(user_id, provider, window_start) DO NOTHING",
            (user_id, provider, window_start),
        )
        cur = conn.execute(
            "UPDATE rate_limit_windows SET used_value = used_value + ? "
            "WHERE user_id = ? AND provider = ? AND window_start = ? AND used_value + ? <= ?",
            (amount, user_id, provider, window_start, amount, config["limit_value"]),
        )
        if cur.rowcount == 0:
            return None
        return {"window_start": window_start, "reserved_amount": amount}


def release_rate_limit(user_id: str, provider: str, hold: dict, amount: int):
    """Give back `amount` units to the window the hold was reserved in
    (used both to fully undo a hold and to refund unused token headroom on
    settle). Clamped at 0 — a window that already rolled over is a no-op."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE rate_limit_windows SET used_value = MAX(0, used_value - ?) "
            "WHERE user_id = ? AND provider = ? AND window_start = ?",
            (amount, user_id, provider, hold["window_start"]),
        )


def rate_limit_summaries() -> list[dict]:
    with get_conn() as conn:
        configs = conn.execute(
            "SELECT user_id, provider, limit_type, limit_value, window_seconds FROM rate_limit_configs"
        ).fetchall()
        out = []
        for c in configs:
            window_start = _window_start(c["window_seconds"])
            row = conn.execute(
                "SELECT used_value FROM rate_limit_windows WHERE user_id = ? AND provider = ? AND window_start = ?",
                (c["user_id"], c["provider"], window_start),
            ).fetchone()
            out.append({
                "user_id": c["user_id"],
                "provider": c["provider"],
                "limit_type": c["limit_type"],
                "limit_value": c["limit_value"],
                "window_seconds": c["window_seconds"],
                "used_value": row["used_value"] if row else 0,
            })
        return out


def set_user_label(user_id: str, label: str):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO user_labels (user_id, label) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET label = excluded.label
            """,
            (user_id, label),
        )


def user_overview() -> list[dict]:
    """One row per known user (anyone with a request, or a row in
    limits/credit_balances/rate_limit_configs), with today's spend,
    trailing 7d/30d average daily spend, and request/block counts.
    Averages are calendar-day bucketed and divide by the full window size
    (idle days count as $0), including today's partial day as-is — see
    docs/user-overview.md."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            WITH known_users AS (
                SELECT user_id FROM requests
                UNION SELECT user_id FROM limits
                UNION SELECT user_id FROM credit_balances
                UNION SELECT user_id FROM rate_limit_configs
            ),
            today_stats AS (
                SELECT user_id,
                       SUM(CASE WHEN blocked = 0 THEN cost_usd ELSE 0 END) AS spent_today,
                       COUNT(*) AS requests_today,
                       SUM(CASE WHEN blocked = 1 THEN 1 ELSE 0 END) AS blocked_today
                FROM requests
                WHERE date(ts) = date('now')
                GROUP BY user_id
            ),
            last7 AS (
                SELECT user_id, SUM(cost_usd) AS cost_7d
                FROM requests
                WHERE blocked = 0 AND date(ts) >= date('now', '-6 days')
                GROUP BY user_id
            ),
            last30 AS (
                SELECT user_id, SUM(cost_usd) AS cost_30d
                FROM requests
                WHERE blocked = 0 AND date(ts) >= date('now', '-29 days')
                GROUP BY user_id
            )
            SELECT
                ku.user_id AS user_id,
                COALESCE(ul.label, '') AS label,
                COALESCE(ts.spent_today, 0) AS spent_today,
                l.daily_limit_usd AS daily_limit_usd,
                COALESCE(l7.cost_7d, 0) / 7.0 AS avg_daily_cost_7d,
                COALESCE(l30.cost_30d, 0) / 30.0 AS avg_daily_cost_30d,
                COALESCE(ts.requests_today, 0) AS requests_today,
                COALESCE(ts.blocked_today, 0) AS blocked_today
            FROM known_users ku
            LEFT JOIN user_labels ul ON ul.user_id = ku.user_id
            LEFT JOIN limits l ON l.user_id = ku.user_id
            LEFT JOIN today_stats ts ON ts.user_id = ku.user_id
            LEFT JOIN last7 l7 ON l7.user_id = ku.user_id
            LEFT JOIN last30 l30 ON l30.user_id = ku.user_id
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
