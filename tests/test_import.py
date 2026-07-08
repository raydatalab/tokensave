"""Tests: package import, version, and basic structure."""

import tokensave


def test_version():
    """Package exports a version string."""
    assert hasattr(tokensave, "__version__")
    assert isinstance(tokensave.__version__, str)
    assert tokensave.__version__ == "0.3.0"


def test_openai_class_exported():
    """tokensave.OpenAI is the main user-facing class."""
    assert hasattr(tokensave, "OpenAI")
    assert callable(tokensave.OpenAI)


def test_logger_exists():
    """Package sets up a module-level logger."""
    assert tokensave.logger is not None
    assert tokensave.logger.name == "tokensave"
