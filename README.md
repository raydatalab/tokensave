
<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://img.shields.io/badge/tokensave-0.3.0-blue?style=flat-square&labelColor=black">
    <img src="https://img.shields.io/badge/tokensave-0.3.0-blue?style=flat-square" alt="tokensave">
  </picture>
</p>

<p align="center">
  <a href="README.zh.md">🇨🇳 中文</a>
</p>

---

# TokenSave

<p align="center">
  <a href="https://pypi.org/project/tokensave/">
    <img src="https://img.shields.io/pypi/v/tokensave?style=flat-square&label=version" alt="PyPI">
  </a>
  <a href="https://pypi.org/project/tokensave/">
    <img src="https://img.shields.io/pypi/pyversions/tokensave?style=flat-square" alt="Python">
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/pypi/l/tokensave?style=flat-square" alt="License">
  </a>
  <a href="https://github.com/raydatalab/tokensave">
    <img src="https://img.shields.io/github/stars/raydatalab/tokensave?style=flat-square" alt="Stars">
  </a>
  <a href="https://pypi.org/project/tokensave/">
    <img src="https://img.shields.io/pypi/dm/tokensave?style=flat-square" alt="Downloads">
  </a>
</p>

LLM API calls cost money. Most of those tokens are wasted on repeated instructions, verbose logs, boilerplate data, and conversation history that keeps growing. TokenSave strips the redundancy before it reaches the API.

**`pip install tokensave` → `from tokensave import OpenAI` → bills go down.**

### Supported Platforms

`Linux` · `macOS` · `Windows` · `WSL`

You need Python 3.10+.

### What It Does

| Before | After |
|--------|-------|
| Sends full conversation history every time | Compresses redundant context on the fly |
| Repeats the same system prompt verbatim | Normalizes and deduplicates |
| Pays for every token, every time | Exact-match cache hits return immediately, zero API cost |
| Needs a setup wizard, daemon, or proxy | One import, zero config |

### Quick Start

```bash
pip install tokensave
```

```python
from tokensave import OpenAI

client = OpenAI(api_key="...", base_url="https://api.deepseek.com/v1")
# Use it like regular openai. TokenSave compresses automatically.
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

That's it. No setup, no daemon, no env vars to tweak.

### Benchmarks

| Scenario | Before | After | Savings | Cost saved (DeepSeek, ×1000) |
|----------|--------|-------|---------|-------------------------------|
| 200-row JSON data | 15,681 tok | 9,256 tok | **41%** | ¥3.20 |
| 3600-line log dump | 91,445 tok | 143 tok | **~100%** | ¥45.70 |

Full benchmarks → [`BENCHMARK.md`](BENCHMARK.md)

### Proxy Mode (Power-User)

For non-Python tools (curl, other languages, Claude Code):

```bash
tokensave proxy
```

Starts a local proxy on `localhost:18787` that compresses requests on the fly. Supports both OpenAI (`/v1/chat/completions`) and Anthropic (`/v1/messages`) formats.

### Tech Stack

| Component | Role |
|-----------|------|
| [`headroom-ai`](https://github.com/nicktrisolaran/headroom) | SmartCrusher + CodeCompressor content compression |
| SQLite (stdlib) | Zero-config exact-match cache |

### License

Apache 2.0 — see [LICENSE](LICENSE).
