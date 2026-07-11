#!/usr/bin/env python3
"""
TokenSave — Context optimization for LLM API calls.

Core usage:
    from tokensave import OpenAI     # drop-in for openai.OpenAI

CLI:
    tokensave setup    Detect environment, check dependencies
    tokensave proxy    Start/stop compression proxy (power-user)
    tokensave analyze  Analyze session for token waste
"""

import argparse
import logging
import sys
from pathlib import Path

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


def cmd_analyze(args):
    """Analyze a session for token waste."""
    from .session_reader import read_session
    from .analyzer import run_analysis, format_output, list_detectors
    from .analyzer.detectors import _ as _load_detectors  # noqa: F401 — triggers registration
    from .advisor import generate_prompts

    path = args.path or None
    detectors = args.detectors.split(",") if args.detectors else None

    session = read_session(path)
    if session is None:
        print("No session found.", file=sys.stderr)
        if path:
            print(f"  (tried: {path})", file=sys.stderr)
        else:
            print("  (tried: ~/.hermes/state.db and ~/.hermes/sessions/)", file=sys.stderr)
            print("  Specify a path: tokensave analyze <file.json|session_id|directory/>", file=sys.stderr)
        sys.exit(1)

    wastes = run_analysis(session, detectors=detectors)
    output = format_output(session, wastes)
    print(output)

    if wastes:
        prompts = generate_prompts(wastes)
        if prompts:
            print()
            for i, prompt in enumerate(prompts[:3], 1):
                print(f"Send to your agent ({i}/{len(prompts)}): \"{prompt}\"")
                if i < len(prompts):
                    print()


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

    a = sub.add_parser("analyze", help="Analyze session for token waste")
    a.add_argument(
        "path", nargs="?", default=None,
        help="Session file (.json), directory, session ID, or omit for auto-detect"
    )
    a.add_argument(
        "--detectors", "-d", default=None,
        help="Comma-separated detector names (default: all)"
    )

    args = parser.parse_args()
    if args.command == "setup":
        cmd_setup(args)
    elif args.command == "proxy":
        cmd_proxy(args)
    elif args.command == "analyze":
        cmd_analyze(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
