"""Tests for the waste analyzer engine and detectors."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tokensave.session_reader import Session, read_session
from tokensave.analyzer import (
    Waste,
    Detector,
    run_analysis,
    format_output,
    list_detectors,
    register_detector,
    _registry,
)


class TestWasteDataclass(unittest.TestCase):
    def test_creation(self):
        w = Waste(
            pattern="test_pattern",
            tokens_wasted=100,
            count=3,
            description="test description",
        )
        self.assertEqual(w.pattern, "test_pattern")
        self.assertEqual(w.tokens_wasted, 100)
        self.assertEqual(w.count, 3)
        self.assertEqual(w.confidence, 0.8)


class TestDetectorRegistry(unittest.TestCase):
    def setUp(self):
        # Save registry state
        self._saved = dict(_registry)

    def tearDown(self):
        # Restore registry state
        _registry.clear()
        _registry.update(self._saved)

    def test_register_detector(self):
        class TestDet(Detector):
            name = "test_reg_detector"
            description = "A test detector"

            def detect(self, session):
                return []

        self.assertIn("test_reg_detector", _registry)
        self.assertEqual(_registry["test_reg_detector"], TestDet)

    def test_list_detectors(self):
        names = list_detectors()
        # Should have at least the 4 built-in detectors
        self.assertGreaterEqual(len(names), 4)
        for expected in [
            "duplicate_tool_calls",
            "context_bloat",
            "model_mismatch",
            "heartbeat_waste",
        ]:
            self.assertIn(expected, names)


class TestDetectorBase(unittest.TestCase):
    def test_not_implemented(self):
        class Incomplete(Detector):
            name = "incomplete"
            description = "missing detect method"

        with self.assertRaises(NotImplementedError):
            Incomplete().detect(Session(id="test"))


class TestRunAnalysis(unittest.TestCase):
    def setUp(self):
        # Create a simple test session
        self.session = Session(
            id="test_session",
            model="claude-sonnet-5",
            messages=[
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"},
            ],
            message_count=2,
            input_tokens=50,
        )

    def test_empty_wastes(self):
        # Session with minimal messages should produce no waste
        s = Session(id="test", model="claude-haiku-4.5", messages=[], input_tokens=0)
        wastes = run_analysis(s)
        self.assertEqual(len(wastes), 0)
        # But context_bloat may fire on empty — update: context_bloat needs messages
        self.assertEqual(len(wastes), 0)

    def test_filter_detectors(self):
        wastes = run_analysis(self.session, detectors=["duplicate_tool_calls"])
        # Only duplicate detector ran
        for w in wastes:
            self.assertIn(w.pattern, ["duplicate_tool_calls", "near_duplicate_tool_calls"])

    def test_unknown_detector_ignored(self):
        wastes = run_analysis(self.session, detectors=["nonexistent_detector"])
        self.assertEqual(len(wastes), 0)


class TestFormatOutput(unittest.TestCase):
    def setUp(self):
        self.session = Session(
            id="test_123",
            model="claude-sonnet",
            messages=[],
            input_tokens=10000,
            output_tokens=2000,
            cost_usd=0.05,
        )

    def test_no_waste(self):
        output = format_output(self.session, [])
        self.assertIn("No significant waste detected", output)
        self.assertIn("test_123", output)

    def test_with_waste(self):
        wastes = [
            Waste(
                pattern="duplicate_tool_calls",
                tokens_wasted=3000,
                count=5,
                description="read_file called 5x with same path",
            ),
        ]
        output = format_output(self.session, wastes)
        self.assertIn("25% avoidable", output)
        self.assertIn("duplicate_tool_calls", output)
        self.assertIn("read_file called 5x", output)

    def test_output_max_wastes(self):
        wastes = [
            Waste(pattern=f"waste_{i}", tokens_wasted=100 * (5 - i), count=1, description=f"desc {i}")
            for i in range(10)
        ]
        output = format_output(self.session, wastes)
        # Should show at most 3 wastes
        lines = output.split("\n")
        waste_lines = [l for l in lines if l.strip().startswith(("1.", "2.", "3."))]
        self.assertLessEqual(len(waste_lines), 3)
        # Should not show 4.
        self.assertNotIn("  4.", output)

    def test_cost_fallback(self):
        s = Session(id="t", messages=[], input_tokens=1_000_000)
        output = format_output(s, [])
        # With 1M tokens and cost_usd=0, estimates ~$1.00 using conservative rate
        self.assertIn("~$1.00", output)
        self.assertIn("No significant waste detected", output)


class TestDuplicateDetector(unittest.TestCase):
    def test_exact_duplicate_detection(self):
        """Session with a file read twice."""
        msgs = [
            {"role": "user", "content": "Read config"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "c1",
                        "type": "function",
                        "function": {
                            "name": "read_file",
                            "arguments": '{"path": "/a/b.py"}',
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "c1",
                "tool_name": "read_file",
                "content": "x = 1\ny = 2",
            },
            {"role": "user", "content": "Read config again"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "c2",
                        "type": "function",
                        "function": {
                            "name": "read_file",
                            "arguments": '{"path": "/a/b.py"}',
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "c2",
                "tool_name": "read_file",
                "content": "x = 1\ny = 2",
            },
        ]
        session = Session(
            id="dup_test",
            model="claude-sonnet-5",
            messages=msgs,
            message_count=len(msgs),
            input_tokens=200,
        )
        wastes = run_analysis(session, detectors=["duplicate_tool_calls"])
        dup_wastes = [w for w in wastes if w.pattern == "duplicate_tool_calls"]
        self.assertEqual(len(dup_wastes), 1)
        self.assertEqual(dup_wastes[0].pattern, "duplicate_tool_calls")
        self.assertGreater(dup_wastes[0].tokens_wasted, 0)

    def test_no_duplicates(self):
        msgs = [
            {"role": "user", "content": "Read a"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "c1",
                        "type": "function",
                        "function": {
                            "name": "read_file",
                            "arguments": '{"path": "/a.py"}',
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "c1",
                "tool_name": "read_file",
                "content": "a content",
            },
            {"role": "user", "content": "Read b"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "c2",
                        "type": "function",
                        "function": {
                            "name": "read_file",
                            "arguments": '{"path": "/b.py"}',
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "c2",
                "tool_name": "read_file",
                "content": "b content",
            },
        ]
        session = Session(
            id="no_dup",
            model="claude-sonnet-5",
            messages=msgs,
            message_count=len(msgs),
            input_tokens=200,
        )
        wastes = run_analysis(session, detectors=["duplicate_tool_calls"])
        dup_wastes = [w for w in wastes if w.pattern == "duplicate_tool_calls"]
        # No exact duplicates — only near-duplicates may fire
        # (read_file called 2x total, which is below near-dup threshold of 3)
        self.assertEqual(len(dup_wastes), 0)


class TestContextBloatDetector(unittest.TestCase):
    def test_large_session_bloat(self):
        """Session with 50+ messages triggers bloat detection."""
        msgs = []
        for i in range(60):
            msgs.append({"role": "user", "content": f"question {i}"})
            msgs.append({"role": "assistant", "content": f"answer {i}"})
        session = Session(
            id="big_session",
            model="claude-sonnet-5",
            messages=msgs,
            message_count=len(msgs),
            input_tokens=50000,
        )
        wastes = run_analysis(session, detectors=["context_bloat"])
        # Should at least find the general bloat
        self.assertTrue(len(wastes) > 0)

    def test_small_session_no_bloat(self):
        """Small session shouldn't trigger general bloat."""
        msgs = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
        session = Session(
            id="small",
            model="claude-haiku-4.5",
            messages=msgs,
            message_count=2,
            input_tokens=30,
        )
        wastes = run_analysis(session, detectors=["context_bloat"])
        # May find small things but not general bloat at confidence >= 0.4
        bloat_wastes = [w for w in wastes if "25%" in w.description]
        self.assertEqual(len(bloat_wastes), 0)


