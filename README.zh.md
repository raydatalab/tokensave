
<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://img.shields.io/badge/tokensave-0.3.0-blue?style=flat-square&labelColor=black">
    <img src="https://img.shields.io/badge/tokensave-0.3.0-blue?style=flat-square" alt="tokensave">
  </picture>
</p>

<p align="center">
  <a href="README.md">🇬🇧 English</a>
</p>

---

# TokenSave

<p align="center">
  <a href="https://pypi.org/project/tokensave/">
    <img src="https://img.shields.io/pypi/v/tokensave?style=flat-square&label=版本" alt="PyPI">
  </a>
  <a href="https://pypi.org/project/tokensave/">
    <img src="https://img.shields.io/pypi/pyversions/tokensave?style=flat-square" alt="Python">
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/pypi/l/tokensave?style=flat-square" alt="许可证">
  </a>
  <a href="https://github.com/raydatalab/tokensave">
    <img src="https://img.shields.io/github/stars/raydatalab/tokensave?style=flat-square" alt="Stars">
  </a>
  <a href="https://pypi.org/project/tokensave/">
    <img src="https://img.shields.io/pypi/dm/tokensave?style=flat-square" alt="下载量">
  </a>
</p>

LLM API 按量计费，但大部分 token 浪费在重复指令、长日志、结构化数据模板和不断累加的对话历史上。TokenSave 在上行前自动去除冗余。

**`pip install tokensave` → `from tokensave import OpenAI` → 省 token，零配置。**

### 支持平台

`Linux` · `macOS` · `Windows` · `WSL`

Python 3.10+ 即可。

### 功能速览

| 之前 | 之后 |
|------|------|
| 每次发送完整对话历史 | 自动压缩冗余上下文 |
| 系统提示词每次都原样发送 | 归一化 + 去重 |
| 每个 token 都要付费 | 精确匹配缓存直接返回，零成本 |
| 需要配置/守护进程/代理 | 一次 import，零配置 |

### 快速开始

```bash
pip install tokensave
```

```python
from tokensave import OpenAI

client = OpenAI(api_key="...", base_url="https://api.deepseek.com/v1")
# 跟普通 openai 一样用。TokenSave 自动压缩。
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": "你好！"}]
)
```

没有配置文件，没有守护进程，不用配环境变量。

### 实测数据

| 场景 | 压缩前 | 压缩后 | 节省 | DeepSeek 省（×1000次） |
|------|--------|--------|------|----------------------|
| 200 条 JSON 数据 | 15,681 tok | 9,256 tok | **41%** | ¥3.20 |
| 3600 行日志 | 91,445 tok | 143 tok | **~100%** | ¥45.70 |

完整数据 → [`BENCHMARK.md`](BENCHMARK.md)

### Proxy 模式（高级用户）

给非 Python 工具用（curl、其他语言等）：

```bash
tokensave proxy
```

在 `localhost:18787` 启动一个本地代理，自动压缩请求。支持 OpenAI（`/v1/chat/completions`）和 Anthropic（`/v1/messages`）格式。

### 技术栈

| 组件 | 作用 |
|------|------|
| [`headroom-ai`](https://github.com/nicktrisolaran/headroom) | SmartCrusher + CodeCompressor 内容压缩 |
| SQLite（标准库） | 零配置精确匹配缓存 |

### 许可证

Apache 2.0 — 详见 [LICENSE](LICENSE)。
