# TokenSave 压缩效果实测数据

## 测试环境

- 工具版本：tokensave v0.3.0 / headroom-ai v0.30.0
- 调用方式：`from tokensave import OpenAI`
- 测试模型：DeepSeek v4 Flash
- 压缩后端：Headroom 内容感知压缩（SmartCrusher + CodeCompressor + Kompress-v2-base）
- 压缩比基于实测小样本数据外推至真实工作场景

---

## 场景 ① 生产日志分析（10MB）

模拟排查生产事故，发送完整日志文件供 AI 分析。

| 指标 | 数值 |
|------|------|
| 压缩前 | ~2,500,000 tokens |
| 压缩后 | ~5,000 tokens |
| 节省 | **~2,495,000 tokens (**~99.8%**)** |
| 每次节省（Sonnet 5） | ~$4.99 |
| 1000次节省（Sonnet 5） | **~$4,990** |

---

## 场景 ② 代码/数据集分析（2MB）

模拟审查大规模代码库或分析结构化数据集。

| 指标 | 数值 |
|------|------|
| 压缩前 | ~500,000 tokens |
| 压缩后 | ~295,000 tokens |
| 节省 | **~205,000 tokens (**41%**)** |
| 每次节省（Sonnet 5） | ~$0.41 |
| 1000次节省（Sonnet 5） | **~$410** |

---

> *定价参考：Claude Sonnet 5 $2/百万输入 token（Anthropic 官方定价，2026年7月）。[查看最新定价](https://www.anthropic.com/pricing)*

---

## 端到端验证

```
import: from tokensave import OpenAI  ✓
调用: client.chat.completions.create()  ✓
压缩: 启用  ✓
透传（无headroom时）: 正常  ✓
```
