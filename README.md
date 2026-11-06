# MiniAgent

一个用 Python 手写的工具调用 Agent，采用 ReAct 风格的「模型决策 → 工具执行 → 结果回传」循环。两个 CLI 应用复用同一套运行时，分别演示函数调用和工作区文件操作。

核心只借助 OpenAI Python SDK 发起 DeepSeek 请求。工具 Schema、消息历史、工具校验与执行、调用结果配对、请求重试和日志由项目自己管理。

## 从一条请求开始

假设你问「计算 (18 + 24) / 6，再告诉我现在几点」。

1. CLI 把输入交给 Agent。Agent 将用户消息和工具说明一起发给模型。
2. 模型可在同一个响应里请求 `calculate` 和 `get_time`。Agent 先检查响应是否完整，再按返回顺序逐个校验和执行。
3. 每次调用都生成带原 `tool_call_id` 的结果。参数错了、工具不存在或执行失败也会回传对应结果。
4. Agent 把调用和结果一并送回模型。拿到最终回答后先写入会话历史，再交给 CLI 显示。

终端会按顺序显示模型请求、工具名和执行状态。例如，同一轮调用两个工具时：

```text
[第 1 轮] 请求模型
[第 1 轮] 模型请求工具 calculate
[第 1 轮] calculate → 成功
[第 1 轮] 模型请求工具 get_time
[第 1 轮] get_time → 成功
[第 2 轮] 请求模型
Agent: …
```

进度由程序在运行时输出，只包含事件元数据。工具参数、返回正文和模型的内部推理不会出现在进度行里。

| 层 | 源码 | 职责 |
| --- | --- | --- |
| 入口 | [cli.py](MiniAgent/cli.py) | 配置、客户端、交互循环 |
| 核心 | [agent.py](MiniAgent/core/agent.py) | 工具注册、请求循环、参数校验、调用结果与会话历史 |
| 应用 | [assistant.py](MiniAgent/apps/assistant.py)、[coding_agent.py](MiniAgent/apps/coding_agent.py) | 演示工具、工作区工具与角色提示 |
| 支撑 | [retry.py](MiniAgent/core/retry.py)、[logger.py](MiniAgent/core/logger.py) | 瞬时请求重试、JSONL 事件 |
| 验证 | [selftest.py](MiniAgent/selftest.py) | 工具和消息协议的离线回归测试 |

## 安装与离线自测

需要 Python **3.11+**。以下命令从仓库根目录运行。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe MiniAgent/selftest.py
```

macOS / Linux 将 Python 路径换成 `./.venv/bin/python`。自测无需 API Key，使用临时目录、预设响应和本地模拟 HTTP。覆盖同轮多工具、截断响应、工具执行中断、文件覆盖确认和本地脚本超时等行为。系统禁止创建符号链接时，对应用例会标记为跳过。

## 运行两个应用

先复制配置模板，把自己的 DeepSeek Key 填进 `.env`。默认模型为 `deepseek-flash`，CLI 显式使用非思考模式，聚焦基本工具调用协议。可以通过 `MINIAGENT_MODEL` 指定其他支持这种调用方式的 DeepSeek 模型。 [DeepSeek 工具调用文档](https://api-docs.deepseek.com/guides/tool_calls/)

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }

# 演示助手
.\.venv\Scripts\python.exe MiniAgent/main.py

# 编程助手，使用默认工作区 MiniAgent/workspace
.\.venv\Scripts\python.exe MiniAgent/main_coding.py
```

演示助手支持算术、本机时间、天气与股票样例。天气和股票结果是固定演示数据。可以试「计算 (18 + 24) / 6，再告诉我现在几点」，然后追问「刚才的计算结果是多少」。

编程助手可试「在工作区新建 hello.txt，写入 hello MiniAgent，然后读回文件」。接着请求替换该文件，终端会列出目标路径，输入 `yes` 才批准覆盖。可用 `--workspace` 指定一个已有目录。两个入口都可用 `--help` 查看参数，输入 `q` 结束当前会话。

```powershell
.\.venv\Scripts\python.exe MiniAgent/main_coding.py --enable-python
```

## 执行边界

- 默认注册 `list_files`、`read_file`、`write_file`。文件工具限制在选定工作区，文本读写各有 16 KiB 上限，目录列表最多 100 项。覆盖需要模型传入 `overwrite=true`，并由用户在终端确认。批准后会再次检查目标路径和文件状态。
- Python 执行默认关闭。启用后只接收工作区内现有的 `.py` 文件，每次都在终端确认，文件在确认期间变动时会拒绝启动。脚本以当前用户权限运行，请只批准自己检查过的脚本。对子进程的等待上限为 15 秒，返回至多 4 KiB 的输出正文。
- 每条输入默认最多发起 5 轮逻辑模型请求。连接错误、HTTP 429 和 5xx 最多额外重试两次，只重试请求。模型输出被截断时不会执行其中的工具。工具批次被中断时，会保留已完成的结果、补齐调用 ID，并区分状态未知和未执行的动作。已执行动作的副作用需要检查实际文件或输出。
- 日志写在 `MiniAgent/logs`，以 `turn_id` 和 `tool_call_id` 串起事件。应用日志仅记录元数据，当前会话文本和工具结果放在内存，并作为请求上下文发给模型。退出后会话历史清空。

## 复习与后续扩展

- [复习与面试手册](docs/MiniAgent_完全手册_复习与面试版.md) 按架构、核心、工具和测试组织，有 144 道分档练习。
- [带侧栏的阅读版](docs/MiniAgent_目录阅读版.html) 可在本地浏览器打开，有模块导航、题库和每日复习记录。
- 十项扩展中，集中工具执行已完成。后续规划为权限、局部编辑、计划模式、任务清单、会话持久化、请求追踪、上下文压缩、长期记忆与 MCP。手册第 13 章给出了各项验收点。

`.env` 保存本地配置，`.venv/` 安装依赖，`MiniAgent/workspace/` 存工作文件，`MiniAgent/logs/` 存运行事件。这些路径和 Python 的 `__pycache__/` 都由 Git 忽略。换电脑时用仓库里的 `.env.example` 和 `requirements.txt` 重建配置与环境。
