"""
Local SQLite cache for LLM API responses — exact-match only.

Uses SHA-256 hash of (model + messages + key params) as cache key.
Zero-config — uses ~/.tokensave/cache.db automatically.

For semantic/fuzzy caching, headroom's SemanticCache provides a more
robust implementation (embedding-based, BM25, hybrid scorers).
"""

import hashlib
import json
import logging
import sqlite3
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger("tokensave.cache")

CACHE_DIR = Path.home() / ".tokensave"
CACHE_FILE = CACHE_DIR / "cache.db"

_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    """Get a thread-local SQLite connection. Creates tables on first use."""
    if not hasattr(_local, "conn") or _local.conn is None:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(CACHE_FILE), timeout=5)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS responses (
                key TEXT PRIMARY KEY,
                model TEXT NOT NULL,
                response TEXT NOT NULL,
                created_at REAL NOT NULL,
                hits INTEGER DEFAULT 1
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_responses_model ON responses(model)"
        )
        conn.commit()
        _local.conn = conn
    return _local.conn


def _cache_key(model: str, messages: list, **params) -> str:
    """Generate a deterministic SHA-256 cache key from request parameters."""
    raw = json.dumps(
        {
            "model": model,
            "messages": messages,
            "temperature": params.get("temperature"),
            "top_p": params.get("top_p"),
            "frequency_penalty": params.get("frequency_penalty"),
            "presence_penalty": params.get("presence_penalty"),
            "stop": params.get("stop"),
            "tools": params.get("tools"),
            "response_format": params.get("response_format"),
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def get(model: str, messages: list, **params) -> Any | None:
    """Exact-match cache lookup. Returns deserialized response dict or None."""
    key = _cache_key(model, messages, **params)
    try:
        conn = _get_conn()
        row = conn.execute(
            "SELECT response, hits FROM responses WHERE key = ?", (key,)
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE responses SET hits = hits + 1 WHERE key = ?", (key,)
            )
            conn.commit()
            logger.debug(f"cache HIT — key={key[:12]}… (hits={row[1]})")
            return json.loads(row[0])
    except Exception as e:
        logger.debug(f"cache read error: {e}")
    return None


def set(model: str, messages: list, response_body: dict, **params) -> None:
    """Store a response in the exact-match cache."""
    key = _cache_key(model, messages, **params)
    try:
        import time

        conn = _get_conn()
        conn.execute(
            """INSERT OR REPLACE INTO responses (key, model, response, created_at)
               VALUES (?, ?, ?, ?)""",
            (key, model, json.dumps(response_body), time.time()),
        )
        conn.commit()
        logger.debug(f"cache SET — key={key[:12]}…")
    except Exception as e:
        logger.debug(f"cache write error: {e}")


def stats() -> dict:
    """Return cache statistics."""
    try:
        conn = _get_conn()
        total = conn.execute("SELECT COUNT(*) FROM responses").fetchone()[0]
        total_hits = conn.execute(
            "SELECT COALESCE(SUM(hits - 1), 0) FROM responses"
        ).fetchone()[0]
        return {"exact_entries": total, "exact_repeat_hits": total_hits}
    except Exception:
        return {"exact_entries": 0, "exact_repeat_hits": 0}


def clear() -> None:
    """Clear all cached responses."""
    try:
        conn = _get_conn()
        conn.execute("DELETE FROM responses")
        conn.commit()
        logger.info("cache cleared")
    except Exception as e:
        logger.warning(f"cache clear error: {e}")
