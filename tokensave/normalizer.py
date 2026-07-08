"""
Lightweight prompt normalization — zero-dependency, always-on.
Runs before compression so the compressor gets cleaner input.
"""

import re
from typing import Any


def normalize_messages(messages: list[dict]) -> list[dict]:
    """Clean up message content: trim whitespace, collapse blank lines.

    Lossless — never changes the semantic content, only formatting.
    """
    cleaned = []
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            content = content.strip()
            # Collapse 3+ consecutive newlines to 2 (preserves paragraph breaks)
            content = re.sub(r"\n{3,}", "\n\n", content)
            # Trim trailing whitespace per line
            content = re.sub(r"[ \t]+\n", "\n", content)
        cleaned.append({**msg, "content": content})
    return cleaned
