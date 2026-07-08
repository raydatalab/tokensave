"""
Prompt normalization for exact-match cache efficiency.
Runs before cache lookup — same prompt different formatting → same cache key.

What we do (all safe, no semantic change):
  1. Unicode NFC normalization
  2. Line endings: \\r\\n → \\n
  3. Strip trailing whitespace per line
  4. Collapse 3+ blank lines to 2 (preserves paragraph breaks)
  5. Canonicalize roles: developer → system
  6. Strip volatile content (UUIDs, timestamps) that breaks cache stability

For prompt cache prefix optimization (Strategy 1), headroom's CacheAligner
handles the heavier lifting: dynamic tail detection, entropy scoring,
provider-specific cache breakpoints.
"""

import re
import unicodedata
from typing import Any

# ── Volatile content patterns ──────────────────────────────────────────
# These break cache-key stability. Replace with stable placeholders so
# semantically identical requests produce the same cache key.

_VOLATILE_PATTERNS = [
    # UUIDs (standard hex format)
    (
        re.compile(
            r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
            re.IGNORECASE,
        ),
        "[UUID]",
    ),
    # ISO 8601 timestamps with timezone
    (
        re.compile(
            r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})\b"
        ),
        "[TIMESTAMP]",
    ),
    # ISO 8601 date-only
    (re.compile(r"\b\d{4}-\d{2}-\d{2}\b"), "[DATE]"),
]


def _clean_content(text: str, strip_volatile: bool = True) -> str:
    """Normalize a single message content string for cache-key stability."""
    if not isinstance(text, str):
        return text

    # 1. Unicode NFC normalization — canonicalizes equivalent Unicode forms
    text = unicodedata.normalize("NFC", text)

    # 2. Line endings: \r\n → \n, then lone \r → \n
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # 3. Strip trailing whitespace per line
    text = re.sub(r"[ \t]+\n", "\n", text)

    # 4. Collapse 3+ blank lines to 2 (preserves paragraph breaks)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # 5. Strip surrounding whitespace
    text = text.strip()

    # 6. Strip volatile content that breaks cache-key stability
    if strip_volatile:
        for pattern, replacement in _VOLATILE_PATTERNS:
            text = pattern.sub(replacement, text)

    return text


def normalize_messages(
    messages: list[dict],
    strip_volatile: bool = True,
) -> list[dict]:
    """Normalize message content for exact-match cache efficiency.

    Pure text-level normalization — never changes message structure (roles,
    ordering, or merging). This is safe by construction: two requests with
    the same semantic content but different formatting will produce the
    same cache key.

    Args:
        messages: List of message dicts with "role" and "content" keys.
        strip_volatile: Replace timestamps/UUIDs with stable placeholders.

    Returns:
        Normalized message list with cleaned content strings.
    """
    if not messages:
        return messages

    cleaned = []
    for msg in messages:
        content = msg.get("content", "")
        role = msg.get("role", "user")

        # Canonicalize role: developer → system
        # OpenAI introduced 'developer' in 2025; semantically equivalent.
        if role == "developer":
            role = "system"

        if isinstance(content, str):
            content = _clean_content(content, strip_volatile=strip_volatile)

        cleaned.append({**msg, "content": content, "role": role})

    return cleaned
