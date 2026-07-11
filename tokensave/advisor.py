"""
Advisor: generates actionable prompts from waste analysis.

Each prompt is a paragraph the user can paste to their agent.
The agent should be able to read it and change its behavior.
"""

from tokensave.analyzer import Waste

# ── Prompt templates per waste pattern ──────────────────────────────────
# Each template takes the top waste and returns a prompt string.
# Tone: direct, actionable, one paragraph. Written for the AGENT to read.

_TEMPLATES: dict[str, str] = {
    "duplicate_tool_calls": (
        "Before calling any tool, check if you already have the result in a "
        "previous message. You called {tool_name} {count}x with identical arguments. "
        "Keep a mental note of what files you have already read and what commands "
        "you have already run. If you need to re-read something, state explicitly "
        "why the previous read was insufficient."
    ),
    "near_duplicate_tool_calls": (
        "You called the same tool {count}x with different arguments. Before each "
        "tool call, ask yourself: do I already have this information from an earlier "
        "call? Batch related queries into a single call where possible. When reading "
        "files, use line ranges instead of reading the entire file."
    ),
    "context_bloat": (
        "Your context window is filling up with redundant information. {detail} "
        "When reading files, always specify line ranges (e.g., lines 1-100) instead "
        "of reading entire files. After you get tool output, check if you already "
        "have the same information from an earlier response. If a conversation has "
        "more than 50 messages, consider asking the user if you can start a fresh "
        "session to reduce context noise."
    ),
    "model_mismatch": (
        "When answering simple questions — short factual queries, yes/no questions, "
        "quick lookups — use a cheaper model like {cheaper_model} instead of the "
        "current model. {count} simple queries in this session were answered with an "
        "expensive model. Reserve expensive models for complex reasoning, multi-step "
        "tool use, and tasks that genuinely need deep thinking."
    ),
    "heartbeat_waste": (
        "For scheduled tasks, health checks, and status polling, use the cheapest "
        "available model (like {cheaper_model}). These tasks don't need frontier "
        "reasoning — they just need basic status awareness. If a check returns "
        "'nothing new' or 'still running', the next check should be identical but "
        "cost 10-100x less. Consider batching multiple checks into one message."
    ),
}

# Fallback for any waste pattern without a specific template
_FALLBACK_TEMPLATE = (
    "Reduce your token usage by addressing this: {pattern}. {description}"
)


def _extract_tool_name(description: str) -> str:
    """Extract the most-mentioned tool name from a waste description."""
    import re

    words = re.findall(r"\b([a-z_]+)\b", description.lower())
    # Common tool names to look for
    tool_keywords = [
        "read_file", "search_files", "terminal", "bash", "execute",
        "write_file", "patch", "todo", "web_search", "web_fetch",
    ]
    for tk in tool_keywords:
        if tk in words:
            return tk
    return "the tool"


def _extract_cheaper_model(description: str) -> str:
    """Extract cheaper model name from description.

    Prefers model names that appear after hint phrases like 'switch to' or 'use'.
    """
    import re

    # Models to look for (cheaper tier: haiku, nano, mini, flash, v3)
    cheap_pattern = (
        r"(claude-haiku[\w.-]*|gpt-[\w.-]*(?:nano|mini)|deepseek-v\d(?!\d)"
        r"|gemini[\w.-]*flash[\w.-]*)"
    )

    # Strategy: find model name appearing after "to <model>" pattern
    to_match = re.search(
        r"\bto\s+([a-z][a-z0-9.-]*[a-z0-9])",
        description,
        re.IGNORECASE,
    )
    if to_match:
        candidate = to_match.group(1)
        if re.match(cheap_pattern, candidate, re.IGNORECASE):
            return candidate

    # Fallback: find any cheap model mentioned, prefer shortest match
    matches = list(re.finditer(cheap_pattern, description, re.IGNORECASE))
    if matches:
        # Return shortest match (less likely to be the expensive variant)
        shortest = min(matches, key=lambda m: len(m.group(1)))
        return shortest.group(1)

    return "a cheaper model"


def generate_prompts(wastes: list[Waste]) -> list[str]:
    """Generate 1-3 paste-to-agent prompt strings from waste findings.

    Each prompt is one paragraph the user can copy and send to their agent.
    """
    if not wastes:
        return []

    prompts = []
    seen_patterns: set[str] = set()

    for w in wastes:
        pattern = w.pattern
        # Only one prompt per pattern type
        base_pattern = pattern.replace("near_", "")
        if base_pattern in seen_patterns:
            continue
        seen_patterns.add(base_pattern)

        template = _TEMPLATES.get(pattern, _FALLBACK_TEMPLATE)

        # Build template variables
        tool_name = _extract_tool_name(w.description)
        cheaper_model = _extract_cheaper_model(w.description)

        prompt = template.format(
            pattern=pattern,
            count=w.count,
            tool_name=tool_name,
            description=w.description,
            cheaper_model=cheaper_model,
            detail=w.description,
        )

        prompts.append(prompt)

        if len(prompts) >= 3:
            break

    return prompts
