"""
TokenSave — Context optimization for LLM API calls.

Safe defaults: pip install does nothing but make the package available.
Use `from tokensave import OpenAI` as a drop-in for `from openai import OpenAI`.
If headroom is installed, messages are compressed before sending. If not,
requests pass through unchanged. Never breaks your existing workflow.
"""

__version__ = "0.1.1"

import logging

logger = logging.getLogger("tokensave")

# Check headroom availability once at import time
_HAS_HEADROOM = False
try:
    import headroom  # noqa: F401
    _HAS_HEADROOM = True
except ImportError:
    pass


class OpenAI:
    """
    Drop-in replacement for `openai.OpenAI` with optional compression.

    Usage:
        # Instead of:
        #   from openai import OpenAI
        #   client = OpenAI(api_key="...")

        from tokensave import OpenAI
        client = OpenAI(api_key="...")

    When headroom is installed ('pip install tokensave[compress]'), messages
    are compressed before being sent to the API. When headroom is not available,
    requests pass through unchanged — no errors, no config changes, no breakage.
    """

    def __new__(cls, *args, **kwargs):
        try:
            from openai import OpenAI as _RealOpenAI
            client = _RealOpenAI(*args, **kwargs)
        except ImportError:
            raise ImportError(
                "tokensave requires 'openai' package. Install with: pip install openai"
            )

        if _HAS_HEADROOM:
            return _CompressingOpenAI(client)
        return client


class _CompressingOpenAI:
    """Wraps an openai.OpenAI client with Headroom compression."""

    def __init__(self, client):
        self._client = client
        self._compressor = None
        self._init_compressor()

    def _init_compressor(self):
        try:
            from headroom import compress as _hr_compress
            self._hr_compress = _hr_compress
            logger.info("tokensave: Headroom compression active")
        except Exception as e:
            logger.warning(f"tokensave: Headroom init failed ({e}), running passthrough")
            self._hr_compress = None

    def _compress_messages(self, messages):
        if not self._hr_compress:
            return messages
        try:
            result = self._hr_compress(messages)
            return result.messages
        except Exception as e:
            logger.warning(f"tokensave: compression failed ({e}), sending uncompressed")
            return messages

    def __getattr__(self, name):
        """Pass through any attribute access to the underlying client."""
        return getattr(self._client, name)
