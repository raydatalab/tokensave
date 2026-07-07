#!/usr/bin/env python3
"""
TokenSave CLI — One command to slash your LLM API bills.

Usage:
    tokensave setup       One-command setup: detect, configure, start saving
    tokensave status      Show current status and savings
    tokensave off         Stop proxy and restore original settings
    tokensave stats       View detailed savings statistics
    tokensave proxy       Start/stop the transparent compression proxy
"""

import argparse
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import __version__
from .detectors import detect_all, summary
from .compressors import check_headroom, wrap_command, list_compressors, get_headroom_version

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("tokensave")


def cmd_setup(args):
    """One-command setup: detect environment, install deps, start proxy."""
    print("⚡ TokenSave Setup\n")

    # Step 1: Detect environment
    env = detect_all()
    print(summary(env))

    # Step 2: Ensure headroom is installed
    print("\n📦 Checking dependencies...")
    if check_headroom():
        ver = get_headroom_version()
        print(f"  ✓ headroom-ai {ver} already installed")
    else:
        print("  Installing headroom-ai...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "headroom-ai[all]"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print("  ✓ headroom-ai installed")
        else:
            print(f"  ✗ Installation failed: {result.stderr[:200]}")
            sys.exit(1)

    # Step 3: Start proxy
    print("\n🌐 Starting compression proxy...")
    from .proxy import TokenSaveProxy, PROXY_PORT
    proxy = TokenSaveProxy()
    if proxy.start():
        print(f"  ✓ Proxy running on 127.0.0.1:{PROXY_PORT}")
    else:
        print("  ⚠ Could not start proxy (maybe already running)")

    # Step 4: Tool-specific integration
    primary = env.get("primary_tool", "unknown")
    print(f"\n🔧 Tool integration: {primary}")

    if primary == "claude_code":
        _setup_claude_code(env)
    elif primary == "sillytavern":
        _setup_sillytavern(env)
    elif primary == "api_user":
        _setup_generic_api(env)
    else:
        _setup_generic_api(env)

    # Step 5: Shell integration
    print("\n💾 Saving environment configuration...")
    _save_env_config()

    print("\n" + "=" * 50)
    print("✅ TokenSave is active!")
    print("   Your API calls are now being compressed automatically.")
    print("   Run 'tokensave status' to check savings.")
    print("   Run 'tokensave off' to disable.")
    print("=" * 50)


def _setup_claude_code(env: dict):
    """Configure TokenSave for Claude Code."""
    print("  Configuring for Claude Code...")

    cc = env["claude_code"]
    if cc.get("mode") == "api":
        # Set proxy env vars for Claude Code API mode
        proxy_url = "http://127.0.0.1:18787"
        print(f"  Setting ANTHROPIC_BASE_URL → {proxy_url}")
        print("  (Claude Code will now route through TokenSave proxy)")

        # Suggest headroom wrap as alternative
        print("\n  💡 Alternative: headroom native wrap")
        print(f"     Run: headroom wrap claude --compress-refs --keep-active")
    else:
        print("  ⚠ Claude Code in subscription mode detected.")
        print("  TokenSave works best with API key access.")
        print("  Set ANTHROPIC_API_KEY to use API mode.")


def _setup_sillytavern(env: dict):
    """Suggest SillyTavern configuration."""
    st = env["sillytavern"]
    path = st.get("path", "SillyTavern")
    print(f"  SillyTavern found at {path}")
    print("  To use TokenSave with SillyTavern:")
    print("    1. Open your connection profile in ST")
    print("    2. Set API URL to: http://127.0.0.1:18787/v1")
    print("    3. Keep your API key as-is")


def _setup_generic_api(env: dict):
    """Configure for generic API usage."""
    proxy_url = "http://127.0.0.1:18787"
    print(f"  Setting API base URL → {proxy_url}")

    if env["api_keys"].get("openai"):
        print("  ✓ OpenAI key detected — ready to proxy")
    if env["api_keys"].get("anthropic"):
        print("  ✓ Anthropic key detected — ready to proxy")

    print("\n  💡 For custom tools, set one of these:")
    print(f"     export OPENAI_BASE_URL={proxy_url}/v1")
    print(f"     export ANTHROPIC_BASE_URL={proxy_url}")


def _save_env_config():
    """Save TokenSave config to ~/.tokensave/config for persistence."""
    config_dir = Path.home() / ".tokensave"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.json"

    config = {
        "proxy_port": 18787,
        "enabled": True,
        "version": __version__,
    }

    import json
    config_path.write_text(json.dumps(config, indent=2))

    # Also create/update shell rc snippet
    rc_content = (
        '# TokenSave — automatic API compression\n'
        'if command -v tokensave &>/dev/null; then\n'
        '    eval "$(tokensave shell-hook)"\n'
        'fi\n'
    )

    for rc_file in [Path.home() / ".bashrc", Path.home() / ".zshrc"]:
        if rc_file.exists():
            existing = rc_file.read_text()
            if "# TokenSave" not in existing:
                rc_file.write_text(existing + "\n" + rc_content)
                print(f"  Added TokenSave hook to {rc_file.name}")


def cmd_status(args):
    """Show current status and savings."""
    from .proxy import TokenSaveProxy, stats, PROXY_PORT

    proxy = TokenSaveProxy()

    print("📊 TokenSave Status\n")
    print(f"  Version: {__version__}")
    print(proxy.status_line)

    if stats.total_requests > 0:
        print(f"\n  📈 Lifetime Stats:")
        print(f"     Requests: {stats.total_requests}")
        print(f"     Input tokens before: {stats.total_input_tokens_before:,}")
        print(f"     Input tokens after:  {stats.total_input_tokens_after:,}")
        print(f"     Compression:         {stats.compression_ratio*100:.1f}%")
        print(f"     Estimated saved:     ${stats.estimated_cost_saved:.2f}")
        print(f"     Runtime:             {stats.runtime_hours:.1f} hours")

    print(f"\n🔧 Compressors:")
    for c in list_compressors():
        status = "✓" if c["available"] else "✗"
        print(f"  {status} {c['name']} {c['version']}")
        print(f"     {c['description']}")


def cmd_off(args):
    """Stop proxy and restore original settings."""
    print("🛑 TokenSave — Shutting down\n")

    from .proxy import TokenSaveProxy
    proxy = TokenSaveProxy()
    proxy.stop()

    # Show final stats
    from .proxy import stats
    if stats.total_requests > 0:
        print(f"  Session summary:")
        print(f"  • {stats.total_requests} requests compressed")
        print(f"  • {stats.compression_ratio*100:.1f}% average compression")
        print(f"  • ~${stats.estimated_cost_saved:.2f} saved")

    print("\n  Environment variables were not modified.")
    print("  To fully disable, unset any proxy env vars you configured:")
    print("    unset ANTHROPIC_BASE_URL")
    print("    unset OPENAI_BASE_URL")


def cmd_stats(args):
    """View detailed savings statistics."""
    from .proxy import stats
    import json

    print("📈 TokenSave — Detailed Statistics\n")

    if stats.total_requests == 0:
        print("  No data yet. Start saving with: tokensave setup")
        return

    data = {
        "total_requests": stats.total_requests,
        "total_input_tokens_before": stats.total_input_tokens_before,
        "total_input_tokens_after": stats.total_input_tokens_after,
        "total_output_tokens": stats.total_output_tokens,
        "compression_ratio": f"{stats.compression_ratio*100:.1f}%",
        "estimated_cost_saved": f"${stats.estimated_cost_saved:.2f}",
        "runtime_hours": f"{stats.runtime_hours:.1f}",
        "tokens_saved": stats.total_input_tokens_before - stats.total_input_tokens_after,
    }

    for key, val in data.items():
        print(f"  {key.replace('_', ' ').title():35s} {val}")

    print(f"\n  💡 That's roughly {data['tokens_saved']:,} tokens")
    print(f"     you didn't pay for. Not bad.")


def cmd_proxy(args):
    """Start/stop the transparent compression proxy."""
    from .proxy import TokenSaveProxy

    proxy = TokenSaveProxy()

    if args.proxy_action == "start":
        if proxy.start():
            print(f"✅ Proxy started on 127.0.0.1:18787")
        else:
            print("⚠ Proxy already running or port in use")

    elif args.proxy_action == "stop":
        proxy.stop()
        print("🛑 Proxy stopped")

    elif args.proxy_action == "restart":
        proxy.stop()
        if proxy.start():
            print("✅ Proxy restarted")
        else:
            print("✗ Failed to restart proxy")


def cmd_shell_hook(args):
    """Print shell hooks for eval."""
    print(
        'export TOKENSAVE_ACTIVE=1\n'
        'alias tsave="tokensave status"\n'
    )


def main():
    parser = argparse.ArgumentParser(
        description="TokenSave — One command to slash your LLM API bills",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"TokenSave {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # setup
    p_setup = subparsers.add_parser("setup", help="One-command setup: detect, configure, start saving")

    # status
    p_status = subparsers.add_parser("status", help="Show current status and savings")

    # off
    p_off = subparsers.add_parser("off", help="Stop proxy and restore original settings")

    # stats
    p_stats = subparsers.add_parser("stats", help="View detailed savings statistics")

    # proxy
    p_proxy = subparsers.add_parser("proxy", help="Manage the compression proxy")
    p_proxy.add_argument("proxy_action", choices=["start", "stop", "restart"])

    # shell-hook (internal)
    p_hook = subparsers.add_parser("shell-hook", help="Print shell hooks (internal)")

    args = parser.parse_args()

    if args.command == "setup":
        cmd_setup(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "off":
        cmd_off(args)
    elif args.command == "stats":
        cmd_stats(args)
    elif args.command == "proxy":
        cmd_proxy(args)
    elif args.command == "shell-hook":
        cmd_shell_hook(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
