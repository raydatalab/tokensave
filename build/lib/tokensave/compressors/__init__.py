"""Compressor backends. Primary: headroom. Future: llmlingua, selective-context."""

import importlib
import logging

logger = logging.getLogger("tokensave")


def check_headroom() -> bool:
    """Check if headroom is installed and importable."""
    try:
        import headroom  # noqa: F401
        return True
    except ImportError:
        return False


def get_headroom_version() -> str:
    """Get headroom version string."""
    try:
        import headroom
        return getattr(headroom, "__version__", "unknown")
    except ImportError:
        return "not installed"


def wrap_command(tool: str, compress_refs: bool = True, keep_active: bool = True) -> list[str]:
    """Return the headroom wrap command args for a given tool."""
    cmd = ["headroom", "wrap", tool]
    if compress_refs:
        cmd.append("--compress-refs")
    if keep_active:
        cmd.append("--keep-active")
    return cmd


AVAILABLE_COMPRESSORS = {"headroom": check_headroom()}


def list_compressors() -> list[dict]:
    """List available compressors and their status."""
    return [
        {
            "name": "headroom",
            "available": check_headroom(),
            "version": get_headroom_version(),
            "description": "Content-aware context compression. 60-95% token reduction.",
            "default": True,
        },
    ]
