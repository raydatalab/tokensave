"""Tests: rule-based message compression."""

from tokensave.compressors.rules import compress_messages


def test_short_conversation_passthrough():
    """Short conversations should pass through unchanged."""
    msgs = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"},
        {"role": "assistant", "content": "Hi there!"},
    ]
    result = compress_messages(msgs)
    assert len(result) == 3
    assert result[0]["content"] == "You are a helpful assistant."
    assert result[1]["content"] == "Hello!"


def test_long_conversation_truncated():
    """Long conversations compress old history."""
    msgs = [{"role": "system", "content": "Be concise."}]
    for i in range(30):
        msgs.append({"role": "user", "content": f"Q{i}"})
        msgs.append({"role": "assistant", "content": f"A{i}"})

    result = compress_messages(msgs)
    # Should have: system + summary + last 10 exchanges (20 msgs) = 22
    assert len(result) == 22, f"Expected 22 msgs, got {len(result)}"
    # First user message should be from the kept portion (turn 10+)
    # Last user message should be Q29
    assert "Q29" in result[-2]["content"], "Last turn should be preserved"


def test_long_message_capped():
    """Individual messages over 6000 chars get truncated."""
    text = "x" * 8000
    msgs = [{"role": "user", "content": text}]
    result = compress_messages(msgs)
    assert len(result[0]["content"]) < 6500
    assert "[... truncated from" in result[0]["content"]


def test_empty_messages():
    """Empty message list returns empty."""
    assert compress_messages([]) == []


def test_no_content_field():
    """Messages without content field are handled."""
    msgs = [{"role": "user"}]
    result = compress_messages(msgs)
    assert len(result) == 1
    assert result[0]["content"] == ""
