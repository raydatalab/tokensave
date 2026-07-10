# TokenSave — 设计目的与终极目标

> 无历史包袱版。只看名字、目的、终极目标。
> 已有的 headroom、smart-router 只是可调用的手段，不绑定。

---

## 名字

**TokenSave** — 帮你搞清楚你的 AI agent 把钱花哪了，然后告诉你怎么省。

---

## 目的（一句话）

> 让每个用 AI agent 的人都能看到自己的 token 账单，知道浪费在哪，并得到一条可以直接发给 agent 让它改的指令。

---

## 终极目标

用户跑 `tokensave analyze`，看到三行输出：

```
花了 $3.20，其中 $1.80 是可以避免的。
最大浪费：重复读文件 12 次（省 $0.90）、pro 模型处理简单查询 5 次（省 $0.60）、心跳占了 18%（省 $0.30）。
复制这段话发给你的 agent：「...」
```

用户复制第三行，粘贴发给 agent。agent 改了行为。下次分析，浪费降到 $0.40。

这就是 TokenSave 存在的全部意义。

---

## 设计原则（硬约束，不可妥协）

### #1 输出必须极短
不是 50 页报告。不是 dashboard。是三行。用户不需要"了解自己的使用习惯"——用户需要知道浪费在哪，然后马上行动。

### #2 建议必须可执行
每条建议 = 一段可以直接粘贴发给 agent 的文本。agent 读完后应该能改变自己的行为。不是给人看的分析报告——是给 agent 看的指令。

### #3 默认零配置
`tokensave analyze`，不指定 session、不指定路径、不指定格式。自动找最近的 session。

### #4 全本地，不上传
读文件、分析、输出，全部本地。不收集任何数据。

### #5 不是一个"平台"
不要 dashboard，不要 web UI，不要注册账号。一个 CLI 命令。用完就走。

---

## 可以调用的手段（工具，不是包袱）

| 手段 | 什么时候用 |
|------|------|
| headroom (SmartCrusher) | 检测上下文膨胀，估算压缩后可节省 token |
| smart-router 的路由决策 | 如果用户装了 smart-router，检查它的日志，看模型选择是否合理 |
| SQLite 精确缓存 | tokensave v0.3.0 已有的——保留作为优化层，不是分析层 |
| Python stdlib | 分析逻辑本身不依赖外部库 |

**重要：** 以上手段是"可用即用"，不是"必须用"。如果有更好的方法完成同一个分析目标，换掉。

---

## 不做的事

- 不追求覆盖所有 agent 平台（先 Hermes，后扩展）
- 不代替 smart-router（smart-router 是事前，tokensave 是事后）
- 不主动优化（分析 + 建议，不自动改配置）
- 不生成图表
- 不追求 100% 准确（估算是 OK 的，但要标注是估算）

---

## 和 smart-router 的分工

| | smart-router | TokenSave |
|:---|:---:|:---:|
| 时机 | 事前（发消息之前） | 事后（session 结束后） |
| 动作 | 建议切换模型 | 分析浪费 + 给优化指令 |
| 用户感知 | 消息里多一行提示 | 主动跑命令看结果 |
| 关系 | 互补，不重叠 | |

---

## 当前状态（2026-07-11）

**文档就绪，等待 Claude Code 实现。**

v0.3.0 已存在：透明 OpenAI 代理，消息规范化 + 缓存 + 压缩。PyPI 上有 4 个版本（0.1.0/0.1.1/0.1.3/0.3.0）。

v0.4.0 要新增：
- `tokensave analyze` CLI 子命令
- 5 个 waste detector
- advisor（可执行 prompt 生成器）

**已完成（文档层）：**
- SKILL.md — 新建，ClawHub 发布用
- README.md — 重写，analyze 为主线 + pipeline 为副线
- pyproject.toml — 版本 0.4.0，描述更新
- DESIGN-v0.4.0.md — 设计思想 + 硬约束
- CLAUDE.md — Claude 工程指令

**待 Claude 实现（代码层）：**

**新代码：**
```
tokensave/analyzer.py    # 浪费检测（5 个检测器）
tokensave/advisor.py      # 生成可执行建议
tokensave/cli.py          # 增加 'analyze' 子命令
```

**不碰的：**
```
tokensave/__init__.py     # 现有管道
tokensave/cache.py        # 缓存层
tokensave/compressors/    # 压缩层
```
