"""
Multi-format session reader for Hermes agent sessions.

Primary source: ~/.hermes/state.db (SQLite)
Secondary source: ~/.hermes/sessions/*.json (error request dumps)
"""

import json
import logging
import os
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger("tokensave.session_reader")

HERMES_DIR = Path.home() / ".hermes"
DEFAULT_DB = HERMES_DIR / "state.db"
DEFAULT_SESSIONS_DIR = HERMES_DIR / "sessions"


@dataclass
class Session:
    """Normalized session data from any source."""

    id: str
    model: str = "unknown"
    messages: list[dict] = field(default_factory=list)
    message_count: int = 0
    tool_call_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    started_at: str = ""
    source: str = ""  # "sqlite" or "json"

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


# ── SQLite reader ──────────────────────────────────────────────────────


def _read_from_sqlite(
    db_path: str | Path, session_id: str | None = None
) -> Session | None:
    """Read a session from Hermes state.db."""
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
    except Exception as e:
        logger.debug(f"Failed to open state.db: {e}")
        return None

    try:
        # Get session metadata
        if session_id:
            row = conn.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM sessions ORDER BY started_at DESC LIMIT 1"
            ).fetchone()

        if row is None:
            conn.close()
            return None

        row_dict = dict(row)

        session = Session(
            id=row_dict.get("id", ""),
            model=row_dict.get("model", "unknown"),
            message_count=row_dict.get("message_count", 0) or 0,
            tool_call_count=row_dict.get("tool_call_count", 0) or 0,
            input_tokens=row_dict.get("input_tokens", 0) or 0,
            output_tokens=row_dict.get("output_tokens", 0) or 0,
            cost_usd=row_dict.get("estimated_cost_usd", 0.0) or 0.0,
            started_at=str(row_dict.get("started_at", "")),
            source="sqlite",
        )

        # Load messages
        msgs = conn.execute(
            "SELECT role, content, tool_calls, tool_name, token_count "
            "FROM messages WHERE session_id = ? AND active = 1 "
            "ORDER BY id",
            (session.id,),
        ).fetchall()

        for m in msgs:
            msg = {"role": m["role"], "content": m["content"] or ""}
            if m["tool_calls"]:
                try:
                    msg["tool_calls"] = json.loads(m["tool_calls"])
                except json.JSONDecodeError:
                    msg["tool_calls_raw"] = m["tool_calls"]
            if m["tool_name"]:
                msg["tool_name"] = m["tool_name"]
            if m["token_count"]:
                msg["token_count"] = m["token_count"]
            session.messages.append(msg)

        conn.close()
        return session

    except Exception as e:
        logger.debug(f"Error reading from state.db: {e}")
        try:
            conn.close()
        except Exception:
            pass
        return None


# ── JSON reader (error request dumps) ──────────────────────────────────


def _read_from_json(filepath: str | Path) -> Session | None:
    """Read a session from a Hermes error request dump JSON file."""
    filepath = Path(filepath)
    try:
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.debug(f"Failed to read JSON session: {e}")
        return None

    if not isinstance(data, dict):
        return None

    request = data.get("request", {})
    body = request.get("body", {})
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except json.JSONDecodeError:
            body = {}

    messages = body.get("messages", [])
    model = body.get("model", "unknown")

    # Extract session ID from filename
    session_id = filepath.stem
    if session_id.startswith("request_dump_"):
        # request_dump_20260710_214623_e95335_20260710_214753_463451
        # → 20260710_214623_e95335
        parts = session_id.replace("request_dump_", "").split("_")
        session_id = "_".join(parts[:3]) if len(parts) >= 3 else session_id

    # Count tool calls
    tool_call_count = 0
    for m in messages:
        if m.get("role") == "assistant" and "tool_calls" in m:
            tool_call_count += len(m["tool_calls"])

    # Estimate tokens — rough, since dumps don't have usage data
    total_chars = sum(len(json.dumps(m, default=str)) for m in messages)
    estimated_input_tokens = max(1, total_chars // 4)

    return Session(
        id=session_id,
        model=model,
        messages=messages,
        message_count=len(messages),
        tool_call_count=tool_call_count,
        input_tokens=estimated_input_tokens,
        output_tokens=0,  # error dumps don't have responses
        cost_usd=0.0,
        source="json",
    )


# ── Auto-discovery ─────────────────────────────────────────────────────


def _find_latest_json(directory: str | Path) -> Path | None:
    """Find the most recent JSON session file in a directory."""
    directory = Path(directory)
    if not directory.is_dir():
        return None
    json_files = sorted(directory.glob("*.json"), key=os.path.getmtime, reverse=True)
    # Filter out sessions.json (index file)
    json_files = [f for f in json_files if f.name != "sessions.json"]
    return json_files[0] if json_files else None


def read_session(path: str | Path | None = None) -> Session | None:
    """Read a session from the given path, auto-detecting format.

    Args:
        path: File path, directory, session ID, or None (auto-find).

    Returns:
        Session or None if no session found.
    """
    if path is None:
        # Auto-find: try SQLite first, then JSON directory
        if DEFAULT_DB.exists():
            session = _read_from_sqlite(DEFAULT_DB)
            if session:
                return session
        latest_json = _find_latest_json(DEFAULT_SESSIONS_DIR)
        if latest_json:
            return _read_from_json(latest_json)
        return None

    path = Path(path)

    if path.is_dir():
        # Directory: find latest JSON
        latest = _find_latest_json(path)
        if latest:
            return _read_from_json(latest)
        return None

    if path.suffix == ".json":
        return _read_from_json(path)

    if path.suffix == ".db":
        return _read_from_sqlite(path)

    # Treat as session ID — try SQLite
    if DEFAULT_DB.exists():
        session = _read_from_sqlite(DEFAULT_DB, str(path))
        if session:
            return session

    # Last resort: try as file path
    if path.exists():
        return _read_from_json(path)

    return None
