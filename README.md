# MiniAgent —— 用纯 Python 手写的 Agent 内核

> 不依赖 LangChain / LangGraph / 任何 Agent 框架，从零实现 Function Calling 循环、工具注册、多实例隔离，并在这套内核上跑了两个完全不同的应用。
>
> Python 3.11 · DeepSeek API · OpenAI SDK · **约 920 行，零框架依赖**

---

## 为什么做这个

用框架搭 Agent 很容易，但说不清它内部怎么运转：

- 模型是怎么"决定"要调工具的？
- 工具执行完，结果怎么回到对话里？
- 为什么两个 Agent 实例不会互相串记忆？

这个项目就是为了把这三件事**手写一遍**。写完之后再看 LangGraph，才知道它替你做了什么、代价是什么。

**核心验证目标只有一条：**

> **加第二个应用时，框架代码一行都不用改。**

如果改了，说明抽象是错的。

---

## 核心设计：框架与应用分离

```
┌─────────────────────────────────────────────────────────┐
│  core/agent.py            【框架】                       │
│  ─────────────────────────────────────────────────────  │
│  · @tool 装饰器        把普通函数变成"工具说明书"          │
│  · Agent 类            ReAct 循环 + 多实例状态            │
│  · 不认识任何具体工具，只认识"有 _schema 属性的函数"        │
└─────────────────────────────────────────────────────────┘
                    ↑ 生产 _schema        ↓ 消费 _schema
┌─────────────────────────────────────────────────────────┐
│  apps/                    【应用】                       │
│  ─────────────────────────────────────────────────────  │
│  assistant.py        assistant 应用：查天气 / 算数 / 时间  │
│  coding_agent.py     coding 应用：读写文件 / 执行命令      │
└─────────────────────────────────────────────────────────┘
```

**关键约定：`@tool` 生产 `_schema`，`Agent` 消费 `_schema`。**

两者是同一个约定的两端，**所以 `@tool` 必须属于框架，不能属于应用** —— 否则每个应用都要重新实现一遍。

### 这套抽象成立的证据

| 应用 | 工具数 | 需要改 `core/agent.py` 吗 |
|---|---|---|
| assistant | 4 | — |
| coding_agent | 3（含路径沙箱、命令执行） | **一行未改** |

添加 `coding_agent` 时，只做了两件事：写工具函数加 `@tool`、把它加进 `Agent(tools=[...])`。

---

## 目录结构

```
.
├── MiniAgent/
│   ├── core/                    ← 框架（不含任何具体工具）
│   │   ├── agent.py      179 行   ReAct 循环 + 多实例状态
│   │   ├── retry.py       68 行   指数退避重试
│   │   └── logger.py      47 行   结构化日志（JSONL）
│   │
│   ├── apps/                    ← 应用
│   │   ├── assistant.py   49 行   4 个工具 + SYSTEM_PROMPT
│   │   └── coding_agent.py 262 行  3 个工具 + 路径沙箱 + 命令拦截
│   │
│   ├── workspace/               ← Coding Agent 的沙箱目录（gitignore）
│   ├── logs/                    ← 运行日志（gitignore）
│   ├── main.py            15 行   assistant 入口
│   ├── main_coding.py     15 行   coding agent 入口
│   └── selftest.py       282 行   37 项自动化自检
│
└── hello_agent.py              ← v1：单文件版本，保留作为演进记录
```

---

## 快速开始

**1. 配置 API Key**

在项目根目录建 `.env`：

```
DEEPSEEK_API_KEY=sk-xxxxxxxx
```

**2. 进入项目目录**

```bash
cd MiniAgent
```

> ⚠️ 必须在 `MiniAgent/` 下运行，否则 `from core.agent import ...` 会失败。
> 因为 Python 找模块是看**当前目录**的。

**3. 运行**

```bash
# 方式一：已激活虚拟环境
python main.py

# 方式二：直接用 venv 里的解释器（Windows，未激活环境时）
..\.venv\Scripts\python.exe main.py
```

**三个入口：**

```bash
# 日常助手（查天气 / 算数 / 时间 / 股票）
main.py

# Coding Agent（读写文件 / 执行命令）
main_coding.py

# 自检（37 项，全绿才算环境正常）
selftest.py
```

---

## 已经验证过的能力

| 能力 | 实现 | 验证方式 |
|---|---|---|
| **Function Calling 循环** | 模型返回 `tool_calls` → 执行 → 结果回喂 → 再问 | 真实对话 |
| **工具自动注册** | `@tool` 读函数签名生成 JSON Schema | 检查 `required` 字段 |
| **多实例状态隔离** | 状态存在 `self.messages`，不是全局变量 | 两个 Agent 记忆互不污染 |
| **并发工具调用** | `for tool_call in msg.tool_calls`（不是 `[0]`） | 一轮返回 2 个 `write_file` 并全部执行 |
| **指数退避重试** | 只重试网络 / 429 / 5xx，客户端错误立刻抛 | 单元测试 5 项 |
| **结构化日志** | JSONL，5 种事件类型，写失败不影响主流程 | 读回解析验证 |
| **路径沙箱** | `abspath + startswith(WORKSPACE + os.sep)` | `../../.env` 被拒绝 |
| **危险命令拦截** | 黑名单 + 归一化（挡 `DEL /S`、`del/s` 变体） | 单元测试 5 项 |
| **37 项自动化自检** | 覆盖读/写/执行/安全/重试/日志 | `selftest.py` 全绿 |

