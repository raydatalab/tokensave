"""
Model mismatch detector.

Detects when expensive models are used for simple queries that could
be handled by cheaper alternatives.
"""

import logging

from tokensave.analyzer import Detector, Waste
from tokensave.pricing import estimate_cost, get_cheapest_equivalent, get_model_price
from tokensave.session_reader import Session

logger = logging.getLogger("tokensave.analyzer.model_mismatch")

# Thresholds
_SHORT_PROMPT_CHARS = 500       # user message below this is "short"
_SHORT_RESPONSE_CHARS = 300     # assistant response below this is "short"
_EXPENSIVE_THRESHOLD = 1.0      # $/1M input — models above this are "expensive"
_CHEAP_THRESHOLD = 0.30         # $/1M input — models below this are "cheap"


def _is_simple_query(user_msg: dict, assistant_msg: dict) -> bool:
    """Heuristic: is this a simple query that could use a cheap model?"""
    user_content = str(user_msg.get("content", ""))
    assistant_content = str(assistant_msg.get("content", ""))

    # Very short prompt + short response = likely simple
    if len(user_content) < _SHORT_PROMPT_CHARS and len(assistant_content) < _SHORT_RESPONSE_CHARS:
        return True

    # No tool calls, short response
    if not assistant_msg.get("tool_calls") and len(assistant_content) < _SHORT_RESPONSE_CHARS:
        return True

    return False


class ModelMismatchDetector(Detector):
    name = "model_mismatch"
    description = "Detect simple queries running on expensive models"

    def detect(self, session: Session) -> list[Waste]:
        messages = session.messages
        if not messages:
            return []

        model = session.model
        if model == "unknown":
            return []

        price = get_model_price(model)
        if price is None:
            return []

        input_price = price.get("input", 0)

        # Only flag if model is above the expensive threshold
        if input_price <= _EXPENSIVE_THRESHOLD:
            return []

        # Find the cheapest equivalent for comparison
        cheapest = get_cheapest_equivalent(model)
        cheapest_price = get_model_price(cheapest) if cheapest else None
        if cheapest_price is None:
            return []

        savings_per_1m = input_price - cheapest_price.get("input", 0)
        if savings_per_1m <= 0:
            return []

        # Scan for simple query patterns: user→assistant→(maybe tool)
        mismatch_count = 0
        mismatch_tokens = 0

        for i, m in enumerate(messages):
            if m.get("role") != "user":
                continue
            # Find the following assistant response
            assistant = None
            for j in range(i + 1, min(i + 3, len(messages))):
                if messages[j].get("role") == "assistant":
                    assistant = messages[j]
                    break

            if assistant and _is_simple_query(m, assistant):
                mismatch_count += 1
                user_tokens = max(1, len(str(m.get("content", ""))) // 4)
                assistant_tokens = max(1, len(str(assistant.get("content", ""))) // 4)
                mismatch_tokens += user_tokens + assistant_tokens

        if mismatch_count == 0:
            return []

        # Calculate potential savings
        wasted = int((mismatch_tokens / 1_000_000) * savings_per_1m * 1_000_000)
        # Convert to token-equivalent: savings_per_1m dollars per 1M tokens
        wasted_tokens = int(mismatch_tokens * (savings_per_1m / input_price))

        provider = price.get("provider", "unknown")

        return [Waste(
            pattern="model_mismatch",
            tokens_wasted=wasted_tokens,
            count=mismatch_count,
            description=(
                f"{mismatch_count} simple quer{'y' if mismatch_count == 1 else 'ies'} "
                f"ran on {model} (~${input_price:.2f}/1M input). "
                f"Switch to {cheapest} (~${cheapest_price['input']:.2f}/1M) "
                f"for similar queries."
            ),
            confidence=0.7,
        )]
