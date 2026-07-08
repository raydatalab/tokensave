"""
TokenSave — Context optimization for LLM API calls.

Safe defaults: pip install does nothing but make the package available.
Use `from tokensave import OpenAI` as a drop-in for `from openai import OpenAI`.
Messages are compressed before sending. Never breaks your existing workflow.
"""

__version__ = "0.1.3"

import logging

logger = logging.getLogger("tokensave")

# Check headroom availability once at import time
_HAS_HEADROOM = False
try:
    import headroom  # noqa: F401
    _HAS_HEADROOM = True
except ImportError:
    pass


class _CompressingCompletions:
    """Wraps openai.resources.chat.Completions to compress messages on create()."""

    def __init__(self, completions, compress_fn):
        self._completions = completions
        self._compress = compress_fn

    def create(self, *args, **kwargs):
        if "messages" in kwargs:
            kwargs["messages"] = self._compress(kwargs["messages"])
        return self._completions.create(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._completions, name)


class _CompressingChat:
    """Wraps openai.resources.chat.Chat to inject compression into completions."""

    def __init__(self, chat, compress_fn):
        self._chat = chat
        self._completions = _CompressingCompletions(chat.completions, compress_fn)

    def __getattr__(self, name):
        if name == "completions":
            return self._completions
        return getattr(self._chat, name)


class _CompressingOpenAI:
    """Wraps an openai.OpenAI client with Headroom compression."""

    def __init__(self, client):
        self._client = client
        self._hr_compress = None
        self._init_compressor()
        # Override .chat with a compressed-aware proxy
        self._chat_proxy = _CompressingChat(client.chat, self._compress_messages)

    def _init_compressor(self):
        try:
            from headroom import compress as _hr_compress
            self._hr_compress = _hr_compress
            logger.info("tokensave: Headroom compression active")
        except Exception as e:
            logger.warning(
                f"tokensave: Headroom init failed ({e}), running passthrough"
            )
            self._hr_compress = None

    def _compress_messages(self, messages):
        if not self._hr_compress:
            return messages
        try:
            result = self._hr_compress(messages)
            return result.messages
        except Exception as e:
            logger.warning(
                f"tokensave: compression failed ({e}), sending uncompressed"
            )
            return messages

    def __getattr__(self, name):
        if name == "chat":
            return self._chat_proxy
        return getattr(self._client, name)


class OpenAI:
    """
    Drop-in replacement for `openai.OpenAI` with optional compression.

    Usage:
        # Instead of:
        #   from openai import OpenAI
        #   client = OpenAI(api_key="...")

        from tokensave import OpenAI
        client = OpenAI(api_key="...")

    When headroom is installed, messages are compressed before being sent to the API.
    When headroom is not available, requests pass through unchanged — no errors,
    no config changes, no breakage.
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
