"""
Duplicate tool call detector.

Finds identical (and near-identical) tool calls within a session.
Waste = (N-1) × estimated response tokens per duplicate group.
"""

import json
import logging
from collections import Counter

from tokensave.analyzer import Detector, Waste
from tokensave.session_reader import Session

logger = logging.getLogger("tokensave.analyzer.duplicates")


def _normalize_args(args_str: str) -> str:
    """Normalize tool call arguments for fuzzy comparison.

    Strips whitespace differences that don't change semantics.
    """
    if not args_str:
        return ""
    try:
        args = json.loads(args_str)
        return json.dumps(args, sort_keys=True)
    except (json.JSONDecodeError, TypeError):
        # Non-JSON args — strip whitespace
        return " ".join(args_str.split())


def _estimate_response_tokens(messages: list[dict], tool_name: str) -> int:
    """Estimate average response tokens for a given tool."""
    responses = []
    for m in messages:
        if m.get("role") == "tool" and m.get("tool_name") == tool_name:
            content = str(m.get("content", ""))
            responses.append(max(1, len(content) // 4))
    if responses:
        return sum(responses) // len(responses)
    # Fallback: use average across all tool responses
    all_responses = [
        max(1, len(str(m.get("content", ""))) // 4)
        for m in messages
        if m.get("role") == "tool"
    ]
    return sum(all_responses) // len(all_responses) if all_responses else 100


class DuplicateDetector(Detector):
    name = "duplicate_tool_calls"
    description = "Detect identical or near-identical tool calls"

    def detect(self, session: Session) -> list[Waste]:
        messages = session.messages
        if not messages:
            return []

        # Collect tool calls with (name, normalized_args)
        exact_calls: list[tuple[str, str]] = []
        fuzzy_calls: list[tuple[str, str]] = []

        for m in messages:
            if m.get("role") != "assistant":
                continue
            tool_calls = m.get("tool_calls", [])
            if not tool_calls:
                continue
            for tc in tool_calls:
                fn = tc.get("function", {})
                name = fn.get("name", "")
                args = fn.get("arguments", "")
                if not name:
                    continue
                norm_args = _normalize_args(args)
                exact_calls.append((name, norm_args))
                # Fuzzy: just the tool name (same tool called repeatedly)
                fuzzy_calls.append((name, ""))

        wastes = []

        # Exact duplicates
        exact_counts = Counter(exact_calls)
        total_exact_waste = 0
        total_exact_count = 0
        dup_groups_exact = []

        for (name, args), count in exact_counts.items():
            if count >= 2:
                resp_tokens = _estimate_response_tokens(messages, name)
                wasted = (count - 1) * resp_tokens
                total_exact_waste += wasted
                total_exact_count += count
                dup_groups_exact.append((name, count, wasted))

        if dup_groups_exact:
            dup_groups_exact.sort(key=lambda x: x[2], reverse=True)
            top = dup_groups_exact[0]
            wastes.append(Waste(
                pattern="duplicate_tool_calls",
                tokens_wasted=total_exact_waste,
                count=len(dup_groups_exact),
                description=(
                    f"{top[0]} called {top[1]}x with identical arguments "
                    f"({len(dup_groups_exact)} duplicate group{'s' if len(dup_groups_exact) > 1 else ''} total)"
                ),
                confidence=0.95,
            ))

        # Near-duplicates: same tool called 3+ times with different args
        name_counts = Counter(f[0] for f in exact_calls)
        high_freq = [(n, c) for n, c in name_counts.items() if c >= 3]
        if high_freq:
            high_freq.sort(key=lambda x: x[1], reverse=True)
            total_near_waste = 0
            details = []
            for name, count in high_freq[:3]:
                resp_tokens = _estimate_response_tokens(messages, name)
                # Assume ~30% of repeated calls are unnecessary (lower confidence)
                wasted = int((count - 1) * resp_tokens * 0.3)
                total_near_waste += wasted
                details.append(f"{name} {count}x")

            if total_near_waste > 0 and not dup_groups_exact:
                wastes.append(Waste(
                    pattern="near_duplicate_tool_calls",
                    tokens_wasted=total_near_waste,
                    count=sum(c for _, c in high_freq),
                    description=(
                        f"Same tool called repeatedly with different args: "
                        f"{', '.join(details)}. "
                        f"~30% of these likely return redundant data."
                    ),
                    confidence=0.5,
                ))

        return wastes
