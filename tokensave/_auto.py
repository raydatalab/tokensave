"""
Auto-patch openai.OpenAI with tokensave optimizations.

Triggered via .pth file on Python startup (pip install tokensave → zero code changes).
Also triggered on `import tokensave`.

Set TOKENSAVE_OFF=1 to disable.

Architecture:
  openai.OpenAI() → _TokenSaveOpenAI proxy → _OptimizedOpenAI wrapper
                                              ├── Exact-match SQLite cache
                                              └── headroom.compress() pipeline
"""

import logging
import os

logger = logging.getLogger("tokensave._auto")

_PATCHED = False


def _patch() -> bool:
    """Wrap openai.OpenAI with tokensave optimizations. Idempotent.

    Returns True if patching succeeded, False if disabled or already patched.
    """
    global _PATCHED

    if _PATCHED:
        return True

    # Honour opt-out
    if os.environ.get("TOKENSAVE_OFF"):
        logger.debug("tokensave auto-patch disabled (TOKENSAVE_OFF=1)")
        return False

    try:
        import openai
        from openai import OpenAI as _RealOpenAI
    except ImportError:
        logger.debug("tokensave: openai not installed, skipping auto-patch")
        return False

    # Prevent double-patching
    if getattr(openai.OpenAI, "__tokensave_patched__", False):
        return True

    class _TokenSaveOpenAI:
        """Transparent proxy: openai.OpenAI() → optimized client.

        Users keep writing `from openai import OpenAI; client = OpenAI(...)`.
        We intercept the constructor and return an optimized wrapper.
        """
        __tokensave_patched__ = True

        def __init__(self, *args, **kwargs):
            # Build the real OpenAI client
            real = _RealOpenAI(*args, **kwargs)
            # Wrap it with tokensave optimizations
            from tokensave import _OptimizedOpenAI

            optimized = _OptimizedOpenAI(real)
            # Bypass __setattr__ during init
            object.__setattr__(self, "_ts", optimized)

        def __getattr__(self, name):
            return getattr(object.__getattribute__(self, "_ts"), name)

        def __setattr__(self, name, value):
            try:
                target = object.__getattribute__(self, "_ts")
                setattr(target, name, value)
            except AttributeError:
                object.__setattr__(self, name, value)

        def __repr__(self):
            try:
                inner = object.__getattribute__(self, "_ts")
                return f"TokenSaveOpenAI({inner})"
            except AttributeError:
                return "TokenSaveOpenAI(uninitialized)"

    openai.OpenAI = _TokenSaveOpenAI
    _PATCHED = True
    if not os.environ.get("TOKENSAVE_QUIET"):
        print("[TokenSave] active — auto-cache + compression", flush=True)
    return True


def _is_patched() -> bool:
    """Check whether the auto-patch is active."""
    return _PATCHED