class TestModelMismatchDetector(unittest.TestCase):
    def test_expensive_simple_queries(self):
        """Simple queries on opus should be flagged."""
        msgs = [
            {"role": "user", "content": "What is 2+2?"},
            {"role": "assistant", "content": "4"},
            {"role": "user", "content": "What day is it?"},
            {"role": "assistant", "content": "It depends on your timezone."},
        ]
        session = Session(
            id="mismatch_test",
            model="claude-opus-4-8",
            messages=msgs,
            message_count=len(msgs),
            input_tokens=100,
        )
        wastes = run_analysis(session, detectors=["model_mismatch"])
        self.assertTrue(len(wastes) > 0)

    def test_cheap_model_no_flag(self):
        """Haiku shouldn't trigger mismatch."""
        msgs = [
            {"role": "user", "content": "What is 2+2?"},
            {"role": "assistant", "content": "4"},
        ]
        session = Session(
            id="haiku_test",
            model="claude-haiku-4.5",
            messages=msgs,
            message_count=2,
            input_tokens=20,
        )
        wastes = run_analysis(session, detectors=["model_mismatch"])
        self.assertEqual(len(wastes), 0)


class TestHeartbeatDetector(unittest.TestCase):
    def test_cron_session_detected(self):
        """Session with 'cron' in ID should be flagged."""
        msgs = [
            {"role": "user", "content": "still running?"},
            {"role": "assistant", "content": "Yes, still running."},
        ]
        session = Session(
            id="cron_daily_check_001",
            model="claude-opus-4-8",
            messages=msgs,
            message_count=2,
            input_tokens=30,
        )
        wastes = run_analysis(session, detectors=["heartbeat_waste"])
        self.assertTrue(len(wastes) > 0)

    def test_normal_session_not_flagged(self):
        """Normal session without idle patterns shouldn't trigger."""
        msgs = [
            {"role": "user", "content": "Write a function to sort a list"},
            {"role": "assistant", "content": "Here's the code..."},
        ]
        session = Session(
            id="normal_session_123",
            model="claude-opus-4-8",
            messages=msgs,
            message_count=2,
            input_tokens=50,
        )
        wastes = run_analysis(session, detectors=["heartbeat_waste"])
        self.assertEqual(len(wastes), 0)


class TestIntegration(unittest.TestCase):
    """End-to-end test with the sample fixture."""

    def test_sample_session(self):
        fixture = Path(__file__).parent / "fixtures" / "sample_session.json"
        self.assertTrue(fixture.exists(), f"Fixture not found: {fixture}")

        session = read_session(fixture)
        self.assertIsNotNone(session)
        self.assertEqual(session.model, "claude-opus-4-8")
        self.assertGreater(session.tool_call_count, 0)

        wastes = run_analysis(session)
        # Should find at least duplicate_tool_calls (read_file called 2x)
        dup = [w for w in wastes if "duplicate_tool_calls" in w.pattern]
        self.assertTrue(len(dup) > 0, f"Expected duplicate_tool_calls, got: {[w.pattern for w in wastes]}")

        output = format_output(session, wastes)
        self.assertIn("Session", output)
        self.assertIn("avoidable", output)


if __name__ == "__main__":
    unittest.main()
