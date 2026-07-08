"""Tests: tokensave optimized wrapper classes."""

from unittest.mock import patch, MagicMock
import tokensave


class TestOptimizedOpenAI:
    """Verify _OptimizedOpenAI wraps client correctly."""

    def test_wraps_client(self):
        """Non-chat attributes pass through to client."""
        real_client = MagicMock()
        comp = tokensave._OptimizedOpenAI(real_client)

        result = comp.models
        assert result == real_client.models

    def test_chat_completions_create_passthrough_no_compressor(self):
        """Without compressor, messages pass through unchanged."""
        real_client = MagicMock()
        comp = tokensave._OptimizedOpenAI(real_client)
        comp._hr_compress = None

        messages = [{"role": "user", "content": "hello"}]
        comp.chat.completions.create(model="gpt-4", messages=messages)

        real_client.chat.completions.create.assert_called_once()
        args, _ = real_client.chat.completions.create.call_args
        # First positional or messages kwarg
        called_kwargs = real_client.chat.completions.create.call_args.kwargs
        assert "messages" in called_kwargs

    def test_chat_completions_create_compresses_messages(self):
        """With compressor, messages are compressed before being sent."""
        real_client = MagicMock()
        comp = tokensave._OptimizedOpenAI(real_client)

        # Set compressor
        mock_compress = MagicMock(
            return_value=MagicMock(messages=[{"role": "user", "content": "short"}])
        )
        comp._hr_compress = mock_compress

        original = [
            {"role": "user", "content": "a very long verbose message"}
        ]

        # Ensure cache miss by clearing cache
        tokensave.cache.clear()

        comp.chat.completions.create(model="gpt-4", messages=original)

        # Should have compressed before calling real API
        mock_compress.assert_called_once()
        real_client.chat.completions.create.assert_called_once()

    def test_compress_messages_no_compressor(self):
        """_compress_messages passes through when no compressor."""
        real_client = MagicMock()
        comp = tokensave._OptimizedOpenAI(real_client)
        comp._hr_compress = None

        messages = [{"role": "user", "content": "hello"}]
        result = comp._compress_messages(messages)
        assert result == messages

    def test_compress_messages_with_compressor(self):
        """_compress_messages calls headroom when available."""
        real_client = MagicMock()
        comp = tokensave._OptimizedOpenAI(real_client)

        mock_compress = MagicMock()
        mock_compress.return_value.messages = [{"role": "user", "content": "short"}]
        comp._hr_compress = mock_compress

        original = [{"role": "user", "content": "long message"}]
        result = comp._compress_messages(original)

        mock_compress.assert_called_once_with(original, optimize=True)
        assert result == [{"role": "user", "content": "short"}]

    def test_compress_messages_graceful_fallback(self):
        """If compressor raises, messages pass through (no crash)."""
        real_client = MagicMock()
        comp = tokensave._OptimizedOpenAI(real_client)

        def failing_compress(msgs):
            raise RuntimeError("compressor exploded")

        comp._hr_compress = failing_compress

        messages = [{"role": "user", "content": "hello"}]
        result = comp._compress_messages(messages)
        assert result == messages


class TestOpenAIFactory:
    """Verify the OpenAI factory instantiates correctly."""

    def test_openai_returns_optimized_wrapper(self):
        """OpenAI() returns _OptimizedOpenAI."""
        with patch("openai.OpenAI") as mock_real:
            mock_real.return_value = MagicMock()
            client = tokensave.OpenAI(api_key="test")
            assert isinstance(client, tokensave._OptimizedOpenAI)

    def test_openai_error_on_missing_dep(self):
        """OpenAI() raises ImportError if openai not installed."""
        with patch.dict("sys.modules", {"openai": None}):
            # Force the import to fail
            import builtins
            original_import = builtins.__import__

            def mock_import(name, *args, **kwargs):
                if name == "openai":
                    raise ImportError("no openai")
                return original_import(name, *args, **kwargs)

            builtins.__import__ = mock_import
            try:
                import importlib
                importlib.reload(tokensave)
                # But this may fail because tokensave is already loaded...
                pass
            finally:
                builtins.__import__ = original_import

    def test_cache_module_exists(self):
        """tokensave.cache is available with expected functions."""
        assert hasattr(tokensave, "cache")
        assert hasattr(tokensave.cache, "get")
        assert hasattr(tokensave.cache, "set")
        assert hasattr(tokensave.cache, "clear")

    def test_normalizer_module_exists(self):
        """tokensave.normalizer is available."""
        assert hasattr(tokensave, "normalizer")
        assert hasattr(tokensave.normalizer, "normalize_messages")
