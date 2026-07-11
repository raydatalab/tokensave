"""Tests for session_reader.py"""
import json
import os
import tempfile
import unittest
from pathlib import Path

from tokensave.session_reader import (
    Session,
    _read_from_json,
    read_session,
)


class TestSessionDataclass(unittest.TestCase):
    def test_total_tokens(self):
        s = Session(id="test", input_tokens=100, output_tokens=50)
        self.assertEqual(s.total_tokens, 150)

    def test_defaults(self):
        s = Session(id="test")
        self.assertEqual(s.model, "unknown")
        self.assertEqual(s.messages, [])
        self.assertEqual(s.message_count, 0)
        self.assertEqual(s.source, "")


class TestReadFromJSON(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def _write_json(self, name, data):
        path = Path(self.tmpdir) / name
        with open(path, "w") as f:
            json.dump(data, f)
        return path

    def test_parse_valid_session(self):
        from tokensave.session_reader import _read_from_json

        data = {
            "timestamp": "2026-01-01",
            "session_id": "abc",
            "reason": "test",
            "request": {
                "method": "POST",
                "url": "http://test",
                "headers": {},
                "body": {
                    "model": "claude-sonnet-5",
                    "messages": [
                        {"role": "system", "content": "You are helpful."},
                        {"role": "user", "content": "Hello"},
                        {"role": "assistant", "content": "Hi there!"},
                    ],
                },
            },
            "error": {"type": "test", "message": "test error"},
        }
        path = self._write_json("session.json", data)
        session = _read_from_json(path)

        self.assertIsNotNone(session)
        self.assertEqual(session.model, "claude-sonnet-5")
        self.assertEqual(session.message_count, 3)
        self.assertEqual(session.source, "json")
        self.assertGreater(session.input_tokens, 0)

    def test_parse_session_with_tool_calls(self):
        data = {
            "timestamp": "2026-01-01",
            "session_id": "abc",
            "reason": "test",
            "request": {
                "method": "POST",
                "url": "http://test",
                "headers": {},
                "body": {
                    "model": "claude-opus-4-8",
                    "messages": [
                        {"role": "user", "content": "Read file config.py"},
                        {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "read_file",
                                        "arguments": '{"path": "config.py"}',
                                    },
                                }
                            ],
                        },
                        {
                            "role": "tool",
                            "tool_call_id": "call_1",
                            "content": "key=value",
                        },
                    ],
                },
            },
            "error": {"type": "test", "message": "err"},
        }
        path = self._write_json("session.json", data)
        session = _read_from_json(path)

        self.assertIsNotNone(session)
        self.assertEqual(session.tool_call_count, 1)
        self.assertEqual(session.message_count, 3)

    def test_bad_json_returns_none(self):
        # Write raw invalid text, not JSON-encoded
        path = Path(self.tmpdir) / "bad.json"
        with open(path, "w") as f:
            f.write("not valid json---")
        session = _read_from_json(path)
        self.assertIsNone(session)

    def test_missing_file_returns_none(self):
        session = _read_from_json("/nonexistent/path.json")
        self.assertIsNone(session)

    def test_minimal_session(self):
        """Session with bare-minimum fields."""
        data = {
            "request": {
                "method": "POST",
                "url": "http://test",
                "headers": {},
                "body": {"model": "gpt-5", "messages": []},
            }
        }
        path = self._write_json("minimal.json", data)
        session = _read_from_json(path)
        self.assertIsNotNone(session)
        self.assertEqual(session.message_count, 0)
        self.assertEqual(session.tool_call_count, 0)

    def test_string_body(self):
        """Body is a JSON string instead of dict."""
        data = {
            "request": {
                "method": "POST",
                "url": "http://test",
                "headers": {},
                "body": '{"model": "claude-haiku-4.5", "messages": [{"role": "user", "content": "hi"}]}',
            }
        }
        path = self._write_json("string_body.json", data)
        session = _read_from_json(path)
        self.assertIsNotNone(session)
        self.assertEqual(session.model, "claude-haiku-4.5")
        self.assertEqual(session.message_count, 1)


class TestReadSessionAutoDetect(unittest.TestCase):
    def test_nonexistent_path(self):
        session = read_session("/nonexistent/path/")
        self.assertIsNone(session)

    def test_directory_with_json(self):
        from tokensave.session_reader import read_session

        with tempfile.TemporaryDirectory() as d:
            data = {
                "timestamp": "2026-01-01",
                "session_id": "test",
                "reason": "test",
                "request": {
                    "method": "POST",
                    "url": "http://test",
                    "headers": {},
                    "body": {
                        "model": "deepseek-v4",
                        "messages": [{"role": "user", "content": "test"}],
                    },
                },
                "error": {"type": "test", "message": "err"},
            }
            path = Path(d) / "dump.json"
            with open(path, "w") as f:
                json.dump(data, f)
            session = read_session(d)
            self.assertIsNotNone(session)
            self.assertEqual(session.model, "deepseek-v4")

    def test_specific_json_file(self):
        with tempfile.TemporaryDirectory() as d:
            data = {
                "request": {
                    "method": "POST",
                    "url": "http://test",
                    "headers": {},
                    "body": {
                        "model": "claude-sonnet-5",
                        "messages": [{"role": "user", "content": "hello"}],
                    },
                }
            }
            path = Path(d) / "test.json"
            with open(path, "w") as f:
                json.dump(data, f)
            session = read_session(str(path))
            self.assertIsNotNone(session)
            self.assertEqual(session.model, "claude-sonnet-5")


if __name__ == "__main__":
    unittest.main()
