"""Detect what LLM tools the user has installed and which API provider they use."""

import os
import shutil
import subprocess
import json
from pathlib import Path

HOME = Path.home()


def detect_claude_code() -> dict:
    """Detect Claude Code installation and configuration."""
    result = {"installed": False, "mode": None, "config_path": None}

    # Check if claude command exists
    claude_path = shutil.which("claude")
    if claude_path:
        result["installed"] = True
        result["binary"] = str(claude_path)

        # Check API key / auth mode
        if os.environ.get("ANTHROPIC_API_KEY"):
            result["mode"] = "api"
            result["api_key_prefix"] = os.environ["ANTHROPIC_API_KEY"][:8] + "..."
        elif os.environ.get("CLAUDE_API_KEY"):
            result["mode"] = "api"
        else:
            result["mode"] = "subscription"

        # Check config
        config_paths = [
            HOME / ".claude" / "settings.json",
            HOME / ".claude" / "claude.json",
            HOME / ".config" / "claude" / "settings.json",
        ]
        for p in config_paths:
            if p.exists():
                result["config_path"] = str(p)
                try:
                    data = json.loads(p.read_text())
                    result["config"] = data
                except (json.JSONDecodeError, OSError):
                    pass
                break

    return result


def detect_sillytavern() -> dict:
    """Detect SillyTavern installation."""
    result = {"installed": False, "path": None}

    # Common install locations
    search_paths = [
        HOME / "SillyTavern",
        HOME / "sillytavern",
        HOME / "ST",
        HOME / "SillyTavern-Launcher",
    ]
    for p in search_paths:
        if p.exists() and (p / "config.yaml").exists():
            result["installed"] = True
            result["path"] = str(p)
            break

    return result


def detect_openai_key() -> bool:
    """Check if user has OpenAI API key configured."""
    return bool(os.environ.get("OPENAI_API_KEY"))


def detect_anthropic_key() -> bool:
    """Check if user has Anthropic API key configured."""
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def get_api_base_urls() -> dict:
    """Get current API base URLs from environment (may have been set by other tools)."""
    return {
        "openai": os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        "anthropic": os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
    }


def detect_all() -> dict:
    """Run all detectors and return a complete profile."""
    env = {
        "claude_code": detect_claude_code(),
        "sillytavern": detect_sillytavern(),
        "api_keys": {
            "openai": detect_openai_key(),
            "anthropic": detect_anthropic_key(),
        },
        "base_urls": get_api_base_urls(),
        "shell": os.environ.get("SHELL", "unknown"),
        "platform": os.uname().sysname if hasattr(os, "uname") else "unknown",
    }

    # Determine primary use case
    if env["claude_code"]["installed"]:
        env["primary_tool"] = "claude_code"
    elif env["sillytavern"]["installed"]:
        env["primary_tool"] = "sillytavern"
    elif env["api_keys"]["openai"] or env["api_keys"]["anthropic"]:
        env["primary_tool"] = "api_user"
    else:
        env["primary_tool"] = "unknown"

    return env


def summary(env: dict) -> str:
    """Return a human-readable summary of the detected environment."""
    lines = ["🔍 Environment Detection:\n"]

    cc = env["claude_code"]
    if cc["installed"]:
        mode_str = "API key" if cc["mode"] == "api" else "subscription"
        lines.append(f"  ✓ Claude Code detected ({mode_str} mode)")
    else:
        lines.append("  ✗ Claude Code not detected")

    st = env["sillytavern"]
    if st["installed"]:
        lines.append(f"  ✓ SillyTavern detected at {st['path']}")
    else:
        lines.append("  ✗ SillyTavern not detected")

    keys = env["api_keys"]
    if keys["openai"]:
        lines.append("  ✓ OpenAI API key found")
    if keys["anthropic"]:
        lines.append("  ✓ Anthropic API key found")

    if not any(keys.values()):
        if not cc["installed"]:
            lines.append("  ⚠ No API keys detected. TokenSave works best with API-based access.")

    lines.append(f"\n  Primary tool: {env['primary_tool']}")
    return "\n".join(lines)
