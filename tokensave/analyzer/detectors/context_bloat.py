"""
Context bloat detector.

Detects stale, redundant, or oversized context that inflates token usage
without contributing to the agent's effectiveness.
"""

import logging

from tokensave.analyzer import Detector, Waste
from tokensave.session_reader import Session

logger = logging.getLogger("tokensave.analyzer.context_bloat")

# Thresholds
_STALE_OVERLAP_THRESHOLD = 200   # chars — if this much content is duplicated
_OVERSIZED_TOOL_OUTPUT = 5000    # chars — tool response above this is suspect
_UNUSED_TOOL_COST = 500          # tokens — estimated cost per unused tool definition
_LARGE_SYSTEM_PROMPT = 3000      # chars — system prompt above this is suspect


def _content_overlap(a: str, b: str) -> int:
    """Count characters in 'a' that also appear in 'b' (simple line-based overlap).

    Uses line-level dedup: lines of 'a' found anywhere in 'b' count as overlap.
    """
    if not a or not b:
        return 0
    lines_a = set(line.strip() for line in a.splitlines() if len(line.strip()) > 20)
    lines_b = set(line.strip() for line in b.splitlines() if len(line.strip()) > 20)
    if not lines_a:
        return 0
    overlap = lines_a & lines_b
    return sum(len(line) for line in overlap)


class ContextBloatDetector(Detector):
    name = "context_bloat"
    description = "Detect stale context and oversized tool outputs"

    def detect(self, session: Session) -> list[Waste]:
        messages = session.messages
        if not messages:
            return []

        wastes = []

        # ── 1. Stale content: tool responses superseded by later reads ──
        stale_count = 0
        stale_tokens = 0

        # Build a set of "what the agent has seen" chronologically
        # If a later tool response contains earlier response content, the earlier is stale
        tool_responses: list[tuple[int, str, str]] = []  # (index, tool_id, content)
        for i, m in enumerate(messages):
            if m.get("role") == "tool":
                content = str(m.get("content", ""))
                tool_id = m.get("tool_call_id", str(i))
                if len(content) > _STALE_OVERLAP_THRESHOLD:
                    tool_responses.append((i, tool_id, content))

        for i in range(len(tool_responses)):
            for j in range(i + 1, len(tool_responses)):
                overlap = _content_overlap(
                    tool_responses[i][2], tool_responses[j][2]
                )
                if overlap > _STALE_OVERLAP_THRESHOLD:
                    stale_count += 1
                    stale_tokens += overlap // 4

        if stale_count >= 2:
            wastes.append(Waste(
                pattern="context_bloat",
                tokens_wasted=stale_tokens,
                count=stale_count,
                description=(
                    f"{stale_count} tool responses contain content already seen "
                    f"in earlier responses — agent read overlapping data multiple times"
                ),
                confidence=0.65,
            ))

        # ── 2. Oversized tool outputs ──
        oversized = []
        for m in messages:
            if m.get("role") != "tool":
                continue
            content = str(m.get("content", ""))
            if len(content) > _OVERSIZED_TOOL_OUTPUT:
                # Estimate: 50% of oversized output is unnecessary
                excess_chars = len(content) - _OVERSIZED_TOOL_OUTPUT
                oversized.append((m.get("tool_name", "unknown"), excess_chars))

        if oversized:
            total_excess_tokens = sum(excess // 4 for _, excess in oversized)
            top = oversized[0]
            wastes.append(Waste(
                pattern="context_bloat",
                tokens_wasted=total_excess_tokens,
                count=len(oversized),
                description=(
                    f"{len(oversized)} tool responses exceed {_OVERSIZED_TOOL_OUTPUT:,} chars "
                    f"(e.g., {top[0]}: +{top[1]:,} excess chars). "
                    f"Use line limits or output filters."
                ),
                confidence=0.55,
            ))

        # ── 3. Large system prompt + unused tools ──
        system_msg = None
        tools_available: set[str] = set()
        tools_used: set[str] = set()

        for m in messages:
            if m.get("role") == "system" and system_msg is None:
                system_msg = str(m.get("content", ""))
            if m.get("role") == "assistant":
                tool_calls = m.get("tool_calls", [])
                for tc in tool_calls:
                    fn = tc.get("function", {})
                    name = fn.get("name", "")
                    if name:
                        tools_used.add(name)

        # Extract tool names from system prompt if present
        if system_msg:
            import re
            # Look for tool definitions in system message
            found = set(re.findall(r'"name":\s*"(\w+)"', system_msg))
            if found:
                tools_available = found

        unused = tools_available - tools_used
        if unused and len(tools_available) >= 5:
            wasted = len(unused) * _UNUSED_TOOL_COST
            wastes.append(Waste(
                pattern="context_bloat",
                tokens_wasted=wasted,
                count=len(unused),
                description=(
                    f"{len(unused)} tool definitions never used in session "
                    f"({', '.join(sorted(list(unused)[:3]))}{'...' if len(unused) > 3 else ''}). "
                    f"Trim unused tools from system prompt."
                ),
                confidence=0.7,
            ))

        # ── 4. Overall session bloat ──
        # If session is large and has low tool-call density, context is likely bloated
        if session.message_count > 30:
            # High message count: estimate 25% of context is noise
            noise_tokens = int(session.input_tokens * 0.25)
            # Only report if we haven't already identified specific bloat
            if not wastes or sum(w.tokens_wasted for w in wastes) < noise_tokens * 0.5:
                wastes.append(Waste(
                    pattern="context_bloat",
                    tokens_wasted=noise_tokens,
                    count=session.message_count,
                    description=(
                        f"Session has {session.message_count} messages. "
                        f"~25% of context is conversation overhead. "
                        f"Consider periodically resetting the session."
                    ),
                    confidence=0.4,
                ))

        return wastes
