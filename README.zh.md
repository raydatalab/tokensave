
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

### 实测数据

| 场景 | 压缩前 | 压缩后 | 节省 | Sonnet 5 省（×1000次） |
|------|--------|--------|------|-----------------------|
| 10MB 生产日志 | ~2,500,000 tok | ~5,000 tok | **~99.8%** | **~$4,990** |
| 2MB 代码/数据集 | ~500,000 tok | ~295,000 tok | **41%** | **~$410** |

完整数据 → [`BENCHMARK.md`](BENCHMARK.md)

> *定价参考：Sonnet 5 $2/百万输入 token，[Anthropic API 定价](https://www.anthropic.com/pricing)，2026年7月。*

### 技术栈

| 组件 | 作用 |
|------|------|
| [`headroom-ai`](https://github.com/nicktrisolaran/headroom) | SmartCrusher + CodeCompressor 内容压缩 |
| SQLite（标准库） | 零配置精确匹配缓存 |

### 许可证

Apache 2.0 — 详见 [LICENSE](LICENSE)。
