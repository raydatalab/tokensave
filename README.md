# TokenSave v0.4.0

> Context optimization for LLM API calls + waste analyzer.
> `pip install tokensave` — bills go down.

---

## What's New in 0.4.0

**`tokensave analyze`** — find out where your agent is wasting tokens, and get a one-click fix.

```bash
$ tokensave analyze

Session 2026-07-11_abc123: 12,400 tokens, ~$0.19, 41% avoidable.

Top wastes:
  #1 duplicate_tool_calls (8x): ~4,800 tokens — read the same file 8 times
  #2 model_mismatch (5x): ~860 tokens — flash-tier queries ran on pro
  #3 context_bloat: ~3,700 tokens — 40% of input is stale context

Send to your agent: "Before reading a file, check if you already read it..."
```

## What It Does (Two Modes)

### Mode 1: Analyze (`tokensave analyze`) ← NEW in 0.4.0

Reads Hermes session data from `~/.hermes/state.db` (SQLite, primary) or `~/.hermes/sessions/*.json` (API error dumps, fallback) and detects four categories of waste:

| Detector | What it finds |
|----------|---------------|
| Duplicate tool calls | Same tool + same args called 2+ times (exact + near-duplicate) |
| Context bloat | Stale overlapping content, oversized tool outputs, unused tools, session overhead |
| Model mismatch | Simple queries running on expensive models |
| Heartbeat waste | Cron/scheduled/idle-check messages on pro-tier |

Output: ≤5 lines, actionable. Zero config. 100% local.

### Mode 2: Pipeline (v0.3.0, unchanged)

Transparent OpenAI wrapper — `from tokensave import OpenAI` — automatic normalization, exact-match cache, and context compression. Cuts token usage without changing your code.

## Why Tokensave + Smart Router

| | TokenSave | Smart Router |
|---|:---:|:---:|
| **When** | After the session (diagnosis) | Before each message (prevention) |
| **Job** | "Here's where you're wasting money" | "Use this model instead" |
| **User** | Run manually, get insights | Runs automatically, suggests switches |

Use both for maximum savings: Smart Router prevents waste, TokenSave reveals what slipped through.

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
