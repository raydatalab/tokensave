"""Tests: tokensave.OpenAI wrapper class."""

from unittest.mock import patch, MagicMock, ANY
import tokensave


class TestCompressingOpenAI:
    """Verify _CompressingOpenAI wraps and compresses correctly."""

    def test_wraps_client(self):
        """Non-chat attributes pass through to client."""
        real_client = MagicMock()
        comp = tokensave._CompressingOpenAI(real_client)

        # Access a non-chat attribute should reach the underlying client
        result = comp.models
        assert result == real_client.models

    def test_chat_completions_create_passthrough_no_compressor(self):
        """Without compressor, messages pass through unchanged."""
        real_client = MagicMock()
        comp = tokensave._CompressingOpenAI(real_client)
        comp._hr_compress = None  # disable compressor

        messages = [{"role": "user", "content": "hello"}]
        comp.chat.completions.create(model="gpt-4", messages=messages)

        real_client.chat.completions.create.assert_called_once_with(
            model="gpt-4", messages=messages
        )

    def test_chat_completions_create_compresses_messages(self):
        """With compressor, messages are compressed before being sent."""
        real_client = MagicMock()
        comp = tokensave._CompressingOpenAI(real_client)

        # Set up a working compressor
        mock_compress = MagicMock(return_value=MagicMock(messages=[{"role": "user", "content": "short"}]))
        comp._hr_compress = mock_compress

        original = [{"role": "user", "content": "a very long verbose message that should be compressed"}]
        comp.chat.completions.create(model="gpt-4", messages=original)

        # Verify compressor was called with original messages
        mock_compress.assert_called_once_with(original)

        # Verify API received compressed messages
        real_client.chat.completions.create.assert_called_once_with(
            model="gpt-4", messages=[{"role": "user", "content": "short"}]
        )

    def test_compress_messages_no_compressor(self):
        """_compress_messages passes through when no compressor."""
        real_client = MagicMock()
        comp = tokensave._CompressingOpenAI(real_client)
        comp._hr_compress = None

        messages = [{"role": "user", "content": "hello"}]
        result = comp._compress_messages(messages)
        assert result == messages

    def test_compress_messages_with_compressor(self):
        """_compress_messages calls headroom when available."""
        real_client = MagicMock()
        comp = tokensave._CompressingOpenAI(real_client)

        mock_compress = MagicMock()
        mock_compress.return_value.messages = [{"role": "user", "content": "short"}]
        comp._hr_compress = mock_compress

        original = [{"role": "user", "content": "long message"}]
        result = comp._compress_messages(original)

        mock_compress.assert_called_once_with(original)
        assert result == [{"role": "user", "content": "short"}]

    def test_compress_messages_graceful_fallback(self):
        """If compressor raises, messages pass through (no crash)."""
        real_client = MagicMock()
        comp = tokensave._CompressingOpenAI(real_client)

        def failing_compress(msgs):
            raise RuntimeError("compressor exploded")

        comp._hr_compress = failing_compress

        messages = [{"role": "user", "content": "hello"}]
        result = comp._compress_messages(messages)
        assert result == messages


class TestOpenAIFactory:
    """Verify the OpenAI factory instantiates correctly."""

    def test_openai_returns_compressing_wrapper(self):
        """When headroom available, OpenAI() returns _CompressingOpenAI."""
        with patch("openai.OpenAI") as mock_real:
            mock_real.return_value = MagicMock()
            # Force _HAS_HEADROOM to True
            with patch("tokensave._HAS_HEADROOM", True):
                client = tokensave.OpenAI(api_key="test")
                assert isinstance(client, tokensave._CompressingOpenAI)

    def test_openai_passthrough_no_headroom(self):
        """When headroom not available, returns raw openai client."""
        with patch("openai.OpenAI") as mock_real:
            mock_real.return_value = "raw_client"
            with patch("tokensave._HAS_HEADROOM", False):
                client = tokensave.OpenAI(api_key="test")
                assert client == "raw_client"
