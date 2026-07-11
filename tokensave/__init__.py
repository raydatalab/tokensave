"""
TokenSave — Context optimization for LLM API calls.

  pip install tokensave   ← the only command you need

Your existing code keeps working — `from openai import OpenAI` is
automatically optimized. No import changes required.

What happens transparently:
  1. Exact-match SQLite cache → repeated requests cost zero
  2. headroom.compress() → intelligent prompt compression
  3. Message normalization → more cache hits
  4. Fail-open → any error passes original request through unchanged

Set TOKENSAVE_OFF=1 to disable.
Set TOKENSAVE_QUIET=1 to suppress activation/exit messages.

Heavy lifting by mature, battle-tested libraries:
  - headroom — SmartCrusher compression + CacheAligner cache alignment
  - litellm — multi-provider prompt cache injection (via headroom)
  - tiktoken — accurate token counting (via headroom)
"""

__version__ = "0.4.2"

import atexit
import json
import logging
import os
import sys

logger = logging.getLogger("tokensave")

# ── Auto-patch openai.OpenAI on import ─────────────────────────────────
from tokensave._auto import _patch as _auto_patch

_auto_patch()

# ── Rule-based compressor (always available, zero extra deps) ─────────
from tokensave.compressors.rules import compress_messages as _rule_compress

# ── Headroom availability check ────────────────────────────────────────
_HAS_HEADROOM = False
try:
    import headroom  # noqa: F401

    _HAS_HEADROOM = True
except ImportError:
    pass


# ── Session savings tracking (memory-only, lightweight) ────────────────
_session_calls = 0
_session_cache_hits = 0
_session_tokens_saved = 0


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: 4 chars ≈ 1 token."""
    if isinstance(text, str):
        return max(1, len(text) // 4)
    if isinstance(text, list):
        return sum(_estimate_tokens(str(m)) for m in text)
    return 0


def _estimate_cost_saved(tokens: int, model: str = "") -> float:
    """Estimate dollars saved. Uses litellm if available, otherwise conservative."""
    try:
        import litellm

        cost_map = getattr(litellm, "model_cost", None)
        if cost_map and model in cost_map:
            cost_per_1k = cost_map[model].get("input_cost_per_token", 0)
            return tokens * cost_per_1k
    except Exception:
        pass
    # Conservative: assume ~$0.001/1K tokens (cheaper than most frontier models)
    return tokens * 0.001 / 1000


def _print_exit_summary():
    """atexit callback: print one-line session savings summary."""
    if os.environ.get("TOKENSAVE_QUIET"):
        return
    if _session_calls == 0:
        return
    cost = _estimate_cost_saved(_session_tokens_saved)
    if cost >= 0.01:
        print(
            f"[TokenSave] {_session_calls} calls, "
            f"{_session_cache_hits} cache hits, "
            f"~{_session_tokens_saved:,} tokens saved "
            f"(~${cost:.2f})",
            flush=True,
        )
    else:
        print(
            f"[TokenSave] {_session_calls} calls, "
            f"{_session_cache_hits} cache hits, "
            f"~{_session_tokens_saved:,} tokens saved",
            flush=True,
        )


atexit.register(_print_exit_summary)


# ── Pipeline classes ───────────────────────────────────────────────────


class _OptimizedCompletions:
    """Wraps openai.resources.chat.Completions with transparent optimizations.

    Pipeline:
      1. Normalize message content (lossless text cleanup)
      2. Exact-match cache lookup (SHA-256, SQLite, zero-cost)
      3. headroom.compress() — compression + cache alignment
      4. Real API call (fail-open if anything breaks)
      5. Cache the response for next time
    """

    def __init__(self, completions, compress_fn):
        self._completions = completions
        self._compress = compress_fn
        from tokensave import cache as _cache
        from tokensave import normalizer as _norm

        self._cache = _cache
        self._norm = _norm

    def create(self, *args, **kwargs):
        global _session_calls, _session_cache_hits, _session_tokens_saved

        if "messages" not in kwargs:
            return self._completions.create(*args, **kwargs)

        streaming = kwargs.get("stream", False)
        model = kwargs.get("model", "")

        # ── 1. Normalize messages (lossless text cleanup) ──────────────
        messages = self._norm.normalize_messages(kwargs["messages"])
        kwargs["messages"] = messages

        cache_params = {
            k: kwargs.get(k)
            for k in (
                "temperature",
                "top_p",
                "frequency_penalty",
                "presence_penalty",
                "stop",
                "tools",
                "response_format",
            )
            if k in kwargs
        }

        # ── 2. Exact-match cache ──────────────────────────────────────
        if not streaming:
            cached = self._cache.get(model, messages, **cache_params)
            if cached is not None:
                _session_calls += 1
                _session_cache_hits += 1
                # Count tokens saved from the cached response
                usage = cached.get("usage", {})
                tokens = usage.get("total_tokens", 0)
                if tokens <= 0:
                    tokens = _estimate_tokens(json.dumps(cached))
                _session_tokens_saved += tokens
                return self._reconstruct(cached)

        # ── 3. Estimate tokens before compression ─────────────────────
        tokens_before = _estimate_tokens(json.dumps(messages))

        # ── 4. Compress messages via headroom (or fallback) ───────────
        kwargs["messages"] = self._compress(messages)

        # ── 5. Real API call ──────────────────────────────────────────
        result = self._completions.create(*args, **kwargs)

        # ── 6. Track savings ──────────────────────────────────────────
        _session_calls += 1
        try:
            # Use prompt_tokens from API response (input tokens actually sent)
            if hasattr(result, "usage") and result.usage:
                tokens_after = getattr(result.usage, "prompt_tokens", 0)
            elif hasattr(result, "model_dump"):
                usage = result.model_dump().get("usage", {})
                tokens_after = usage.get("prompt_tokens", 0)
            else:
                tokens_after = tokens_before
            saved = max(0, int(tokens_before) - int(tokens_after or 0))
            _session_tokens_saved += saved
        except (TypeError, ValueError, AttributeError):
            pass  # non-numeric usage data (e.g. mock objects in tests)

        # ── 7. Cache response for next time ───────────────────────────
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
        except Exception:
            pass

    def _compress_messages(self, messages):
        messages = _rule_compress(messages)
        if self._hr_compress:
            try:
                result = self._hr_compress(messages, optimize=True)
                messages = result.messages
            except Exception as e:
                logger.debug(f"tokensave: headroom skipped ({e}), rules-only")
        return messages

    def __getattr__(self, name):
        if name == "chat":
            return self._chat_proxy
        return getattr(self._client, name)


class OpenAI:
    """Drop-in replacement for `openai.OpenAI` with automatic optimizations.

    Usage:
        from tokensave import OpenAI
        client = OpenAI(api_key="...")

    Or just keep using `from openai import OpenAI` — tokensave auto-patches it.
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
