---
name: tokensave
description: Analyze your Hermes agent's token waste and get one-click fix prompts. Finds duplicate tool calls, context bloat, model mismatch, and heartbeat waste. 100% local, zero config.
version: 0.4.0
author: raydatalab
license: Apache-2.0
platforms: [linux, macos, wsl]
triggers:
  - token waste
  - analyze cost
  - audit tokens
  - save cost
  - save money
  - too expensive
  - api bill
  - wasted tokens
  - spending too much
  - 浪费 token
  - 省钱
  - 账单
  - 分析用量
  - token usage
  - model cost
  - optimize cost
  - 优化成本
  - check waste
metadata:
  hermes:
    tags: [cost-optimization, token-analysis, waste-detection, diagnostics]
    homepage: https://github.com/raydatalab/tokensave
    related_skills: [hermes-smart-router, hermes-cost-optimization]
---

# TokenSave

Analyze your Hermes agent's token usage and get one-click fix prompts.

## Why Use Me

Every day your agent wastes tokens — re-reading the same files, running on
pro when flash would do, keeping stale context around. TokenSave tells you
exactly where the waste is, how much it costs, and gives you a ready-to-paste
prompt to fix it.

## How It Works

When you send "tokensave" or ask about cost/waste, run:

```bash
tokensave analyze ~/.hermes/sessions/<latest>.json
```

Copy the output and paste it into your response. The user sees:

```
Session abc123: 12,400 tokens, ~$0.19, 41% avoidable.

Top wastes:
  #1 duplicate_tool_calls (8x): ~4,800 tokens
  #2 model_mismatch (5x): ~860 tokens
  #3 context_bloat: ~3,700 tokens

Send to your agent: "Before reading a file, check if you already..."
```

## When to Use

- User asks about costs, bills, or token usage
- User says "analyze my session" or "how much did I spend"
- User mentions "waste", "expensive", "save money"
- You want to help the user understand where their money goes

## What You Need

- Hermes Agent v0.17+
- `pip install tokensave`
- Nothing else — no API keys, no network, no config

## Pipeline Mode (Bonus)

tokensave also works as a transparent OpenAI wrapper that cuts token usage
automatically. If the user has installed it with `from tokensave import OpenAI`,
their API calls go through normalize → cache → compress. But that's automatic —
you don't need to do anything.

## Tier Reference

| Tier | What it checks | Output |
|------|---------------|--------|
| `analyze` | Session file | Waste report + fix prompt |
| `pipeline` | Transparent proxy | Automatic token savings |
