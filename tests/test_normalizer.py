"""Tests: prompt normalization for cache-key stability (Strategy 1)."""

from tokensave.normalizer import normalize_messages, _clean_content, _VOLATILE_PATTERNS


# ── Content-level normalization ────────────────────────────────────────

class TestCleanContent:
    """Tests for _clean_content — individual message content normalization."""

    def test_unicode_nfc_normalization(self):
        """Unicode composed/decomposed forms are normalized to NFC."""
        nfc = "café"
        nfd = "café"  # NFD: two codepoints
        assert nfc != nfd
        assert _clean_content(nfc) == _clean_content(nfd)

    def test_crlf_to_lf(self):
        """Windows line endings are normalized to Unix."""
        assert _clean_content("hello\r\nworld") == "hello\nworld"

    def test_lone_cr_to_lf(self):
        """Lone \\r is normalized to \\n."""
        assert _clean_content("hello\rworld") == "hello\nworld"

    def test_mixed_line_endings(self):
        """Mixed line endings all become \\n."""
        assert _clean_content("a\r\nb\rc\r\nd") == "a\nb\nc\nd"

    def test_strip_trailing_whitespace_per_line(self):
        """Trailing spaces and tabs on each line are removed."""
        result = _clean_content("hello   \n  world\t\n  ")
        assert result == "hello\n  world"

    def test_collapse_blank_lines(self):
        """3+ consecutive blank lines collapse to 2."""
        result = _clean_content("para1\n\n\n\n\npara2")
        assert result == "para1\n\npara2"

    def test_preserve_paragraph_breaks(self):
        """Double newlines (single blank line) are preserved."""
        result = _clean_content("para1\n\npara2")
        assert result == "para1\n\npara2"

    def test_strip_surrounding_whitespace(self):
        """Leading/trailing whitespace is stripped."""
        assert _clean_content("  hello world  ") == "hello world"

    def test_uuid_stripping(self):
        """UUIDs are replaced with [UUID] placeholder."""
        result = _clean_content("Error: 550e8400-e29b-41d4-a716-446655440000 occurred")
        assert "550e8400" not in result
        assert "[UUID]" in result

    def test_multiple_uuids_stripped(self):
        """Multiple UUIDs are all replaced."""
        text = (
            "req a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11 went to "
            "session b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22"
        )
        result = _clean_content(text)
        assert result.count("[UUID]") == 2

    def test_iso_timestamp_stripped(self):
        """ISO 8601 timestamps are replaced with [TIMESTAMP]."""
        result = _clean_content("Log at 2024-01-15T14:30:00Z: done")
        assert "[TIMESTAMP]" in result
        assert "2024-01-15T14:30:00Z" not in result

    def test_iso_timestamp_with_tz_offset_stripped(self):
        """ISO 8601 with numeric TZ offset is stripped."""
        result = _clean_content("Event at 2024-06-01T08:15:30+05:00")
        assert "[TIMESTAMP]" in result

    def test_iso_date_stripped(self):
        """ISO 8601 date-only is replaced with [DATE]."""
        result = _clean_content("Report for 2024-01-15 ready")
        assert "[DATE]" in result
        assert "2024-01-15" not in result

    def test_volatile_stripping_disabled(self):
        """When strip_volatile=False, patterns are left untouched."""
        text = "UUID 550e8400-e29b-41d4-a716-446655440000 at 2024-01-15T14:30:00Z"
        result = _clean_content(text, strip_volatile=False)
        assert "550e8400" in result
        assert "2024-01-15T14:30:00Z" in result

    def test_non_string_passthrough(self):
        """Non-string content passes through unchanged."""
        assert _clean_content(None) is None
        assert _clean_content(42) == 42

    def test_empty_string(self):
        """Empty string stays empty."""
        assert _clean_content("") == ""


# ── Message-level normalization ────────────────────────────────────────

