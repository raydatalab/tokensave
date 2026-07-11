---
name: tokensave
description: Use when analyzing token waste, costs, or API bills. Finds duplicate tool calls, context bloat, model mismatch, and heartbeat waste. 100% local, zero config.
version: 0.4.1
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
  - reduce cost
  - cut cost
  - api spending
  - token budget
  - expensive model
  - how much did this cost
  - estimate cost
  - cost breakdown
  - where is my money going
  - agent spending
  - api fees
  - lower my bill
metadata:
  hermes:
    tags: [cost-optimization, token-analysis, waste-detection, diagnostics]
    homepage: https://github.com/raydatalab/tokensave
    related_skills: [hermes-smart-router, hermes-cost-optimization]
---

# TokenSave

## Overview

Every day your agent wastes tokens — re-reading the same files, running on
pro when flash would do, keeping stale context around. TokenSave analyzes
your session and tells you exactly where the waste is, how much it costs,
and gives you a ready-to-paste prompt to fix it.

## When to Use

- User asks about costs, bills, or token usage
- User says "analyze my session" or "how much did I spend"
- User mentions "waste", "expensive", "save money"
- You want to help the user understand where their money goes

## How It Works

When you send "tokensave" or ask about cost/waste, just run:

```bash
tokensave analyze
```

It auto-detects the latest session from `~/.hermes/state.db` (the primary session store). You can also target a specific source:

```bash
tokensave analyze <session_id>          # specific session from state.db
tokensave analyze <file.json>           # error request dump
tokensave analyze <directory/>          # latest JSON in directory
tokensave analyze --detectors dup,bloat # specific detectors only
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

## What It Detects

Four waste detectors run against your session:

| Detector | What it finds |
|----------|---------------|
| Duplicate tool calls | Same tool + same args called 2+ times (exact + near-duplicate) |
| Context bloat | Stale/redundant context, oversized tool outputs, unused tool definitions, session overhead |
| Model mismatch | Simple queries running on expensive models — tells you which cheaper model to use |
| Heartbeat waste | Cron jobs and idle/status checks that could run on a cheaper model |

## Data Sources

TokenSave reads from two sources (no config needed):

| Source | Format | What's there |
|--------|--------|-------------|
| `~/.hermes/state.db` | SQLite | Primary — full session transcripts with token counts, costs, and metadata |
| `~/.hermes/sessions/*.json` | JSON | API error request dumps — partial data but useful when SQLite is unavailable |

Auto-detect tries SQLite first, falls back to JSON, then gives a clear error message.

## What You Need

- Python 3.10+
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
| `analyze` | SQLite sessions + JSON error dumps | Waste report + fix prompt |
| `pipeline` | Transparent proxy | Automatic token savings |

## Common Pitfalls

1. **No session data found.** If `tokensave analyze` returns no results, the session
   may not have been written to `state.db` yet. Hermes writes state.db on session end —
   try again after `/new`.
2. **JSON fallback gives incomplete analysis.** JSON error dumps lack full metadata.
   Always prefer SQLite mode (default). If you're seeing JSON fallback, the state.db
   may be locked by another Hermes process.
3. **Duplicate detection is generous.** Near-duplicate detection uses fuzzy matching
   and may flag legitimate re-reads. Use the report as a starting point, not a verdict.
4. **Pipeline mode doesn't work with all providers.** The transparent wrapper only
   supports OpenAI-compatible APIs. Non-OpenAI providers will fall through to direct
   calls.
