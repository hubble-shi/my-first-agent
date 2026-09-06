# My First Agent — 最小可运行的 ReAct Agent

> 一个不依赖任何 Agent 框架、纯手写的 LLM 工具调用循环。
> Python 3.11 + DeepSeek API + OpenAI SDK

---

## 它能做什么

这个 Agent 会自己判断「这个问题需不需要查数据」，需要就调工具，拿到结果后再回答。

```
你: 北京和上海哪个热？

--- 第 1 轮 ---
模型要调工具: get_weather(北京)  →  晴，26度，微风
模型要调工具: get_weather(上海)  →  多云，30度，湿度大
--- 第 2 轮 ---
最终回答: 上海更热（30°C vs 26°C，且湿度大体感更闷）
```

注意它**没有直接回答**——它先去拿了两个城市的数据，才做对比。这就是 Agent 和普通聊天机器人的区别。

内置两个工具：

| 工具 | 作用 |
| --- | --- |
| `get_weather(city)` | 查询城市天气 |
| `calculate(expression)` | 计算数学表达式 |

---

## 快速开始

**1. 安装依赖**

```bash
pip install openai python-dotenv
```

**2. 配置 API Key**

在项目根目录创建 `.env` 文件：

```
DEEPSEEK_API_KEY=sk-你的key
```

**3. 运行**

```bash
python hello_agent.py
```

输入 `q` 退出。

---

## 核心：ReAct 循环

整个 Agent 的本质就是这段代码（约 30 行）：

```python
for turn in range(5):                       # 最多转 5 轮，防止死循环
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        tools=tools,                        # 告诉模型有哪些工具可用
    )
    msg = response.choices[0].message

    if msg.tool_calls:                      # 情况 A：模型要调工具
        messages.append(msg)
        for tool_call in msg.tool_calls:    # ⚠️ 注意：可能一次返回多个调用
            result = tool_map[name](**args) #     执行真正的 Python 函数
            messages.append({               #     把结果塞回对话
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })
        continue                            # 回到循环开头，让模型继续思考

    return msg.content                      # 情况 B：模型给出最终答案
```

流程：

```
思考 → 决定调工具 → 执行 → 观察结果 → 再思考 → … → 回答
```

这个循环叫 **ReAct**（Reasoning + Acting），是 LangGraph、Claude Code 等所有 Agent 框架最底层的那一层。

---

## 实现中的两个关键点

**1. 一次请求可能返回多个工具调用（parallel tool calls）**

问「北京和上海哪个热」时，模型会在同一轮里返回**两个** `get_weather` 调用。
所以必须用 `for tool_call in msg.tool_calls` 遍历，如果只取 `tool_calls[0]`，第二个城市的数据就丢了，模型会开始编答案。

**2. 为什么需要工具？**

LLM 的本质是预测下一个 token，它不做数学运算。
问 `12345 * 6789`，纯靠模型大概率算错；接上 `calculate` 工具后，答案是精确的 `83810205`。

> 模型不擅长的，用工具补上 —— 这是 Agent 最核心的价值。

---

## 项目结构

```
agent-study/
├── hello_agent.py    # 主程序：工具定义 + Agent 循环
├── .env              # API Key（不上传）
├── .gitignore
└── .venv/            # 虚拟环境（不上传）
```

---

## Roadmap

- [x] 最小 ReAct 循环 + 工具调用
- [ ] 把工具定义改成装饰器自动注册（`@tool`）
- [ ] 加对话记忆（多轮上下文管理）
- [ ] 接入 MCP 协议，把工具抽成独立的 MCP Server
- [ ] 自研 Agent 框架（<200 行），不依赖任何第三方 Agent 库

---

## 说明

这是学习 Agent 开发过程中的第一个可运行项目，用于理解 ReAct 循环的底层实现。
代码全部手写，未使用 LangChain / LangGraph 等框架。
