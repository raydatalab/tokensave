"""Tests: CLI entry point."""

from unittest.mock import patch
from tokensave.cli import main


def test_cli_help_not_crash():
    """CLI shows help without error."""
    with patch("sys.argv", ["tokensave", "--help"]):
        try:
            main()
        except SystemExit as e:
            # argparse exits with 0 on --help, non-zero on error
            assert e.code == 0 or e.code is None


def test_cli_version_not_crash():
    """CLI shows version without error."""
    with patch("sys.argv", ["tokensave", "--version"]):
        try:
            main()
        except SystemExit as e:
            assert e.code == 0 or e.code is None
