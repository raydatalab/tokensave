"""
Model pricing data for waste detection.

Precedence:
  1. litellm.model_cost (if installed) — always current
  2. Built-in fallback table below — covers common models

Prices are per 1M tokens (input / output). Updated 2026-07.
"""

import logging

logger = logging.getLogger("tokensave.pricing")

# ── Built-in fallback pricing (per 1M tokens) ──────────────────────────
# Format: {model_id: {"input": $/1M, "output": $/1M, "provider": str}}
# Prices sourced from official provider pages, July 2026.

_FALLBACK_PRICES: dict[str, dict] = {
    # ── Anthropic ──────────────────────────────────────────────────────
    "claude-opus-4-8":        {"input": 15.00, "output": 75.00, "provider": "anthropic"},
    "claude-opus-4-7":        {"input": 15.00, "output": 75.00, "provider": "anthropic"},
    "claude-opus-4":          {"input": 15.00, "output": 75.00, "provider": "anthropic"},
    "claude-opus-4.5":        {"input": 15.00, "output": 75.00, "provider": "anthropic"},
    "claude-sonnet-5":        {"input": 3.00,  "output": 15.00, "provider": "anthropic"},
    "claude-sonnet-4":        {"input": 3.00,  "output": 15.00, "provider": "anthropic"},
    "claude-sonnet-4.5":      {"input": 3.00,  "output": 15.00, "provider": "anthropic"},
    "claude-haiku-4.5":       {"input": 0.80,  "output": 4.00,  "provider": "anthropic"},
    "claude-haiku-3.5":       {"input": 0.80,  "output": 4.00,  "provider": "anthropic"},
    "claude-fable-5":         {"input": 3.00,  "output": 15.00, "provider": "anthropic"},
    # ── OpenAI ─────────────────────────────────────────────────────────
    "gpt-5":                  {"input": 1.25,  "output": 10.00, "provider": "openai"},
    "gpt-5-mini":             {"input": 0.15,  "output": 0.60,  "provider": "openai"},
    "gpt-5-nano":             {"input": 0.05,  "output": 0.20,  "provider": "openai"},
    "gpt-4.1":                {"input": 2.00,  "output": 8.00,  "provider": "openai"},
    "gpt-4.1-mini":           {"input": 0.40,  "output": 1.60,  "provider": "openai"},
    "gpt-4.1-nano":           {"input": 0.10,  "output": 0.40,  "provider": "openai"},
    "gpt-4o":                 {"input": 2.50,  "output": 10.00, "provider": "openai"},
    "gpt-4o-mini":            {"input": 0.15,  "output": 0.60,  "provider": "openai"},
    "o4-mini":                {"input": 1.10,  "output": 4.40,  "provider": "openai"},
    "o3":                     {"input": 10.00, "output": 40.00, "provider": "openai"},
    # ── DeepSeek ───────────────────────────────────────────────────────
    "deepseek-v4-pro":        {"input": 1.20,  "output": 4.80,  "provider": "deepseek"},
    "deepseek-v4":            {"input": 0.60,  "output": 2.40,  "provider": "deepseek"},
    "deepseek-v4-flash":      {"input": 0.27,  "output": 1.10,  "provider": "deepseek"},
    "deepseek-v3":            {"input": 0.27,  "output": 1.10,  "provider": "deepseek"},
    "deepseek-r1":            {"input": 0.55,  "output": 2.19,  "provider": "deepseek"},
    # ── Google ─────────────────────────────────────────────────────────
    "gemini-3-pro":           {"input": 1.25,  "output": 10.00, "provider": "google"},
    "gemini-3-flash":         {"input": 0.15,  "output": 0.60,  "provider": "google"},
    "gemini-2.5-pro":         {"input": 1.25,  "output": 10.00, "provider": "google"},
    "gemini-2.5-flash":       {"input": 0.15,  "output": 0.60,  "provider": "google"},
}

# Cheapest model per provider family (for heartrate/mismatch comparison)
_CHEAPEST_PER_PROVIDER: dict[str, str] = {
    "anthropic": "claude-haiku-4.5",
    "openai":    "gpt-5-nano",
    "deepseek":  "deepseek-v3",
    "google":    "gemini-3-flash",
}


def _get_litellm_prices() -> dict[str, dict]:
    """Try to load pricing from litellm. Returns {} on any failure."""
    try:
        import litellm

        cost_map = getattr(litellm, "model_cost", None)
        if not cost_map:
            return {}
        result = {}
        for model, info in cost_map.items():
            if not isinstance(info, dict):
                continue
            inp = info.get("input_cost_per_token", 0)
            out = info.get("output_cost_per_token", 0)
            if inp or out:
                result[model] = {
                    "input": inp * 1_000_000,
                    "output": out * 1_000_000,
                    "provider": info.get("litellm_provider", "unknown"),
                }
        return result
    except Exception:
        return {}


def get_model_price(model: str) -> dict | None:
    """Return {"input": $/1M, "output": $/1M, "provider": str} or None."""
    # Try litellm first for up-to-date pricing
    litellm_prices = _get_litellm_prices()
    if model in litellm_prices:
        return litellm_prices[model]

    # Fall back to built-in table
    if model in _FALLBACK_PRICES:
        return _FALLBACK_PRICES[model]

    # Partial match: strip version suffixes and try again
    for known in _FALLBACK_PRICES:
        if model.startswith(known) or known.startswith(model):
            return _FALLBACK_PRICES[known]

    return None


def estimate_cost(model: str, input_tokens: int = 0, output_tokens: int = 0) -> float | None:
    """Estimate USD cost for given token counts. Returns None if model unknown."""
    price = get_model_price(model)
    if price is None:
        return None
    cost = (input_tokens / 1_000_000) * price["input"] + (output_tokens / 1_000_000) * price["output"]
    return round(cost, 6)


def get_cheapest_equivalent(model: str) -> str | None:
    """Return the cheapest model from the same provider, or None."""
    price = get_model_price(model)
    if price is None:
        return None
    provider = price.get("provider", "")
    return _CHEAPEST_PER_PROVIDER.get(provider)


def get_provider(model: str) -> str | None:
    """Return the provider for a model, or None."""
    price = get_model_price(model)
    if price is None:
        return None
    return price.get("provider")
