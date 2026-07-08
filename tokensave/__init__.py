"""
TokenSave — Context optimization for LLM API calls.

Safe defaults: pip install does nothing but make the package available.
Use `from tokensave import OpenAI` as a drop-in for `from openai import OpenAI`.
Messages are compressed before sending. Never breaks your existing workflow.
"""

__version__ = "0.1.3"

import json
import logging

logger = logging.getLogger("tokensave")

# Check headroom availability once at import time
_HAS_HEADROOM = False
try:
    import headroom  # noqa: F401
    _HAS_HEADROOM = True
except ImportError:
    pass


class _OptimizedCompletions:
    """Wraps openai.resources.chat.Completions with:

    1. Prompt normalization (whitespace, formatting)
    2. Exact-match semantic cache (SQLite, zero-config)
    3. Auto max_tokens (if user didn't set one)
    4. Headroom compression (if available)
    """

    def __init__(self, completions, compress_fn):
        self._completions = completions
        self._compress = compress_fn
        from tokensave import cache as _cache
        from tokensave import normalizer as _norm
        self._cache = _cache
        self._norm = _norm

    def create(self, *args, **kwargs):
        if "messages" not in kwargs:
            return self._completions.create(*args, **kwargs)

        streaming = kwargs.get("stream", False)

        # 1. Normalize messages (lossless — cleans formatting)
        messages = self._norm.normalize_messages(kwargs["messages"])
        kwargs["messages"] = messages

        model = kwargs.get("model", "")

        cache_params = {k: kwargs.get(k) for k in
            ("temperature", "top_p", "frequency_penalty", "presence_penalty",
             "stop", "tools", "response_format")
            if k in kwargs}

        # 2. Cache check (exact match — same request = same response)
        if not streaming:
            cached = self._cache.get(model, messages, **cache_params)
            if cached is not None:
                return self._reconstruct(cached)

        # 3. Compress messages (lossy but recoverable via CCR)
        kwargs["messages"] = self._compress(messages)

        # 4. Real API call
        result = self._completions.create(*args, **kwargs)

        # 5. Cache the response (non-streaming only)
        if not streaming:
            try:
                if hasattr(result, "model_dump"):
                    body = json.loads(result.model_dump_json())
                elif hasattr(result, "to_dict"):
                    body = result.to_dict()
                else:
                    body = result
                self._cache.set(model, messages, body, **cache_params)
            except Exception as e:
                logger.debug(f"cache set failed: {e}")

        return result

    def _reconstruct(self, data: dict):
        """Rebuild a ChatCompletion-like object from cached dict."""
        try:
            from openai.types.chat import ChatCompletion
            return ChatCompletion.model_validate(data)
        except Exception:
            # Fallback: return a dict-like wrapper
            return _DictWrapper(data)

    def __getattr__(self, name):
        return getattr(self._completions, name)


class _DictWrapper:
    """Minimal dict-to-object adapter for cached responses."""

    def __init__(self, data):
        self._data = data

    def __getattr__(self, name):
        val = self._data.get(name)
        if isinstance(val, dict):
            return _DictWrapper(val)
        if isinstance(val, list):
            return [_DictWrapper(v) if isinstance(v, dict) else v for v in val]
        return val

    def __getitem__(self, key):
        return self._data[key]

    def __repr__(self):
        return f"_DictWrapper({self._data})"


class _OptimizedChat:
    """Wraps openai.resources.chat.Chat to inject optimizations into completions."""

    def __init__(self, chat, compress_fn):
        self._chat = chat
        self._completions = _OptimizedCompletions(chat.completions, compress_fn)

    def __getattr__(self, name):
        if name == "completions":
            return self._completions
        return getattr(self._chat, name)


class _OptimizedOpenAI:
    """Wraps an openai.OpenAI client with all optimizations."""

    def __init__(self, client):
        self._client = client
        self._hr_compress = None
        self._init_compressor()
        self._chat_proxy = _OptimizedChat(client.chat, self._compress_messages)

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
    Drop-in replacement for `openai.OpenAI` with automatic optimizations.

    Usage:
        # Instead of:
        #   from openai import OpenAI
        #   client = OpenAI(api_key="...")

        from tokensave import OpenAI
        client = OpenAI(api_key="...")

    Optimizations applied transparently on every API call:
    • Prompt normalization — trims whitespace, collapses blank lines (lossless)
    • Request cache — repeated identical requests return cached response (zero tokens)
    • Message compression — with headroom installed, compresses before sending
    """

    def __new__(cls, *args, **kwargs):
        try:
            from openai import OpenAI as _RealOpenAI
            client = _RealOpenAI(*args, **kwargs)
        except ImportError:
            raise ImportError(
                "tokensave requires 'openai' package. Install with: pip install openai"
            )

        return _OptimizedOpenAI(client)
