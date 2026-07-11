"""
Heartbeat / idle waste detector.

Detects cron jobs, scheduled messages, and idle polling that waste tokens
on expensive models for no-news checks.
"""

import logging
import re

from tokensave.analyzer import Detector, Waste
from tokensave.pricing import estimate_cost, get_cheapest_equivalent, get_model_price
from tokensave.session_reader import Session

logger = logging.getLogger("tokensave.analyzer.heartbeat")

# Idle-check content patterns — tight, must match genuine idle/polling phrases.
# Avoid patterns that match normal task descriptions.
_IDLE_PATTERNS = [
    re.compile(r"still (running|alive|active|working)\b", re.IGNORECASE),
    re.compile(r"\bno (changes?|updates?|news?|output)\b", re.IGNORECASE),
    re.compile(r"\bnothing (to|new|changed|happened)\b", re.IGNORECASE),
    re.compile(r"\bchecking (in|status|progress)\b", re.IGNORECASE),
    re.compile(r"\bstill nothing\b", re.IGNORECASE),
    re.compile(r"\ball (clear|good|quiet|normal)\b", re.IGNORECASE),
    re.compile(r"\b(polling|watching)\b", re.IGNORECASE),
    re.compile(r"\bany (updates?|changes?|news?)\?$", re.IGNORECASE),
    # Only match "health check" or "status check" when it's the primary topic
    re.compile(r"^(health|status)\s*check", re.IGNORECASE),
]

# File/session naming patterns that suggest cron/automated sessions
_CRON_NAME_PATTERNS = [
    re.compile(r"cron", re.IGNORECASE),
    re.compile(r"scheduled?", re.IGNORECASE),
    re.compile(r"heartbeat", re.IGNORECASE),
    re.compile(r"health.?check", re.IGNORECASE),
    re.compile(r"monitor", re.IGNORECASE),
    re.compile(r"poll", re.IGNORECASE),
]


def _looks_like_idle(content: str) -> bool:
    """Check if message content looks like an idle/polling check."""
    if not content:
        return False
    return any(p.search(content) for p in _IDLE_PATTERNS)


class HeartbeatDetector(Detector):
    name = "heartbeat_waste"
    description = "Detect cron/heartbeat/idle-check waste"

    def detect(self, session: Session) -> list[Waste]:
        messages = session.messages
        sid = session.id

        # ── 1. Check session naming for cron patterns ──
        is_cron = any(p.search(sid) for p in _CRON_NAME_PATTERNS)

        # ── 2. Check message content for idle patterns ──
        # Only check user messages — tool output matching patterns is too noisy
        idle_user_messages = 0
        idle_tokens = 0
        for m in messages:
            if m.get("role") != "user":
                continue
            content = str(m.get("content", ""))
            if _looks_like_idle(content):
                idle_user_messages += 1
                idle_tokens += max(1, len(content) // 4)

        # ── 3. Determine waste ──
        total_user_messages = sum(1 for m in messages if m.get("role") == "user")

        # Session is idle only if most USER messages look like idle checks
        is_idle_session = (
            idle_user_messages >= 2
            and total_user_messages > 0
            and idle_user_messages >= total_user_messages * 0.5
        )

        if not is_cron and not is_idle_session:
            return []

        # Calculate waste: if heartbeat, the whole session cost is potentially wasteful
        model = session.model
        cheapest = get_cheapest_equivalent(model)
        cheapest_price = get_model_price(cheapest) if cheapest else None

        wastes = []

        # Waste type A: confirmed cron/heartbeat session using expensive model
        if is_cron and cheapest_price and cheapest != model:
            price = get_model_price(model)
            if price:
                savings_per_1m = price.get("input", 0) - cheapest_price.get("input", 0)
                if savings_per_1m > 0:
                    wasted_tokens = int(
                        session.input_tokens * (savings_per_1m / price["input"])
                    )
                    wastes.append(Waste(
                        pattern="heartbeat_waste",
                        tokens_wasted=wasted_tokens,
                        count=idle_user_messages,
                        description=(
                            f"Session appears to be a cron/heartbeat using {model}. "
                            f"Switch scheduled tasks to {cheapest} "
                            f"(save ~${savings_per_1m:.2f}/1M input tokens)."
                        ),
                        confidence=0.75,
                    ))

        # Waste type B: idle checks within a normal session
        if idle_user_messages >= 2 and not is_cron:
            wastes.append(Waste(
                pattern="heartbeat_waste",
                tokens_wasted=idle_tokens,
                count=idle_user_messages,
                description=(
                    f"{idle_user_messages} user messages look like idle/status checks "
                    f"('still running?', 'any updates?'). "
                    f"Batch these or use a cheaper model."
                ),
                confidence=0.5,
            ))

        return wastes
