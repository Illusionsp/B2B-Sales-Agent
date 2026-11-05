"""
Guardrails the original prompt pack didn't have:

1. A dedupe ledger (SQLite) — so the same company never gets a second
   generated email silently. This matters the moment this is wired up to
   actually send mail; better to build the habit in from day one.
2. A simple sliding-window rate limiter — so a bug, loop, or overeager
   client script can't burn through the whole Groq/Tavily free quota
   (or worse, blast a lead list) in one run.
"""
import sqlite3
import time
import threading
from contextlib import contextmanager

from app.config import settings

_lock = threading.Lock()
_request_timestamps: list[float] = []


def _get_conn():
    conn = sqlite3.connect(settings.SENT_LOG_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sent_log (
                company_name_lower TEXT PRIMARY KEY,
                company_name TEXT,
                company_url TEXT,
                subject_line TEXT,
                created_at TEXT
            )
            """
        )


def has_been_processed(company_name: str) -> dict | None:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM sent_log WHERE company_name_lower = ?",
            (company_name.strip().lower(),),
        ).fetchone()
        return dict(row) if row else None


def record_processed(company_name: str, company_url: str, subject_line: str):
    with _get_conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO sent_log
                (company_name_lower, company_name, company_url, subject_line, created_at)
            VALUES (?, ?, ?, ?, datetime('now'))
            """,
            (company_name.strip().lower(), company_name, company_url, subject_line),
        )


def remove_from_log(company_name: str) -> bool:
    with _get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM sent_log WHERE company_name_lower = ?",
            (company_name.strip().lower(),),
        )
        return cur.rowcount > 0


def list_log() -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute("SELECT * FROM sent_log ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


class RateLimitExceeded(Exception):
    pass


def check_rate_limit():
    """Simple sliding-window limiter: N requests per rolling 60s window."""
    with _lock:
        now = time.time()
        cutoff = now - 60
        while _request_timestamps and _request_timestamps[0] < cutoff:
            _request_timestamps.pop(0)

        if len(_request_timestamps) >= settings.RATE_LIMIT_PER_MINUTE:
            raise RateLimitExceeded(
                f"Rate limit of {settings.RATE_LIMIT_PER_MINUTE} requests/minute exceeded. "
                "Try again shortly."
            )
        _request_timestamps.append(now)
