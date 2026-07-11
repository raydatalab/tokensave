"""Tests for advisor.py — prompt generator."""
import unittest

from tokensave.advisor import generate_prompts, _extract_tool_name, _extract_cheaper_model
from tokensave.analyzer import Waste


class TestExtractToolName(unittest.TestCase):
    def test_read_file(self):
        desc = "read_file called 5x with identical arguments"
        self.assertEqual(_extract_tool_name(desc), "read_file")

    def test_terminal(self):
        desc = "terminal was invoked repeatedly"
        self.assertEqual(_extract_tool_name(desc), "terminal")

    def test_unknown_tool(self):
        desc = "some unknown tool pattern"
        self.assertEqual(_extract_tool_name(desc), "the tool")


class TestExtractCheaperModel(unittest.TestCase):
    def test_extract_after_switch_to(self):
        desc = "Switch scheduled tasks to deepseek-v3 (save ~$0.16/1M input tokens)."
        result = _extract_cheaper_model(desc)
        self.assertEqual(result, "deepseek-v3")

    def test_extract_haiku(self):
        desc = "Use claude-haiku-4.5 instead of claude-opus-4-8"
        result = _extract_cheaper_model(desc)
        self.assertIn("haiku", result.lower())

    def test_no_model_found(self):
        desc = "Some description without model names"
        result = _extract_cheaper_model(desc)
        self.assertEqual(result, "a cheaper model")


class TestGeneratePrompts(unittest.TestCase):
    def test_empty_wastes(self):
        prompts = generate_prompts([])
        self.assertEqual(prompts, [])

    def test_single_waste(self):
        wastes = [
            Waste(
                pattern="duplicate_tool_calls",
                tokens_wasted=4800,
                count=8,
                description="read_file called 8x with identical arguments /app/config.py",
            )
        ]
        prompts = generate_prompts(wastes)
        self.assertEqual(len(prompts), 1)
        self.assertIn("read_file", prompts[0])
        self.assertIn("8x", prompts[0])

    def test_multiple_wastes(self):
        wastes = [
            Waste(
                pattern="duplicate_tool_calls",
                tokens_wasted=4000,
                count=8,
                description="read_file called 8x",
            ),
            Waste(
                pattern="context_bloat",
                tokens_wasted=3000,
                count=1,
                description="Session has 100 messages. ~25% overhead.",
            ),
            Waste(
                pattern="model_mismatch",
                tokens_wasted=2000,
                count=5,
                description="5 simple queries on claude-opus-4-8. Switch to claude-haiku-4.5.",
            ),
        ]
        prompts = generate_prompts(wastes)
        # Should generate up to 3 prompts
        self.assertLessEqual(len(prompts), 3)
        self.assertGreaterEqual(len(prompts), 1)

    def test_dedup_similar_patterns(self):
        """Near-duplicate and exact duplicate should only produce one prompt."""
        wastes = [
            Waste(pattern="duplicate_tool_calls", tokens_wasted=100, count=2, description="d1"),
            Waste(pattern="near_duplicate_tool_calls", tokens_wasted=50, count=3, description="d2"),
        ]
        prompts = generate_prompts(wastes)
        self.assertEqual(len(prompts), 1)

    def test_prompt_is_one_paragraph(self):
        """Each prompt should be a single paragraph."""
        wastes = [
            Waste(pattern="context_bloat", tokens_wasted=7000, count=1, description="Test"),
        ]
        prompts = generate_prompts(wastes)
        for p in prompts:
            self.assertNotIn("\n\n", p, f"Prompt has blank line: {p}")

    def test_fallback_template(self):
        """Unknown pattern should use fallback template."""
        wastes = [
            Waste(
                pattern="custom_waste",
                tokens_wasted=500,
                count=1,
                description="Some custom waste finding",
            )
        ]
        prompts = generate_prompts(wastes)
        self.assertEqual(len(prompts), 1)
        self.assertIn("custom_waste", prompts[0])


if __name__ == "__main__":
    unittest.main()