class TestNormalizeMessages:
    """Tests for normalize_messages — message list normalization."""

    def test_empty_list(self):
        """Empty message list returns empty."""
        assert normalize_messages([]) == []

    def test_basic_passthrough(self):
        """Simple conversation passes through with content cleaned."""
        msgs = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello!"},
        ]
        result = normalize_messages(msgs)
        assert len(result) == 2
        assert result[0]["role"] == "system"
        assert result[0]["content"] == "You are helpful."
        assert result[1]["role"] == "user"
        assert result[1]["content"] == "Hello!"

    def test_developer_role_canonicalized(self):
        """'developer' role is canonicalized to 'system'."""
        msgs = [
            {"role": "developer", "content": "You are a code assistant."},
            {"role": "user", "content": "Write a function."},
        ]
        result = normalize_messages(msgs)
        assert result[0]["role"] == "system"
        assert result[1]["role"] == "user"

    def test_message_order_preserved(self):
        """Message order is never changed — pure text normalization only."""
        msgs = [
            {"role": "user", "content": "Q1"},
            {"role": "system", "content": "Be helpful."},
            {"role": "assistant", "content": "A1"},
            {"role": "user", "content": "Q2"},
        ]
        result = normalize_messages(msgs)
        # Order must match exactly
        assert [m["role"] for m in result] == ["user", "system", "assistant", "user"]

    def test_consecutive_same_role_not_merged(self):
        """Consecutive same-role messages are NOT merged (structure preserved)."""
        msgs = [
            {"role": "user", "content": "First."},
            {"role": "user", "content": "Second."},
        ]
        result = normalize_messages(msgs)
        assert len(result) == 2
        assert result[0]["content"] == "First."
        assert result[1]["content"] == "Second."

    def test_preserves_extra_fields(self):
        """Extra fields in messages are preserved during normalization."""
        msgs = [
            {"role": "system", "content": "Be helpful.", "name": "sys"},
            {"role": "user", "content": "Hello!", "custom_field": "value"},
        ]
        result = normalize_messages(msgs)
        assert result[0].get("name") == "sys"
        user_msg = [m for m in result if m.get("custom_field") == "value"]
        assert len(user_msg) == 1

    def test_messages_without_content_field(self):
        """Messages missing 'content' field are handled gracefully."""
        msgs = [{"role": "user"}]
        result = normalize_messages(msgs)
        assert len(result) == 1
        assert result[0].get("content") == ""

    def test_end_to_end_cache_stability(self):
        """Two semantically identical requests normalize to the same cache key."""
        req1 = [
            {"role": "system", "content": "  Be helpful.  "},
            {"role": "user", "content": "What is 2024-06-15?"},
            {"role": "user", "content": "My session: 550e8400-e29b-41d4-a716-446655440000"},
        ]

        req2 = [
            {"role": "system", "content": "Be helpful."},
            {"role": "user", "content": "What is [DATE]?"},
            {"role": "user", "content": "My session: [UUID]"},
        ]

        result1 = normalize_messages(req1)
        result2 = normalize_messages(req2)

        assert len(result1) == len(result2) == 3
        assert result1[0]["content"] == result2[0]["content"]
        assert result1[1]["content"] == result2[1]["content"]
        assert result1[2]["content"] == result2[2]["content"]

    def test_cache_stability_across_line_endings(self):
        """CRLF and LF versions normalize identically."""
        msgs_crlf = [
            {"role": "system", "content": "Helpful.\r\nConcise."},
            {"role": "user", "content": "Hello!\r\n\r\n\r\n\r\nWorld"},
        ]
        msgs_lf = [
            {"role": "system", "content": "Helpful.\nConcise."},
            {"role": "user", "content": "Hello!\n\nWorld"},
        ]
        result_crlf = normalize_messages(msgs_crlf)
        result_lf = normalize_messages(msgs_lf)
        assert result_crlf == result_lf


# ── Volatile patterns ──────────────────────────────────────────────────

class TestVolatilePatterns:
    """Verify the volatile-content regex patterns are correct."""

    def test_uuid_pattern_matches_standard_uuids(self):
        """UUID pattern matches lowercase UUIDs."""
        pattern, _ = _VOLATILE_PATTERNS[0]
        assert pattern.search("req 550e8400-e29b-41d4-a716-446655440000 ok")

    def test_uuid_pattern_matches_uppercase_uuids(self):
        """UUID pattern matches uppercase UUIDs (case-insensitive)."""
        pattern, _ = _VOLATILE_PATTERNS[0]
        assert pattern.search("req 550E8400-E29B-41D4-A716-446655440000 ok")

    def test_uuid_pattern_does_not_match_short_hex(self):
        """UUID pattern does NOT match short hex strings."""
        pattern, _ = _VOLATILE_PATTERNS[0]
        assert not pattern.search("color #abc123")

    def test_timestamp_pattern_matches_utc(self):
        """Timestamp pattern matches UTC ISO 8601."""
        pattern, _ = _VOLATILE_PATTERNS[1]
        assert pattern.search("at 2024-01-15T14:30:00Z done")

    def test_timestamp_pattern_does_not_match_plain_time(self):
        """Timestamp pattern does NOT match bare time like '14:30:00'."""
        pattern, _ = _VOLATILE_PATTERNS[1]
        assert not pattern.search("at 14:30:00 today")

    def test_date_pattern_matches_iso_date(self):
        """Date pattern matches ISO 8601 date."""
        pattern, _ = _VOLATILE_PATTERNS[2]
        assert pattern.search("report 2024-12-31 is due")

    def test_date_pattern_does_not_match_year_only(self):
        """Date pattern requires MM-DD, not just year."""
        pattern, _ = _VOLATILE_PATTERNS[2]
        assert not pattern.search("in the year 2024 we saw")
