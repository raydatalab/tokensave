#!/usr/bin/env python3
"""
TokenSave — Context optimization for LLM API calls.

Core usage:
    from tokensave import OpenAI     # drop-in for openai.OpenAI

CLI:
    tokensave setup    Detect environment, check dependencies
    tokensave proxy    Start/stop compression proxy (power-user)
"""

import argparse
import logging
import sys

from . import __version__
from .detectors import detect_all, summary
from .compressors import check_headroom, list_compressors, get_headroom_version

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("tokensave")


def cmd_setup(args):
    """Detect environment and check dependencies. Read-only."""
    print("⚡ TokenSave\n")
    env = detect_all()
    print(summary(env))

    if check_headroom():
        print(f"\n  ✓ headroom {get_headroom_version()} — compression ready")
    else:
        print("\n  ○ headroom not installed")
        print("    pip install 'tokensave[compress]'")

    print("\n  → from tokensave import OpenAI")


def cmd_proxy(args):
    """Start/stop compression proxy."""
    from .proxy import TokenSaveProxy
    proxy = TokenSaveProxy()

    if args.action == "start":
        if proxy.start():
            print("✅ Proxy on 127.0.0.1:18787")
        else:
            print("⚠ Port 18787 in use")
    elif args.action == "stop":
        proxy.stop()
        print("🛑 Proxy stopped")


def main():
    parser = argparse.ArgumentParser(
        description="TokenSave — Context optimization for LLM API calls"
    )
    parser.add_argument("--version", action="version", version=f"TokenSave {__version__}")

    sub = parser.add_subparsers(dest="command")
    sub.add_parser("setup", help="Detect environment, check dependencies")

    p = sub.add_parser("proxy", help="Start/stop compression proxy (power-user)")
    p.add_argument("action", choices=["start", "stop"])

    args = parser.parse_args()
    if args.command == "setup":
        cmd_setup(args)
    elif args.command == "proxy":
        cmd_proxy(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
