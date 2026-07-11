# TokenSave v0.4.4

> Token waste analyzer for AI agents — find where your money goes and get one-click fix prompts.
> `pip install tokensave` — bills go down.

<p align="center">
  <img src="https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fclawhub.ai%2Fapi%2Fv1%2Fskills%2Ftokensave&query=%24.skill.stats.downloads&label=ClawHub+downloads&color=blue&cacheSeconds=3600" alt="ClawHub downloads">
</p>

---

```bash
$ tokensave analyze

Session 20260711_a1b2c3: 12,000 tokens, ~$0.05, 44% avoidable.

Top wastes:
  1. duplicate_tool_calls (5x): ~3,000 tokens — read_file called 5x with same path
  2. context_bloat (1x): ~1,800 tokens — 40% of input is stale context
  3. model_mismatch (3x): ~500 tokens — simple queries routed through pro

Send to your agent: "Before calling any tool, check if you already have
the result in a previous message..."
```

One session. 12K tokens. 44% could have been avoided — 5,300 tokens saved with a single paste.

All numbers from `tests/test_analyzer.py` real test fixtures. No made-up data.

---

## What It Does (Two Modes)

### Mode 1: Analyze (`tokensave analyze`)

Reads Hermes session data from `~/.hermes/state.db` (SQLite, primary) or
`~/.hermes/sessions/*.json` (API error dumps, fallback) and detects four
categories of waste:

| Detector | What it finds |
|----------|---------------|
| Duplicate tool calls | Same tool + same args called 2+ times (exact + near-duplicate) |
| Context bloat | Stale overlapping content, oversized tool outputs, unused tools, session overhead |
| Model mismatch | Simple queries running on expensive models |
| Heartbeat waste | Cron/scheduled/idle-check messages on pro-tier |

Output: ≤5 lines, actionable. Zero config. 100% local.

### Mode 2: Pipeline (v0.3.0, unchanged)

Transparent OpenAI wrapper — `from tokensave import OpenAI` — automatic
normalization, exact-match cache, and context compression. Cuts token usage
without changing your code.

## Why TokenSave + Smart Router

| | TokenSave | Smart Router |
|---|:---:|:---:|
| **When** | After the session (diagnosis) | Before each message (prevention) |
| **Job** | "Here's where you're wasting money" | "Use this model instead" |
| **User** | Run manually, get insights | Runs automatically, suggests switches |

Use both for maximum savings: Smart Router prevents waste, TokenSave reveals
what slipped through.

## Install

```bash
pip install tokensave
```

Or as a Hermes skill:

```bash
hermes skills install raydatalab/tokensave     # from ClawHub
hermes skills install raydatalab/tokensave     # from GitHub
```

## Usage

```bash
# Analyze your latest session (auto-detect from state.db)
tokensave analyze

# Analyze a specific session by ID
tokensave analyze 20260710_214623_e95335

# Analyze an error request dump
tokensave analyze ~/.hermes/sessions/request_dump_*.json

# Run only specific detectors
tokensave analyze --detectors duplicate_tool_calls,model_mismatch

# Pipeline mode (automatic)
export OPENAI_API_KEY=sk-...
python3 -c "
from tokensave import OpenAI
client = OpenAI()
# All calls go through normalize → cache → compress
"
```

## Benchmarks (Pipeline Mode)

| Scenario | Before | After | Savings |
|----------|--------|-------|---------|
| 10MB production logs | ~2,500,000 tok | ~5,000 tok | **~99.8%** |
| 2MB code/dataset | ~500,000 tok | ~295,000 tok | **41%** |

Full benchmarks → [`BENCHMARK.md`](BENCHMARK.md)

## Tech Stack

| Component | Role |
|-----------|------|
| Python stdlib | Waste detection, session parsing |
| SQLite (stdlib) | Exact-match cache |
| [`headroom-ai`](https://github.com/nicktrisolaran/headroom) | SmartCrusher + CodeCompressor (pipeline mode) |

## License

Apache 2.0 — see [LICENSE](LICENSE).
