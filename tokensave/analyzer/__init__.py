"""
Token waste analyzer engine.

Runs detectors against a session and produces ranked waste findings.
"""

import logging
from dataclasses import dataclass, field

from tokensave.session_reader import Session

logger = logging.getLogger("tokensave.analyzer")


@dataclass
class Waste:
    """A single waste finding from a detector."""

    pattern: str          # "duplicate_tool_calls", "context_bloat", etc.
    tokens_wasted: int    # estimated tokens wasted
    count: int            # number of occurrences
    description: str      # human-readable, one line
    confidence: float = 0.8  # 0.0-1.0, how confident we are this is real waste


class Detector:
    """Base class for waste detectors.

    Subclass and override detect(). Registration is automatic.
    """

    name: str = "base"
    description: str = ""

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.name != "base":
            register_detector(cls)

    def detect(self, session: Session) -> list[Waste]:
        """Analyze session and return waste findings."""
        raise NotImplementedError


# ── Detector registry ──────────────────────────────────────────────────

_registry: dict[str, type[Detector]] = {}


def register_detector(cls: type[Detector]) -> None:
    """Register a detector class."""
    _registry[cls.name] = cls
    logger.debug(f"Registered detector: {cls.name}")


def get_detector(name: str) -> type[Detector] | None:
    """Get a detector class by name."""
    return _registry.get(name)


def list_detectors() -> list[str]:
    """List registered detector names."""
    return sorted(_registry.keys())


# ── Analysis engine ────────────────────────────────────────────────────


def run_analysis(
    session: Session, detectors: list[str] | None = None
) -> list[Waste]:
    """Run all (or specified) detectors against a session.

    Returns wastes sorted by (tokens_wasted * confidence) descending.
    """
    if detectors is None:
        detector_names = list_detectors()
    else:
        # Validate requested detector names
        available = set(_registry.keys())
        detector_names = [d for d in detectors if d in available]
        unknown = set(detectors) - available
        if unknown:
            logger.warning(f"Unknown detectors: {unknown}")

    wastes: list[Waste] = []
    for name in detector_names:
        cls = _registry.get(name)
        if cls is None:
            continue
        try:
            detector = cls()
            results = detector.detect(session)
            if results:
                wastes.extend(results)
        except Exception as e:
            logger.warning(f"Detector '{name}' failed: {e}")

    # Sort by estimated impact (tokens_wasted * confidence)
    wastes.sort(key=lambda w: w.tokens_wasted * w.confidence, reverse=True)
    return wastes


# ── Output formatter ───────────────────────────────────────────────────

# Separator between waste description and per-occurrence detail
_WASTE_SEP = "\n      "


def format_output(session: Session, wastes: list[Waste]) -> str:
    """Format analysis results as ≤5 lines of output.

    Returns a string suitable for terminal display.
    """
    total_tokens = session.total_tokens
    cost = session.cost_usd

    # Cost line
    if cost > 0:
        cost_str = f"~${cost:.2f}"
    elif total_tokens > 0:
        # Estimate cost roughly: assume $1/1M tokens (conservative blend)
        cost_est = total_tokens / 1_000_000 * 1.0
        cost_str = f"~${cost_est:.2f}"
    else:
        cost_str = "unknown"

    # Waste summary
    total_wasted = sum(w.tokens_wasted for w in wastes)
    if total_tokens > 0 and total_wasted > 0:
        waste_pct = min(99, int(total_wasted / total_tokens * 100))
        waste_str = f"{waste_pct}% avoidable"
    elif total_wasted > 0:
        waste_str = f"~{total_wasted:,} tokens waste"
    else:
        waste_str = ""

    lines = []
    if waste_str:
        lines.append(
            f"Session {session.id}: {total_tokens:,} tokens, {cost_str}, {waste_str}."
        )
    else:
        lines.append(
            f"Session {session.id}: {total_tokens:,} tokens, {cost_str}. No significant waste detected."
        )

    if not wastes:
        return "\n".join(lines)

    # Top wastes (up to 3)
    lines.append("")
    lines.append("Top wastes:")
    for i, w in enumerate(wastes[:3], 1):
        desc = w.description.replace("\n", _WASTE_SEP)
        lines.append(f"  {i}. {w.pattern} ({w.count}x): ~{w.tokens_wasted:,} tokens — {desc}")

    return "\n".join(lines)


# ── Auto-load detectors on import ──────────────────────────────────────
# At bottom to avoid circular imports (detectors import Detector from here).
try:
    from tokensave.analyzer import detectors as _detectors  # noqa: F401
except ImportError:
    pass