---

## 一个真实运行记录

**任务**：`帮我在 workspace 里创建 hello.py，打印 1 到 10 的平方，然后运行它`

```
--- 第 1 轮 ---
  模型要调工具: write_file({'path': 'hello.py', 'content': 'for i in range(1, 11):...'})
  工具返回: 已写入 hello.py（62 字节）

--- 第 2 轮 ---
  模型要调工具: run_command({'command': 'python3 hello.py'})
  工具返回: 命令失败（返回码 9009）          ← Windows 没有 python3

--- 第 3 轮 ---
  模型要调工具: run_command({'command': 'python hello.py'})
  工具返回: 1 的平方是 1 / 2 的平方是 4 / ... / 10 的平方是 100

--- 第 4 轮 ---
  最终回答: 完成。另外说明：本环境中 python3 不可用，需要用 python 运行。
```

**注意第 2→3 轮**：代码里**没有任何"python3 失败就换 python"的逻辑**。
模型看到返回码 9009，自己判断是"命令不存在"，换了写法重试。

**这就是 ReAct 里 Observation 的价值：失败不是终点，是一条新信息。**

> 后来为了不再浪费这一轮，我在 `SYSTEM_PROMPT` 里注入了一段「运行环境」说明
> （Windows / cmd / Python 命令是 `python`），直接把 4 轮降到 3 轮。

---

## 设计取舍（我刻意没做的事）

**这一节比上面所有功能都重要 —— 因为它说明我知道边界在哪。**

| 没做 | 为什么 |
|---|---|
| **容器沙箱** | 危险命令黑名单只是"减速带"，不是"墙"。只要模型能调 `python`，就能用 `shutil.rmtree` 绕过关键词检查。真正的方案是 Docker + 只读挂载，但部署复杂度对学习项目不划算。 |
| **上下文压缩** | `messages` 只增不减，聊久了会串台甚至超上限。**这是已知缺陷**，压缩方案在后续计划里。 |
| **流式输出** | 命令行场景收益低，等有 Web 界面时再做。 |
| **MCP 协议** | 想做，但它属于"扩展能力"，优先级低于可靠性。 |
| **子 Agent / 多 Agent** | 这个项目的定位是"单 Agent 内核"，多 Agent 编排放在主项目里做。 |
| **登录 / 用户系统** | 演示项目不需要，用 `user_id` 参数代替反而更清晰。 |

---

## 已知问题

1. **`self.messages` 无限增长** —— 聊 30 轮以上会开始重复前面内容，100 轮会超上下文上限。
2. **黑名单可被绕过** —— 见上表。已实测：`python -c "import shutil; shutil.rmtree(...)"` 能穿过。
3. **工具串行执行** —— 模型一次返回多个 `tool_calls` 时，是顺序执行的，没有并发。
4. **没有重试降级** —— 重试 3 次都失败后，异常直接抛到入口，用户看到的是堆栈。

---

## 后续计划

围绕「Agent 可靠性四问」补齐能力：

| 问题 | 计划 |
|---|---|
| 状态为什么会漂移 | 任务清单（task_create / update）+ Plan Mode |
| 工具为什么不会乱调 | 权限系统（白名单 + 默认拒绝）+ auto 模式分类器 |
| 上下文为什么越来越乱 | 上下文压缩（摘要 + 恢复最近文件）+ 分层记忆 |
| 断了怎么恢复 | Checkpoint 持久化 |

外加两个能力扩展：精确编辑（`edit_file`，search/replace 而不是整文件重写）、MCP 客户端。

---

## 技术栈

```
Python 3.11
OpenAI SDK        ← 只用了最基础的 chat.completions，没有用 Responses API
DeepSeek API      ← 兼容 OpenAI 协议，改 base_url 即可
python-dotenv     ← 读 .env
```

**没有 LangChain，没有 LangGraph，没有任何 Agent 编排库。**

---

## 演进记录

| 版本 | 内容 |
|---|---|
| v1 | `hello_agent.py`：单文件 301 行，跑通 ReAct 循环 |
| v2 | 状态从全局变量收进 `Agent` 类，多实例记忆隔离 |
| v3 | 拆成 `core/` + `apps/`，加第二个应用，框架零改动 |
| v4 | 加固：重试、日志、路径沙箱、命令拦截、37 项自检 |
