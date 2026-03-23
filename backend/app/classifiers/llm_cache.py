"""
SQLite-backed LLM response cache.

Caches API responses keyed on (provider, model, messages_hash) so that
identical prompts are never sent to the same model twice.  The cache is
shared across all classifier instances and persists across server restarts.

Usage is transparent — ``LLMBaseClassifier._call_llm`` checks the cache
before making an API call and stores the response afterwards.
"""

import hashlib
import json
import logging
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Default location next to the main DB.  Override with LLM_CACHE_DB env var.
_DEFAULT_DB = str(Path(__file__).resolve().parent.parent.parent.parent / "llm_cache.db")
_DB_PATH = os.environ.get("LLM_CACHE_DB", _DEFAULT_DB)

_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    """Return a thread-local SQLite connection (one per thread)."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(_DB_PATH, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS llm_cache (
                cache_key   TEXT PRIMARY KEY,
                provider    TEXT NOT NULL,
                model       TEXT NOT NULL,
                response    TEXT NOT NULL,
                created_at  REAL NOT NULL
            )
            """
        )
        conn.commit()
        _local.conn = conn
    return conn


def _make_key(provider: str, model: str, messages: list) -> str:
    """Deterministic cache key from provider + model + messages content."""
    payload = json.dumps(
        {"provider": provider, "model": model, "messages": messages},
        sort_keys=True,
        ensure_ascii=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def get_cached(provider: str, model: str, messages: list) -> Optional[str]:
    """Return cached response or None."""
    key = _make_key(provider, model, messages)
    try:
        conn = _get_conn()
        row = conn.execute(
            "SELECT response FROM llm_cache WHERE cache_key = ?", (key,)
        ).fetchone()
        if row:
            logger.debug("LLM cache HIT  [%s/%s] %s", provider, model, key[:12])
            return row[0]
        logger.debug("LLM cache MISS [%s/%s] %s", provider, model, key[:12])
    except Exception:
        logger.warning("LLM cache read error", exc_info=True)
    return None


def put_cached(provider: str, model: str, messages: list, response: str) -> None:
    """Store a response in the cache."""
    key = _make_key(provider, model, messages)
    try:
        conn = _get_conn()
        conn.execute(
            """
            INSERT OR REPLACE INTO llm_cache (cache_key, provider, model, response, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (key, provider, model, response, time.time()),
        )
        conn.commit()
    except Exception:
        logger.warning("LLM cache write error", exc_info=True)


def cache_stats() -> dict:
    """Return basic cache statistics."""
    try:
        conn = _get_conn()
        total = conn.execute("SELECT COUNT(*) FROM llm_cache").fetchone()[0]
        by_provider = conn.execute(
            "SELECT provider, model, COUNT(*) FROM llm_cache GROUP BY provider, model"
        ).fetchall()
        return {
            "total_entries": total,
            "by_model": [
                {"provider": p, "model": m, "count": c} for p, m, c in by_provider
            ],
        }
    except Exception:
        return {"total_entries": 0, "by_model": []}


def clear_cache(provider: Optional[str] = None, model: Optional[str] = None) -> int:
    """Clear cache entries. Returns number of rows deleted."""
    try:
        conn = _get_conn()
        if provider and model:
            cur = conn.execute(
                "DELETE FROM llm_cache WHERE provider = ? AND model = ?",
                (provider, model),
            )
        elif provider:
            cur = conn.execute(
                "DELETE FROM llm_cache WHERE provider = ?", (provider,)
            )
        else:
            cur = conn.execute("DELETE FROM llm_cache")
        conn.commit()
        return cur.rowcount
    except Exception:
        logger.warning("LLM cache clear error", exc_info=True)
        return 0
