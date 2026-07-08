"""Rule-based compression — zero-deps, mechanical, effective.

Strategy: the bulk of tokens is in long messages and deep conversation history.
We don't play with filler words. We cut where the tokens actually are.
"""

# Max characters in a single message (~1500 tokens, safe for most models)
_MAX_MSG_CHARS = 6000

# Max conversation turns to keep verbatim; older turns are summarized
_MAX_HISTORY_TURNS = 10

# ── 1. Message length capping ───────────────────────────────────────

def _cap_message_length(text: str) -> str:
    """Hard truncate a single message content."""
    if not isinstance(text, str) or len(text) <= _MAX_MSG_CHARS:
        return text
    return text[:_MAX_MSG_CHARS] + (
        f"\n[... truncated from {len(text)} chars]"
    )

# ── 2. Conversation history compression ────────────────────────────

def _compress_history(messages: list[dict]) -> list[dict]:
    """Keep system prompt + last N turns. Older turns get one-line summary."""

    # Split turns: system (index 0) vs rest
    system_msgs = [m for m in messages if m.get("role") == "system"]
    non_system = [m for m in messages if m.get("role") != "system"]

    if len(non_system) <= _MAX_HISTORY_TURNS * 2:
        return messages  # short enough

    # Keep last N exchanges (each exchange = 1 user + 1 assistant = 2 messages)
    keep = _MAX_HISTORY_TURNS * 2
    old = non_system[:-keep]
    recent = non_system[-keep:]

    # Summarize old history as a single condensed message
    old_text = " ".join(
        m.get("content", "") for m in old if isinstance(m.get("content"), str)
    )
    summary = f"[Previous conversation summarized: {len(old)} messages, ~{len(old_text)} chars]"

    return system_msgs + [
        {"role": "system", "content": summary}
    ] + recent


# ── Entry point ────────────────────────────────────────────────────

def compress_messages(messages: list[dict]) -> list[dict]:
    """Apply compression: cap message length + trim history."""
    if not messages:
        return messages

    # 1. Cap individual message length
    capped = []
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str) and content:
            content = _cap_message_length(content)
        capped.append({**msg, "content": content})

    # 2. Compress conversation history
    return _compress_history(capped)
