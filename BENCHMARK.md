# TokenSave 压缩效果实测数据

## 测试环境

- 工具版本：tokensave v0.1.1 / headroom-ai v0.30.0
- 调用方式：`from tokensave import OpenAI`
- 测试模型：DeepSeek v4 Flash
- 压缩后端：Headroom 内容感知压缩（SmartCrusher + CodeCompressor + Kompress-v2-base）

---

## 场景 ① 结构化数据（200条JSON）

模拟数据库查询返回的 JSON 列表（50KB 数据）

| 指标 | 数值 |
|------|------|
| 压缩前 | 15,681 tokens |
| 压缩后 | 9,256 tokens |
| 节省 | 6,425 tokens (**41%**) |
| 每次节省（DeepSeek） | ¥0.0032 |
| 1000次节省（DeepSeek） | ¥3.20 |

---

## 场景 ② 代码 + 日志（3600行日志）

模拟 agent 分析代码错误 + 读取日志文件（~200KB）

| 指标 | 数值 |
|------|------|
| 压缩前 | 91,445 tokens |
| 压缩后 | 143 tokens |
| 节省 | 91,302 tokens (**~100%**) |
| 每次节省（DeepSeek） | ¥0.0457 |
| 1000次节省（DeepSeek） | ¥45.70 |
| 1000次节省（Claude） | ¥274.00 |

---

## 端到端验证

```
import: from tokensave import OpenAI  ✓
调用: client.chat.completions.create()  ✓
压缩: 启用  ✓
透传（无headroom时）: 正常  ✓
```

---

## 一句话

```
pip install tokensave
from tokensave import OpenAI   # 开箱即用，立刻省钱
```
