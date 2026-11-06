# MiniAgent 完全手册 · 复习与面试版

> **v3.2 · 源码与离线自测**　16 个模块 · 144 道分档练习 · 14 次小步复习

先走 **01 → 03 → 04 → 05 → 06 → 12**，看懂一条请求怎样完成。日常可打开 [带侧栏的目录阅读版](MiniAgent_目录阅读版.html)，或从 [十四次复习路线](#151-十四次学习任务) 挑一节。

## 阅读导航

| 模块 | 学完能做什么 |
|---|---|
| [00 怎样使用这本手册](#00-怎样使用这本手册) | 选择首次通读或每日路线，知道每次读到哪里就可以停。 |
| [01 项目架构与一条任务的数据流](#01-项目架构与一条任务的数据流) | 画出入口、核心、模型与工具之间的数据流。 |
| [02 读源码必需的 Python 基础](#02-读源码必需的-python-基础) | 把列表、字典、函数、装饰器和异常读成实际执行步骤。 |
| [03 入口、导入与客户端生命周期](#03-入口导入与客户端生命周期) | 说明 CLI 从读取配置到发起模型请求的顺序。 |
| [04 工具注册与 JSON Schema](#04-工具注册与-json-schema) | 由 Python 函数签名推导 Schema，再预测执行校验。 |
| [05 Agent 构造与状态隔离](#05-agent-构造与状态隔离) | 分清 Agent 自己的状态、共享引用和文件工作区。 |
| [06 主循环与消息协议](#06-主循环与消息协议) | 手推一次调用批次，解释工具失败、回填与最终回答。 |
| [07 演示助手的四个工具](#07-演示助手的四个工具) | 看懂四个演示工具和受限算术的求值过程。 |
| [08 文件路径与读写工具](#08-文件路径与读写工具) | 解释路径解析、字节截断、独占创建与显式覆盖。 |
| [09 Python 脚本执行与权限边界](#09-python-脚本执行与权限边界) | 说清脚本注册、人工确认、启动、输出和系统权限。 |
| [10 重试规则与指数退避](#10-重试规则与指数退避) | 计算重试次数和等待顺序，理解副作用边界。 |
| [11 JSONL 日志与观测边界](#11-jsonl-日志与观测边界) | 按 ID 串起一次工具调用，说明日志的数据范围。 |
| [12 把 selftest 从头读懂](#12-把-selftest-从头读懂) | 用准备、执行、断言和清理拆解离线测试。 |
| [13 设计判断、当前缺口与十项扩展](#13-设计判断当前缺口与十项扩展) | 按当前完成项与后续验收点介绍项目。 |
| [14 面试表达与场景追问](#14-面试表达与场景追问) | 用具体调用流程和测试证据回答面试追问。 |
| [15 每日复习路线与维护卡](#15-每日复习路线与维护卡) | 按十四次路线小步复习并维护自己的疑问记录。 |

---

## 00 怎样使用这本手册

> **本模块目标**　选择首次通读或每日路线，知道每次读到哪里就可以停。

**小节直达**　[00.1](#001-这次重写的阅读约定) · [00.2](#002-首次读一遍只走主线) · [00.3](#003-每天一次最小学习循环) · [00.4](#004-题库怎样用) · [00.5](#005-跳转与阅读方式)

### 00.1 这次重写的阅读约定

正文对应现在的源码。代码摘录帮助你沿路径阅读，教学示例用来手推，后续扩展单独放在第 13 章。

### 00.2 首次读一遍只走主线

1. 看 01，画出用户、CLI、Agent、模型、工具之间的箭头。
2. 看 03 → 05，理解程序怎样启动，工具怎样变成说明书。
3. 看 06，用纸写出一次调用两个工具后的完整消息顺序。
4. 看 12，挑一个失败用例。先预测，再跑离线自测，最后解释断言。
5. 看 14，练三十秒介绍。读到陌生语法时随时回到 02。

### 00.3 每天一次最小学习循环

每天挑一节，先花一分钟回忆上次学到的函数。读完后做 A、B 各一题，再对照代码核对。能独立说出**输入、状态变化、输出、一个边界**，今天就可以停。

### 00.4 题库怎样用

01–12 各有 12 题。A 解释对象与语法，B 预测实际行为，C 说明设计选择与边界。先自己说一遍再展开答案。读过题目和能独立推演是两种进度。

### 00.5 跳转与阅读方式

Markdown 目录可以跳到章节和小节。带侧栏的 HTML 版还支持搜索、难度筛选、继续上次和十四次复习路线。复习勾选保存在浏览器本地，换浏览器或路径时进度可能另算。

[返回全书目录](#阅读导航) · [下一模块 →](#01-项目架构与一条任务的数据流)

---

## 01 项目架构与一条任务的数据流

> **本模块目标**　画出入口、核心、模型与工具之间的数据流。

**小节直达**　[01.1](#011-项目究竟做了什么) · [01.2](#012-先看职责再看文件) · [01.3](#013-一条任务经过哪些数据) · [01.4](#014-状态到底放在哪里) · [01.5](#015-这套抽象怎么评价) · [本模块 12 题](#m01-a01-基础识别)

### 01.1 项目究竟做了什么

MiniAgent 把模型给出的工具请求转成 Python 函数调用，再把结果作为上下文交回模型。演示助手提供四个小工具，编程助手提供文件操作。两者共用同一个 `Agent`。

面试时可以说「我手写了一个 ReAct 风格的工具调用循环」。模型选择下一步行动，Python 执行工具，工具结果作为新的观察交回模型，模型再决定继续调用还是回答。ReAct 原论文让模型交替生成显式推理轨迹和动作。MiniAgent 用结构化的 `tool_calls` 表达动作，终端显示的是程序实际执行的步骤。 [ReAct 论文](https://arxiv.org/abs/2210.03629)

### 01.2 先看职责，再看文件

```text
用户 ↔ main.py / main_coding.py → cli.py
                                      ↓ 注入请求函数、模型名和工具列表
                                  core/agent.py
                                  ↙           ↘
                    SDK → DeepSeek             apps/ 下的 Python 函数
                    retry.py 包装请求            工作区路径检查与本地 I/O
                                      ↓
                         logger.py 记录关键事件
```

| 先读哪个文件 | 对它提的问题 |
|---|---|
| [cli.py](../MiniAgent/cli.py) | 谁读配置，谁创建 SDK 客户端，谁负责显示？ |
| [core/agent.py](../MiniAgent/core/agent.py) | 谁保存历史、验证参数、决定下一轮？ |
| [apps/assistant.py](../MiniAgent/apps/assistant.py) | 一次普通的算术工具调用怎样返回？ |
| [apps/coding_agent.py](../MiniAgent/apps/coding_agent.py) | 文件工具用哪个目录，哪些路径会被拒绝？ |
| [selftest.py](../MiniAgent/selftest.py) | 怎样绕开付费请求，验证一轮消息是否配对？ |

[源码 · cli.py · main](../MiniAgent/cli.py#L43)

### 01.3 一条任务经过哪些数据

你问「先计算 2+3，再查本机时间」。程序把用户消息和工具说明发给模型。模型可以回两个调用，每个包含函数名、参数 JSON 文本和调用 ID。程序解析参数、按顺序执行并回填两个结果。模型收到新历史后回答，CLI 显示文本。

### 01.4 状态到底放在哪里

`agent.messages` 是单个会话的列表。`agent.tools` 是可调用函数表，`agent.schemas` 是发给模型的说明列表。编程工具的闭包保存工作区，日志记录事件。退出进程后，已写的文件和日志还能查，消息历史随实例消失。

### 01.5 这套抽象怎么评价

新增一个同类型本地工具，可以用 `@tool` 生成说明，再把函数传给 Agent。更换模型传输则可以换 `complete`。面试时把这两个变化举成例子，再说明当前只处理同步、串行工具，单实例面向一个交互会话。

### 01.Q 分档自测与面试追问

#### M01-A01 基础识别

**入口、核心和工具各负责什么？**

<details>
<summary>展开参考答案</summary>

入口读配置并显示。核心负责请求、校验、执行与历史。工具各自完成实际业务动作。

</details>

#### M01-A02 基础识别

**模型如何知道可以调用哪些工具？**

<details>
<summary>展开参考答案</summary>

请求的 tools 字段包含可序列化的 Schema。模型返回调用意图，本地才用函数表找到真实 Python 函数。

</details>

#### M01-A03 基础识别

**项目使用了 SDK，它还算手写框架吗？**

<details>
<summary>展开参考答案</summary>

SDK 负责请求与响应格式；工具注册、调度、消息历史、执行回传、重试和事件由项目实现。

</details>

#### M01-A04 基础识别

**两个应用为什么共用一个 Agent？**

<details>
<summary>展开参考答案</summary>

任务的请求循环相同。应用层分别提供角色提示和工具列表。

</details>

#### M01-B01 代码推演

**一次输入收到两次模型响应、三个工具调用，怎样计数？**

<details>
<summary>展开参考答案</summary>

一次用户回合、两轮逻辑请求、三次工具执行。底层请求尝试还要加网络重试。

</details>

#### M01-B02 代码推演

**把天气工具换成文件工具，核心要懂路径吗？**

<details>
<summary>展开参考答案</summary>

工具在应用层绑定工作区和检查路径。核心通过统一的参数与结果接口调用。

</details>

#### M01-B03 代码推演

**两个 Agent 用同一个工作区会怎样？**

<details>
<summary>展开参考答案</summary>

各有自己的历史，但两个工具组都可能操作同一份磁盘文件。

</details>

#### M01-B04 代码推演

**重启后，哪部分还能看到？**

<details>
<summary>展开参考答案</summary>

实际文件和 JSONL 日志保留。当前会话的 messages 只在内存里，重启要重新开始。

</details>

#### M01-C01 面试追问

**不用 LangGraph，自己获得了什么练习？**

<details>
<summary>展开参考答案</summary>

能亲手推导模型请求、工具执行和消息协议，同时要自行处理出错、重试和状态边界。

**继续追问**　FitBot 使用 LangGraph 时，哪些工具边界仍需由你定义？

</details>

#### M01-C02 面试追问

**两个应用共用内核，足够证明能扩展吗？**

<details>
<summary>展开参考答案</summary>

这是本地函数接入的一条证据。复杂参数、远程工具、权限和并发还需要单独的接口与用例。

</details>

#### M01-C03 面试追问

**应如何向面试官交代当前验证范围？**

<details>
<summary>展开参考答案</summary>

说明离线测试验证运行时和协议，真实模型是否选对工具以及任务成功率需要另外验证。

</details>

#### M01-C04 面试追问

**给 Agent 接入外部工具，先检查什么？**

<details>
<summary>展开参考答案</summary>

参数结构、授权、失败语义、超时、结果大小与日志边界；先验证能否保留工具调用 ID。

**继续追问**　远程调用成功但本地没收到结果，重试会怎样？

</details>

[返回全书目录](#阅读导航) · [下一模块 →](#02-读源码必需的-python-基础)

---

## 02 读源码必需的 Python 基础

> **本模块目标**　把列表、字典、函数、装饰器和异常读成实际执行步骤。

**小节直达**　[02.1](#021-变量列表字典和真假值) · [02.2](#022-函数对象与函数调用) · [02.3](#023-位置参数与关键字展开) · [02.4](#024-类实例与-self) · [02.5](#025-装饰器属性与签名) · [02.6](#026-json字典字符串与字节) · [02.7](#027-读循环推导式与异常) · [本模块 12 题](#m02-a01-基础识别)

### 02.1 变量、列表、字典和真假值

变量是对象的名字，不是对象本身。`messages = []` 创建列表并把名字指向它；`messages.append(x)` 改列表内容。字典按键找值，列表按位置取元素：

```python
# 教学示例
messages = [{'role': 'user', 'content': '你好'}]
first = messages[0]
role = first['role']
```

`messages[0]` 得到第一个字典；`first['role']` 得到字符串 user。下标从 0 开始；`[-1]` 是最后一个。空列表、空字符串、None、0 在 if 中都被当作假，非空列表通常为真。因此 `if msg.tool_calls:` 表示“存在待处理调用”，不是检查它是否等于 True。

`a or b` 返回第一个真值对象，否则返回 b，不一定返回布尔值。`out or '(无输出)'` 是在两段文本间选择；`err or out` 并没有把两段输出合并。

### 02.2 函数对象与函数调用

```python
# 教学示例
action = get_time        # 取得函数对象，不执行
result = get_time()      # 立刻调用，取得结果
later = lambda: get_time()  # 制作一个以后可调用的动作
```

重试包装器需要反复执行同一动作，所以接收函数对象。若先写 `flaky()`，它可能在重试器接管之前就失败。lambda 是小型匿名函数，不是异步、不自动延迟到后台；只有调用它时才执行函数体。

### 02.3 位置参数与关键字展开

```python
# 教学示例
args = {'path': 'a.txt', 'content': 'hello'}
write_file(**args)
# 等同于 write_file(path='a.txt', content='hello')
```

调用处 `**args` 把映射展开成按参数名传入的值；`write_file(args)` 则只传了一个位置参数，通常缺少 content。`get_weather(args)` 不缺参数，却把整个字典当成 city，当前查表时会遇到不可哈希字典错误。

函数定义处 `def log_event(event, **fields)` 做相反的事：把额外关键字参数收集进 fields 字典。类型注解 `path: str` 是元信息，不会自动阻止你传整数。

### 02.4 类、实例与 self

`Agent` 是定义对象行为的类；`agent = Agent(...)` 创建一个实例；`agent.run('你好')` 可以理解成 `Agent.run(agent, '你好')`，实例被放进 self 参数。

构造函数中的 `messages = []` 只是局部名字；`self.messages = []` 设置实例属性，后续方法可以访问。属性不是永久存储，进程退出后内存不会自动留在磁盘。

对名字赋值与修改对象内容是两种操作。`self.requests = []` 把实例属性指向一个新列表；`self.requests.append(...)` 修改这个列表的内容。

### 02.5 装饰器、属性与签名

```python
# 教学示例
@tool
def hello(name: str):
    return '你好，' + name
```

它的注册效果等价于函数定义后执行 `hello = tool(hello)`。装饰器可以返回原函数，也可以返回包装函数；本项目给原函数挂 `_schema` 后原样返回，因此直接调用工具仍是普通函数调用。

函数也是对象，所以能有 `hello.__name__`、`hello.__doc__`、自定义的 `hello._schema`。`inspect.signature` 读取参数名、注解和默认值，不能代替实际调用验证。

[源码 · agent.py · tool](../MiniAgent/core/agent.py#L23)

### 02.6 JSON、字典、字符串与字节

```python
# 教学示例
import json
text = '{"city": "杭州"}'
obj = json.loads(text)
encoded = json.dumps(obj, ensure_ascii=False)
raw = '你好'.encode('utf-8')
decoded = raw.decode('utf-8')
```

text 与 encoded 是 str，obj 是 dict，raw 是 bytes。loads/dumps 面向字符串，load/dump 面向文件对象。JSON 不只有对象，还允许数组、数字等，因此解析成功不代表参数一定是字典。

`len('你好')` 是 2 个字符，UTF-8 编码后通常是 6 个字节。这解释了写文件统计字节时为何要先 encode。

### 02.7 读循环、推导式与异常

`range(1, 121)` 产生 1 到 120。`lines[:200]` 取开头最多 200 项，不包含索引 200；不足 200 项也不会补齐。`''.join(parts)` 把字符串片段拼起来；字符串本来带换行才会形成多行。

```python
# 教学拆解
selected = []
for line in result.splitlines():
    if line.startswith('第 '):
        selected.append(line)
# 原紧凑写法：[line for line in result.splitlines() if line.startswith('第 ')]
```

return 结束函数，continue 进入当前循环下一轮，raise 把异常交给外层。try 只保护它缩进范围内的语句；函数调用的参数会先求值。要验证函数会抛异常，应把可能失败的调用放入 `with self.assertRaises(...)`。

### 02.Q 分档自测与面试追问

#### M02-A01 基础识别

**messages 中列表与字典分别表示什么？**

<details>
<summary>展开参考答案</summary>

列表保留消息的先后顺序。字典描述一条消息的 role、content 等字段。

</details>

#### M02-A02 基础识别

**f 和 f() 有什么区别？**

<details>
<summary>展开参考答案</summary>

f 是函数对象，可以作为参数传入。f() 当场执行，并产生结果或异常。

</details>

#### M02-A03 基础识别

**调用处 **args 与定义处 **fields 方向相同吗？**

<details>
<summary>展开参考答案</summary>

调用处展开一个字典成关键字参数；定义处把收到的关键字参数收集成一个字典。

</details>

#### M02-A04 基础识别

**文件读到的 bytes 怎样变成 str？**

<details>
<summary>展开参考答案</summary>

用相应编码解码。相反，写文件前可把字符串用 UTF-8 编码成字节。

</details>

#### M02-B01 代码推演

**json.loads('[]') 返回什么，能直接 ** 展开吗？**

<details>
<summary>展开参考答案</summary>

得到列表。关键字展开需要映射，因此框架先检查参数是字典。

</details>

#### M02-B02 代码推演

**空字符串 text 与「无输出」做 or 会怎样？**

<details>
<summary>展开参考答案</summary>

空字符串为假，表达式返回后面的默认字符串。

</details>

#### M02-B03 代码推演

**range(1, 4) 和 lines[:2] 包含哪些项？**

<details>
<summary>展开参考答案</summary>

range 产生 1、2、3。切片取下标 0、1 的元素，短于两项时取已有元素。

</details>

#### M02-B04 代码推演

**为什么 ScriptedModel 保存请求时需要 deepcopy？**

<details>
<summary>展开参考答案</summary>

请求里的 messages 是会变化的列表。拷贝把当时的内容和嵌套对象独立保存。

</details>

#### M02-C01 面试追问

**类型注解自动阻止错误类型吗？**

<details>
<summary>展开参考答案</summary>

Python 普通函数调用不会按注解自动检查。装饰器生成说明，执行入口负责实际检查。

</details>

#### M02-C02 面试追问

**只用 class 就一定不会共享状态吗？**

<details>
<summary>展开参考答案</summary>

类属性、引用同一个可变对象或共享外部目录都能造成共享；这里实例历史在构造时新建。

</details>

#### M02-C03 面试追问

**为什么调用 write() 再传给断言接不住异常？**

<details>
<summary>展开参考答案</summary>

参数先求值，异常在断言收到参数前就发生。把可能失败的调用放进 assertRaises 上下文。

</details>

#### M02-C04 面试追问

**装饰器返回原函数与包装函数有何差别？**

<details>
<summary>展开参考答案</summary>

返回原函数保留对象和调用方式；包装函数可增加调用行为，但需处理签名与元数据。

</details>

[返回全书目录](#阅读导航) · [下一模块 →](#03-入口导入与客户端生命周期)

---

## 03 入口、导入与客户端生命周期

> **本模块目标**　说明 CLI 从读取配置到发起模型请求的顺序。

**小节直达**　[03.1](#031-从命令行启动到等待输入) · [03.2](#032-import-会执行哪些事) · [03.3](#033-配置客户端请求是三个时刻) · [03.4](#034-路径与运行环境不要混为一谈) · [03.5](#035-读完做一次口述) · [本模块 12 题](#m03-a01-基础识别)

### 03.1 从命令行启动到等待输入

`main.py` 调用 `main()`，`main_coding.py` 调用 `main(coding=True)`。`cli.py` 先解析参数，再读取仓库根目录的 `.env`。接着选工具、创建客户端、构造 Agent，最后进入 `while True`。每条非空输入执行一次 `agent.run(question)`，CLI 负责打印返回文本。

[源码 · cli.py · main](../MiniAgent/cli.py#L43)

### 03.2 import 会执行哪些事

导入模块时，Python 执行模块顶层语句。函数定义会建立函数对象，`@tool` 会在定义时生成 Schema。客户端构造在 `main` 里，导入核心或运行离线测试都不需要 Key。`if __name__ == "__main__"` 让入口只在脚本直接运行时启动。

### 03.3 配置、客户端、请求是三个时刻

1. `load_dotenv(...)` 把配置加载进环境，已有系统变量优先。
2. `with OpenAI(...) as client` 管理客户端生命周期，设置 DeepSeek 地址、20 秒 SDK 请求超时和 `max_retries=0`。
3. `partial` 给 `client.chat.completions.create` 预填 DeepSeek 的非思考模式选项。Agent 只得到 `complete`，在循环里传模型名、消息和工具说明。这个入口用基础文本与工具协议。

### 03.4 路径与运行环境不要混为一谈

仓库根目录用来找 `.env`。编程工具默认操作 `MiniAgent/workspace`。`--workspace .\my-demo` 里的相对路径从启动 CLI 的当前目录解析。`sys.executable` 则是当前正在运行 CLI 的 Python 路径，脚本工具用它启动同一个解释器。

| 本地看到的名字 | 用途 |
|---|---|
| `.env` | 保存本地 API Key 和模型配置的小文本文件 |
| `.venv/` | Python 虚拟环境，`Scripts/` 有启动用的 `python.exe`，`Lib/` 里有 SDK 等依赖 |
| `.env.example`、`requirements.txt` | 可以提交的配置模板和依赖清单，换电脑时用它们重建环境 |

当前 Trae 命令用 `\.venv\Scripts\python.exe` 运行。如果虚拟环境被删掉，需要重新创建并安装依赖，原来的命令才能继续使用。Git 忽略 `.env` 和 `.venv/`。

### 03.5 读完做一次口述

先运行两个入口的 `--help`。手推输入 `" q "` 时为什么会退出，按 Ctrl+C 又在哪里被处理。HTTP 状态错误和空模型响应由 CLI 显示简短提示，可以继续输入。普通 `q` 会退出循环并关闭客户端。

### 03.Q 分档自测与面试追问

#### M03-A01 基础识别

**两个入口最大的差别是什么？**

<details>
<summary>展开参考答案</summary>

main_coding.py 传 coding=True，因此多了解析工作区与执行开关的参数，并选择编程工具组。

</details>

#### M03-A02 基础识别

**入口的 __name__ 判断做什么？**

<details>
<summary>展开参考答案</summary>

仅在文件被直接当脚本运行时启动 CLI。导入时它只建立模块和函数。

</details>

#### M03-A03 基础识别

**读 .env、创建客户端、发请求怎样区分？**

<details>
<summary>展开参考答案</summary>

读配置准备环境值，创建客户端设定连接参数，循环中的 complete 才实际发送请求。

</details>

#### M03-A04 基础识别

**CLI 使用哪个服务，如何定位？**

<details>
<summary>展开参考答案</summary>

OpenAI Python SDK 请求显式配置的 DeepSeek base_url，默认使用 deepseek-flash。

</details>

#### M03-B01 代码推演

**导入 Agent 为什么不需要 API Key？**

<details>
<summary>展开参考答案</summary>

核心模块只定义函数和类。读取 Key 与创建客户端发生在 CLI 的 main 中。

</details>

#### M03-B02 代码推演

**为什么 --help 能在没有 Key 时工作？**

<details>
<summary>展开参考答案</summary>

参数解析先执行，帮助流程会输出后退出，尚未走到读取和验证 Key 的语句。

</details>

#### M03-B03 代码推演

**输入 ' q ' 与 'Q' 会发生什么？**

<details>
<summary>展开参考答案</summary>

strip 去掉两端空白，所以前者退出。Q 大小写不同，会作为提问处理。

</details>

#### M03-B04 代码推演

**q 后客户端何时关闭？**

<details>
<summary>展开参考答案</summary>

break 离开交互循环，然后退出 OpenAI 客户端的 with 块，资源被关闭。

</details>

#### M03-C01 面试追问

**如何让自检无需真实 Key？**

<details>
<summary>展开参考答案</summary>

给 Agent 注入预设响应函数，或者给实际 SDK 注入 MockTransport。

</details>

#### M03-C02 面试追问

**为什么 CLI 用 partial？**

<details>
<summary>展开参考答案</summary>

先给 SDK 请求绑定 DeepSeek 的非思考模式选项，让 Agent 核心只调用传入的 complete。

</details>

#### M03-C03 面试追问

**命令中的 python 与 sys.executable 有何差别？**

<details>
<summary>展开参考答案</summary>

python 依赖 shell 查找顺序；sys.executable 是当前解释器的路径。

</details>

#### M03-C04 面试追问

**系统提示能代替 CLI 参数与真实检查吗？**

<details>
<summary>展开参考答案</summary>

提示影响模型选择，工作区限制、工具注册与确认来自程序逻辑。

</details>

[返回全书目录](#阅读导航) · [下一模块 →](#04-工具注册与-json-schema)

---

## 04 工具注册与 JSON Schema

> **本模块目标**　由 Python 函数签名推导 Schema，再预测执行校验。

**小节直达**　[04.1](#041-工具说明与可执行函数分开) · [04.2](#042-按数据变化读装饰器) · [04.3](#043-从一个有默认参数的例子推导) · [04.4](#044-empty-与-none-分别表示什么) · [04.5](#045-当前支持范围与执行校验) · [本模块 12 题](#m04-a01-基础识别)

### 04.1 工具说明与可执行函数分开

`Agent.tools["read_file"]` 是 Python 函数。`Agent.schemas` 里的描述可以编码成 JSON 发给模型。用手册类比，Schema 是菜单，函数是厨师，模型发回的是点单。

### 04.2 按数据变化读装饰器

`@tool` 读取签名和类型注解，遍历参数，把 `str/int/float/bool` 转为 `string/integer/number/boolean`。没有默认值的参数进入 `required`。函数名、文档字符串与参数描述一起存到 `func._schema`，装饰器最后返回原函数。可以在 [agent.py](../MiniAgent/core/agent.py) 顺着 `tool → _matches_type → execute_tool` 对照。

[源码 · agent.py · tool](../MiniAgent/core/agent.py#L23)

### 04.3 从一个有默认参数的例子推导

```python
def write_file(path: str, content: str, overwrite: bool = False):
    ...
```

`properties` 有三个键。`required` 只有 `path` 和 `content`，因为 `overwrite` 已有默认值。模型只传前两个参数时，`func(**args)` 让 Python 使用 `False`。如果传了 `"overwrite": "true"`，字符串会在执行前被拒绝。

### 04.4 empty 与 None 分别表示什么

`inspect.Parameter.empty` 表示没有给默认值。`None` 可以作为 Python 默认值。当前 Schema 类型不含 JSON null，所以对 `value: str = None` 来说，省略参数与显式传 `null` 结果不同。项目内置工具使用和注解一致的默认值。

### 04.5 当前支持范围与执行校验

装饰阶段拒绝未支持的注解、位置专用参数和可变长参数。执行阶段才检查模型传回的 JSON、对象结构、必填键、额外键和实际类型。`bool` 在 Python 是 `int` 的子类，运行时使用精确类型判断防止 `true` 混进整数参数。`number` 接收整数或有限浮点数。

解析 JSON 时，`object_pairs_hook` 会收到键值对列表。`_unique_json_object` 逐个检查键是否已经出现。这样 `{"overwrite":false,"overwrite":true}` 会被拒绝，避免默认解析悄悄采用后一个值。

[源码 · agent.py · execute_tool](../MiniAgent/core/agent.py#L153)

### 04.Q 分档自测与面试追问

#### M04-A01 基础识别

**tool 装饰器的主要步骤是什么？**

<details>
<summary>展开参考答案</summary>

读取签名和注解，整理类型与必填项，写入 _schema，返回原函数。

</details>

#### M04-A02 基础识别

**properties 和 required 各表示什么？**

<details>
<summary>展开参考答案</summary>

properties 描述允许的键及类型；required 列出必须给出的键。

</details>

#### M04-A03 基础识别

**函数没有文档字符串时会怎样？**

<details>
<summary>展开参考答案</summary>

description 是空字符串，注册仍可完成。

</details>

#### M04-A04 基础识别

**str、int、float、bool 对应哪些 Schema 类型？**

<details>
<summary>展开参考答案</summary>

依次是 string、integer、number、boolean。

</details>

#### M04-B01 代码推演

**repeat(text: str, times: int=1) 必填哪些？**

<details>
<summary>展开参考答案</summary>

只必填 text。省略 times 时由 Python 使用 1。

</details>

#### M04-B02 代码推演

**参数 value: str = None 时，省略与传 null 一样吗？**

<details>
<summary>展开参考答案</summary>

省略使用默认值 None；显式 null 解码为 None，会因类型不符合 string 被拒绝。

</details>

#### M04-B03 代码推演

**直接调用带 @tool 的 read_file 会经过核心校验吗？**

<details>
<summary>展开参考答案</summary>

它是普通函数调用，执行工具自身的路径和读写逻辑。execute_tool 的参数校验发生在框架入口。

</details>

#### M04-B04 代码推演

**工具参数写 list[str] 或 *args 会怎样？**

<details>
<summary>展开参考答案</summary>

装饰器无法生成当前支持的 Schema，会在装饰阶段报 TypeError。

</details>

#### M04-C01 面试追问

**Schema 正确还需要执行时检查吗？**

<details>
<summary>展开参考答案</summary>

需要。模型输出是外部输入，仍可能漏字段、给错类型或返回坏 JSON。

</details>

#### M04-C02 面试追问

**同名工具为什么在 Agent 构造时检查？**

<details>
<summary>展开参考答案</summary>

只有装配同一实例时，才知道两个函数会争抢同一个名字。

</details>

#### M04-C03 面试追问

**为什么用 type(value) is int？**

<details>
<summary>展开参考答案</summary>

Python 的 bool 是 int 的子类。精确检查避免把 JSON true 当作整数。

</details>

#### M04-C04 面试追问

**以后要支持 MCP 的复杂参数，如何演进？**

<details>
<summary>展开参考答案</summary>

先引入能描述函数名、Schema、调用方式的工具表示，再选用能处理对象、数组的 Schema 校验，并保留现有回归。

**继续追问**　本地函数和远端工具的授权是否应该走同一入口？

</details>

[返回全书目录](#阅读导航) · [下一模块 →](#05-agent-构造与状态隔离)

---

## 05 Agent 构造与状态隔离

> **本模块目标**　分清 Agent 自己的状态、共享引用和文件工作区。

**小节直达**　[05.1](#051-构造函数装配了什么) · [05.2](#052-工具列表怎样被消费) · [05.3](#053-两个实例为什么不串历史) · [05.4](#054-必填角色与默认预算的取舍) · [本模块 12 题](#m05-a01-基础识别)

### 05.1 构造函数装配了什么

构造 Agent 时传入工具、角色提示、`complete`、模型名和可选的轮数上限。它记录请求函数与配置，创建独立的 `tools`、`schemas` 和 `messages`。第一条消息是 `system`，内容来自应用层的角色提示。

[源码 · agent.py · __init__](../MiniAgent/core/agent.py#L126)

### 05.2 工具列表怎样被消费

构造函数逐一检查工具有无 `_schema` 和重名情况，然后建立 `名字 → 函数` 映射并收集 Schema。重名在装配阶段报错，可以在启动时发现。`max_turns` 要求是正整数，默认 5。

### 05.3 两个实例为什么不串历史

```python
a = Agent(tools, "数学助手", complete=fake_complete, model="fake")
b = Agent(tools, "文件助手", complete=fake_complete, model="fake")
```

只调用 `a.run(...)` 时，`b.messages` 仍只有 system。两个实例可以引用同一个工具函数和它的 Schema，因此不要原地修改 Schema。编程应用要隔离文件，用不同目录分别调用 `build_tools`；多个实例指向同一路径时仍会操作同一份文件。

### 05.4 必填角色与默认预算的取舍

核心不知道用户要数学还是编程，所以角色由应用提供。`max_turns` 计数的是一次输入内的模型决策轮数。每轮可能有多个调用，也可能有多个网络尝试。一个 Agent 用于一个交互会话，当前没有同一实例并发执行的保护。

### 05.Q 分档自测与面试追问

#### M05-A01 基础识别

**构造函数装配了什么？**

<details>
<summary>展开参考答案</summary>

角色消息、工具函数表、Schema 列表、请求函数、模型名和轮数预算。

</details>

#### M05-A02 基础识别

**tools 字典为什么不直接发给模型？**

<details>
<summary>展开参考答案</summary>

字典里存真实 Python 函数；模型请求应携带可序列化的说明。

</details>

#### M05-A03 基础识别

**messages 初始值是什么？**

<details>
<summary>展开参考答案</summary>

一个只含 system 消息的列表，正文是应用提供的角色提示。

</details>

#### M05-A04 基础识别

**轮数上限默认是多少，要求什么类型？**

<details>
<summary>展开参考答案</summary>

默认 5，要求正整数，布尔值也会被拒绝。

</details>

#### M05-B01 代码推演

**a、b 两个实例，只有 a 收到一轮消息，b 的历史怎样？**

<details>
<summary>展开参考答案</summary>

b 仍只有自己的 system 消息。

</details>

#### M05-B02 代码推演

**同一个实例连续 run 会怎样？**

<details>
<summary>展开参考答案</summary>

它会继续向自己的 messages 追加上下文，因此后续请求可看到前面的会话。

</details>

#### M05-B03 代码推演

**注册一个没加 @tool 的函数会怎样？**

<details>
<summary>展开参考答案</summary>

构造时因为没有 _schema 抛 TypeError。

</details>

#### M05-B04 代码推演

**传两个同名工具会怎样？**

<details>
<summary>展开参考答案</summary>

构造时抛 ValueError，避免执行表和工具说明产生歧义。

</details>

#### M05-C01 面试追问

**schemas 列表独立，列表里的字典也独立吗？**

<details>
<summary>展开参考答案</summary>

同一个函数的 _schema 可被多个实例引用。两个列表独立，所引用的 Schema 字典仍可能共享。

</details>

#### M05-C02 面试追问

**同一个实例并发处理多个用户输入会怎样？**

<details>
<summary>展开参考答案</summary>

历史可交错，工具调用和结果顺序无法保证。当前 CLI 按一个会话串行使用。

</details>

#### M05-C03 面试追问

**工具实例和工作区隔离有什么关系？**

<details>
<summary>展开参考答案</summary>

每次 build_tools 产生一组捕获根目录的闭包；要隔离磁盘数据，应为会话选不同工作区。

</details>

#### M05-C04 面试追问

**max_turns 能限制全部工具和网络尝试数吗？**

<details>
<summary>展开参考答案</summary>

它限制逻辑模型轮数；一个响应可以带多个工具，网络错误还可能触发重试。

</details>

[返回全书目录](#阅读导航) · [下一模块 →](#06-主循环与消息协议)

---

## 06 主循环与消息协议

> **本模块目标**　手推一次调用批次，解释工具失败、回填与最终回答。

**小节直达**　[06.1](#061-先把一次用户输入和一轮模型请求分开) · [06.2](#062-把大函数压成四个动作) · [06.3](#063-请求发出前后发生什么) · [06.4](#064-工具分支逐步手推) · [06.5](#065-为什么调用与结果必须配对) · [06.6](#066-最终回答怎样进入历史) · [06.7](#067-轮数到了以后已执行动作怎样处理) · [06.8](#068-一张异常地图) · [本模块 12 题](#m06-a01-基础识别)

### 06.1 先把一次用户输入和一轮模型请求分开

一次 `run` 处理一条用户输入。一次 `for` 迭代包含一轮逻辑请求。如果第一轮返回两个工具请求，第二轮返回文本，就有一次用户输入、两轮模型决策、两次工具执行。网络重试可能额外增加请求尝试。

### 06.2 把大函数压成四个动作

```text
追加 user
  ↓
请求模型，转换成普通 assistant 字典
  ├─ 带工具调用：保存 assistant → 逐条执行与追加 tool → 继续循环
  └─ 带最终文本：保存 assistant → 返回文本给 CLI
```

打开 [agent.py](../MiniAgent/core/agent.py)，先看 `run` 怎样区分工具批次和最终回答。然后读 `_append_tool_batch` 怎样保存调用与结果，再读 `execute_tool` 怎样形成一条结果。

复习时可以给三个函数各写一句话。`run` 管本次输入经历几轮模型请求。`_append_tool_batch` 管这批调用和结果怎样按 ID 排进历史。`execute_tool` 管单个工具能不能执行，以及怎样回传成功、拒绝或异常。把这三件事分开，面试时就能讲清问题发生在哪一层。

[源码 · agent.py · run](../MiniAgent/core/agent.py#L220)

### 06.3 请求发出前后发生什么

请求用 `self.complete(**request)` 发送，`call_with_retry` 包住请求动作。`_assistant_message` 先看 `finish_reason`。普通文本要以 `stop` 结束，工具批次要以 `tool_calls` 结束。即使截断的响应里已有一条看起来完整的写文件请求，`length` 也会让整批在进入历史、执行工具之前被拒绝。 [DeepSeek 响应字段](https://api-docs.deepseek.com/api/create-chat-completion/)

通过这一关后再检查字段形状和同批 ID。合格的 SDK 响应会被转换成普通字典，因此 `messages` 可以整体用 JSON 表示。

[源码 · agent.py · _assistant_message](../MiniAgent/core/agent.py#L74)

### 06.4 工具分支逐步手推

假设第一轮要调用 `a=calculate("2+3")` 和 `b=get_time()`。第一轮结束的历史为 `system → user → assistant(tool_calls=[a,b]) → tool(a,"5") → tool(b,时间)`。这个顺序也决定编程助手同轮先写后读时，后一个工具能读到前一个写进去的内容。

把这个顺序和终端对照。先看到「第 1 轮 请求模型」，接着是两个工具各自的请求与状态，再看到「第 2 轮 请求模型」。第 2 轮读到的是已经补齐两个 `tool` 结果的历史。也可以用写文件练习观察跨轮行为，模型可能先用一轮读文件，再用另一轮写入。

### 06.5 为什么调用与结果必须配对

模型按 ID 找对应结果。如果 `a` 的参数 JSON 破了，`execute_tool` 会回一条 `role="tool", tool_call_id="a"` 的错误结果。随后照常执行 `b`。没有工具 ID 的响应无法配对，因此先检查协议形状，再写入历史。

如果三条调用依次为 a、b、c，a 已完成，b 执行时被 Ctrl+C 打断，历史就保留 a 的结果，将 b 标为「完成状态未知」，将 c 标为「未执行」。`_append_tool_batch` 补齐相应 ID 后把中断交给上层，CLI 随即退出。如果在别处捕获中断并继续复用该 Agent，下一次请求仍能携带完整的调用与结果。

[源码 · agent.py · execute_tool](../MiniAgent/core/agent.py#L153)

### 06.6 最终回答怎样进入历史

第二轮返回「结果是 5」时，先保存 `{"role":"assistant","content":"结果是 5"}`，再把文本返回。下一条用户追问「刚才是多少」时，模型能看到这条旧回答。前一轮只有文本、完全没调工具时，同样会保存。

### 06.7 轮数到了以后，已执行动作怎样处理

`max_turns=1` 时第一轮仍可调用工具。写入成功后，结果会保留，CLI 收到「已达到上限」提示。当前没有额外一次模型总结，也没有自动撤销文件修改。面试中可用这个例子说明预算和副作用的关系。

### 06.8 一张异常地图

| 失败 | 处理位置 | 结果 |
|---|---|---|
| 连接失败、HTTP 429、5xx | `call_with_retry` | 按规则重试请求 |
| 空响应、生成截断、无法配对的调用 | `_assistant_message` 与 `run` | 执行前拒收响应，向 CLI 报错 |
| JSON 格式错误、键重复、工具或参数不合法 | `execute_tool` | 写入同 ID 的拒绝结果 |
| 工具预期失败或抛出异常 | `execute_tool` | 预期错误给出原因，意外错误给出异常类型 |
| 首轮请求失败或被 Ctrl+C 中断 | `run` | 移除本次未得到响应的用户消息 |
| 模型在工具执行后失败 | `run` | 保留已经配对的历史和实际产生的副作用 |
| Ctrl+C 中断工具批次 | `_append_tool_batch` | 保留已完成结果，补齐其余 ID，停止执行 |

### 06.Q 分档自测与面试追问

#### M06-A01 基础识别

**run 的两个主要分支按什么区分？**

<details>
<summary>展开参考答案</summary>

有 tool_calls 时执行工具并继续；有文本且无调用时保存最终回答并返回。都没有会报错。

</details>

#### M06-A02 基础识别

**为什么先追加 user 再发请求？**

<details>
<summary>展开参考答案</summary>

模型从当前 messages 读取本次问题和历史上下文。

</details>

#### M06-A03 基础识别

**tool_call_id 有什么用途？**

<details>
<summary>展开参考答案</summary>

把每条 tool 结果与发起调用的 ID 对上，同轮多个同名调用也可区分。

</details>

#### M06-A04 基础识别

**工具分支的 continue 和 return 有何差别？**

<details>
<summary>展开参考答案</summary>

continue 让模型再看包含工具结果的历史；return 会结束本次用户回合。

</details>

#### M06-B01 代码推演

**一轮带三个工具调用，按什么顺序执行？**

<details>
<summary>展开参考答案</summary>

按模型返回的顺序逐个执行，保存 assistant 请求后逐个追加 tool 结果。

</details>

#### M06-B02 代码推演

**两个普通问答都没用工具，历史有哪些角色？**

<details>
<summary>展开参考答案</summary>

system、user、assistant、user、assistant。

</details>

#### M06-B03 代码推演

**第一个工具的参数是合法 JSON 数组，第二个工具正常，会怎样？**

<details>
<summary>展开参考答案</summary>

第一条结果报告必须是 JSON 对象，第二个调用仍执行。两条结果都携带各自的原 ID。

</details>

#### M06-B04 代码推演

**max_turns=1，第一轮写文件成功，会怎样？**

<details>
<summary>展开参考答案</summary>

保存调用和写入结果，文件已经改变，向 CLI 返回达到轮数上限的提示。

</details>

#### M06-C01 面试追问

**统一执行入口解决了哪些问题？**

<details>
<summary>展开参考答案</summary>

在一处处理注册查找、解析、参数校验、工具异常与回传。主循环只管理请求和消息次序。

**继续追问**　权限检查应插在参数验证前还是执行前？分别会影响什么？

</details>

#### M06-C02 面试追问

**第二轮模型报错，已写的文件该如何解释？**

<details>
<summary>展开参考答案</summary>

历史保留第一次调用与结果；文件已经改变，当前项目没有跨工具事务或自动回滚。

</details>

#### M06-C03 面试追问

**第一项已写文件，第二项被中断，第三项还没开始。历史应该怎么处理？**

<details>
<summary>展开参考答案</summary>

保留第一项结果。第二项补同 ID 的结果并标记状态未知，第三项补同 ID 的结果并标记未执行。最后把中断交还调用者，避免重跑有副作用的工具。

**继续追问**　如何通过断言证明第三项从未启动，并且下一次请求仍能发送？

</details>

#### M06-C04 面试追问

**模型返回文本就代表完成了任务吗？**

<details>
<summary>展开参考答案</summary>

工具状态和最终文本可能不一致。要核实文件内容或其他目标状态，必要时再测真实模型。

</details>

[返回全书目录](#阅读导航) · [下一模块 →](#07-演示助手的四个工具)

---

## 07 演示助手的四个工具

> **本模块目标**　看懂四个演示工具和受限算术的求值过程。

**小节直达**　[07.1](#071-角色提示放在应用层) · [07.2](#072-天气工具就是字典查询) · [07.3](#073-计算器怎样只接受算术) · [07.4](#074-时间与股票分别是什么例子) · [07.5](#075-从工具函数想到验证) · [本模块 12 题](#m07-a01-基础识别)

### 07.1 角色提示放在应用层

`assistant.SYSTEM_PROMPT` 要求使用对应工具，并把固定数据标成演示。程序也在固定数据结果里附上「演示数据」标签。提示负责引导模型措辞，运行时负责校验调用。

### 07.2 天气工具就是字典查询

`data.get(city, "暂无数据")` 先查城市键，缺失时返回默认值。用北京和一个字典里不存在的城市各试一次，能看到命中和缺失两种结果。

### 07.3 计算器怎样只接受算术

`ast.parse(expression.strip(), mode="eval")` 把文本解析成表达式语法树，解析这一步没有执行表达式。`_arithmetic` 只处理数字、允许的二元运算和一元正负。`2 + 3 * 4` 的乘法节点先算出 12，再算加法得 14。遇到函数调用、取属性、幂运算或布尔常量，会走拒绝分支。长度、中间数值与除零另有限制。

[源码 · assistant.py · _arithmetic](../MiniAgent/apps/assistant.py#L27)

### 07.4 时间与股票分别是什么例子

`get_time()` 没有输入参数，返回带时区偏移的本机时间。`get_stock_price(code)` 接收字符串，但任何代码都返回固定的 100 元示例。自测时间时可以验证能解析出时区，避免断言一个会随时间变化的具体值。

### 07.5 从工具函数想到验证

直接调用 `calculate("1/0")` 会抛出 `ToolError`。模型经 `execute_tool` 调用时，才会收到「工具失败」的结果。一个测试验证算术语义，一个测试验证框架把异常转换成协议消息。

### 07.Q 分档自测与面试追问

#### M07-A01 基础识别

**天气数据从哪里来？**

<details>
<summary>展开参考答案</summary>

来自源码里的固定城市字典。

</details>

#### M07-A02 基础识别

**get_stock_price 实际返回什么？**

<details>
<summary>展开参考答案</summary>

股票代码和固定的 100 元演示价格。

</details>

#### M07-A03 基础识别

**get_time 为什么适合演示无参工具？**

<details>
<summary>展开参考答案</summary>

它不要求工具参数，调用模型时参数对象可以是 {}，结果来自本机时间。

</details>

#### M07-A04 基础识别

**ast.parse 之后是谁做计算？**

<details>
<summary>展开参考答案</summary>

_arithmetic 递归读语法树，只执行白名单里定义的算术。

</details>

#### M07-B01 代码推演

**天气字典找不到城市会怎样？**

<details>
<summary>展开参考答案</summary>

data.get 返回「暂无数据」，仍带有演示标签。

</details>

#### M07-B02 代码推演

**模型给天气工具传了对象而非字符串，会在哪失败？**

<details>
<summary>展开参考答案</summary>

execute_tool 会在调用天气函数前拒绝错误类型。

</details>

#### M07-B03 代码推演

**calculate('1/0') 会怎样？**

<details>
<summary>展开参考答案</summary>

直接调用时抛 ToolError。经框架执行时会回传带原 ID 的错误结果。

</details>

#### M07-B04 代码推演

**表达式 2+3*4 怎样求出 14？**

<details>
<summary>展开参考答案</summary>

先递归求右侧的乘法节点 3*4，再计算外层加法。

</details>

#### M07-C01 面试追问

**把天气 mock 改成真实服务，应改哪里？**

<details>
<summary>展开参考答案</summary>

工具实现、超时和失败处理。工具输入输出仍符合原接口时，核心循环可继续复用。

</details>

#### M07-C02 面试追问

**try/except 为什么无法为 eval 提供权限边界？**

<details>
<summary>展开参考答案</summary>

异常只能处理出错，任意表达式的副作用可能早已执行。当前做法先解析，再按允许的节点求值。

</details>

#### M07-C03 面试追问

**只读工具也要考虑什么？**

<details>
<summary>展开参考答案</summary>

读取的数据是否允许发送给模型，调用的成本与失败语义，以及外部内容可能影响模型判断。

</details>

#### M07-C04 面试追问

**演示工具简单，面试可展示什么？**

<details>
<summary>展开参考答案</summary>

用简单工具说明同一运行时复用，再用失败配对、先写后读和测试证据展示工程点。

</details>

[返回全书目录](#阅读导航) · [下一模块 →](#08-文件路径与读写工具)

---

## 08 文件路径与读写工具

> **本模块目标**　解释路径解析、字节截断、独占创建与显式覆盖。

**小节直达**　[08.1](#081-先定位路径基准) · [08.2](#082-路径检查究竟做了哪两件事) · [08.3](#083-读取按三个阶段走) · [08.4](#084-写入如何避免意外覆盖) · [08.5](#085-文件工具怎样接上核心) · [本模块 12 题](#m08-a01-基础识别)

### 08.1 先定位路径基准

`build_tools(workspace)` 把目录解析为绝对路径，再定义和返回一组函数。内部函数引用 `root`，调用时就能知道这组工具属于哪个工作区。这是闭包。换一个目录调用一次 `build_tools`，就得到绑定新根目录的工具组。

### 08.2 路径检查究竟做了哪两件事

`_workspace_path` 先检查路径格式，拒绝绝对路径、盘符、父级段、控制字符，以及以点或空格结尾的 Windows 路径段等。再对 `root / relative` 调用 `resolve()`，用 `is_relative_to(root)` 检查解析后的路径归属。符号链接指向外部时，在第二步挡住。检查和打开文件之间仍有时间间隔，共享可写目录或硬链接需要更强的隔离措施。

[源码 · coding_agent.py · _workspace_path](../MiniAgent/apps/coding_agent.py#L29)

### 08.3 读取按三个阶段走

先定位并检查是文件，再以 `rb` 读取最多 `limit + 1` 字节。第 `limit + 1` 个字节用来判断是否截断。最后用 UTF-8 解码并加提示。若字节上限落在汉字中间，增量解码器会保留未完成的尾部字节，返回完整字符。若前面的文本本身编码错误，则报 UTF-8 错误。

[源码 · coding_agent.py · _bounded_read](../MiniAgent/apps/coding_agent.py#L49)

### 08.4 写入如何避免意外覆盖

`write_file` 先将文本编码成字节，超过 16 KiB 就拒绝。无论是否传入 `overwrite=True`，都先试用 `xb` 独占创建。这样另一个进程刚建好的文件也会进入已有文件分支。新建时写到一半出错，会尝试清理自己创建的残缺文件。

目标已存在时，`overwrite=True` 只会发起覆盖请求，终端用户还要输入 `yes`。程序记录原文件的身份、大小和修改时间等信息，批准后复查。随后写入同目录的临时文件，替换前再复查一次。发现文件已变动就退出，原内容得以保留。最后一次检查与替换之间仍有并发间隙。

[源码 · coding_agent.py · _write_text](../MiniAgent/apps/coding_agent.py#L86)

### 08.5 文件工具怎样接上核心

`list_files` 只列当前目录的直接子项，最多返回 100 项。三种文件工具都通过 `@tool` 带上参数说明。核心只知道工具名、参数和结果，不需要知道哪一个工具正在访问文件系统。

### 08.Q 分档自测与面试追问

#### M08-A01 基础识别

**工作区根目录来自哪里？**

<details>
<summary>展开参考答案</summary>

CLI 选默认目录或用户提供的 --workspace，再交给 build_tools 保存解析后的根目录。

</details>

#### M08-A02 基础识别

**_workspace_path 的两层检查各是什么？**

<details>
<summary>展开参考答案</summary>

_workspace_path 先拒绝不合规路径格式，再检查 resolve() 的结果仍在根目录内。

</details>

#### M08-A03 基础识别

**为何要读取 limit + 1 字节？**

<details>
<summary>展开参考答案</summary>

多读的那个字节只用来判断是否存在截断。

</details>

#### M08-A04 基础识别

**xb 模式保护了什么？**

<details>
<summary>展开参考答案</summary>

仅在目标不存在时新建；已存在会抛 FileExistsError，原文件保持原样。

</details>

#### M08-B01 代码推演

**为什么使用 is_relative_to，而非字符串前缀？**

<details>
<summary>展开参考答案</summary>

路径按部件比较。相邻目录 workspace-other 的字符串前缀相同，但它不在 workspace 内。

</details>

#### M08-B02 代码推演

**恰好 16 KiB 的文件是否显示截断？**

<details>
<summary>展开参考答案</summary>

未读到第 16 KiB 之后的额外字节时不显示。

</details>

#### M08-B03 代码推演

**一行内容有五万字节，read_file 怎样返回？**

<details>
<summary>展开参考答案</summary>

依然按字节上限截断，行数不影响这个判断。

</details>

#### M08-B04 代码推演

**write_file 的 content 收到整数，模型调用时在哪失败？**

<details>
<summary>展开参考答案</summary>

execute_tool 按 string 类型拒绝，文件函数尚未开始。

</details>

#### M08-C01 面试追问

**resolve 后还会有哪些边界？**

<details>
<summary>展开参考答案</summary>

检查与打开间可能被并发替换路径，同文件系统上的硬链接也不是符号链接。可信演示目录与更强的系统级隔离是不同层的控制。

</details>

#### M08-C02 面试追问

**如何设计 edit_file 的最小正确行为？**

<details>
<summary>展开参考答案</summary>

用待匹配原文定位，恰好一次才替换；零处或多处匹配时保留文件。并发时还应验证版本。

**继续追问**　为什么按行号盲改更容易写错？

</details>

#### M08-C03 面试追问

**如何证明覆盖成功，避免只测创建？**

<details>
<summary>展开参考答案</summary>

先写第一版。分别试默认写入、没有确认回调的显式覆盖、用户拒绝的显式覆盖，读回文件确认仍是第一版。最后允许覆盖，再读回第二版。

</details>

#### M08-C04 面试追问

**两个 Agent 同时写同一文件，当前有何保证？**

<details>
<summary>展开参考答案</summary>

独占创建保护新文件。覆盖在批准后与替换前检查目标文件是否改变。检查和替换之间仍有间隙，同时使用同一目录的进程需要更严格的并发协调。

</details>

[返回全书目录](#阅读导航) · [下一模块 →](#09-python-脚本执行与权限边界)

---

## 09 Python 脚本执行与权限边界

> **本模块目标**　说清脚本注册、人工确认、启动、输出和系统权限。

**小节直达**　[09.1](#091-一条脚本请求的执行顺序) · [09.2](#092-为什么用参数列表启动进程) · [09.3](#093-subprocess-的参数各管一件事) · [09.4](#094-从-bytes-到文本) · [09.5](#095-一次拒绝说明了什么) · [本模块 12 题](#m09-a01-基础识别)

### 09.1 一条脚本请求的执行顺序

默认工具列表里没有 `run_python`。CLI 加 `--enable-python` 时传入批准函数，注册脚本工具。执行前检查工作区内的普通 `.py` 文件，再请终端用户确认。批准后复查路径与文件状态，两次检查之间有变化就拒绝启动。

[源码 · coding_agent.py · run_python](../MiniAgent/apps/coding_agent.py#L173)

### 09.2 为什么用参数列表启动进程

传给 `subprocess.run` 的第一个参数是列表。第一个元素为 `sys.executable`，最后一个元素为脚本绝对路径，中间是 Python 的 UTF-8 和非缓冲输出选项。路径里有空格也作为一个参数传入，避免拼接成任意 shell 字符串。

### 09.3 subprocess 的参数各管一件事

| 参数 | 作用 |
|---|---|
| `cwd=root` | 设置进程起始目录 |
| `env=environment` | 只继承 PATH 等少量变量，API Key 不直接传给子进程 |
| `stdin=DEVNULL` | 让脚本不能从当前终端读输入 |
| `stdout=output, stderr=STDOUT` | 标准输出和错误输出合并到临时文件 |
| `timeout=15` | 等待脚本进程最多约 15 秒，超时按错误处理 |

脚本拥有当前用户的系统权限。它仍可访问用户有权读取的其他文件、发网络请求或启动后代进程。请只批准你已检查和信任的脚本。当前超时针对直接子进程，临时文件在运行中的体积也没有 4 KiB 上限。

[源码 · coding_agent.py · _run_python](../MiniAgent/apps/coding_agent.py#L190)

### 09.4 从 bytes 到文本

进程完成后将临时输出文件的读指针移回开头，取前 4 KiB 正文并以 UTF-8 解码。脚本可能产生非法 UTF-8 字节，因此这里用替换字符保留可读部分。退出码非零时，错误结果包含退出码和有界输出。

### 09.5 一次拒绝说明了什么

用户拒绝或脚本在确认期间改变时，都应停在启动前。自测把 `_run_python` 换成可记录调用的替身，并断言它从未被调用。另一个用例批准脚本并真正用本地解释器运行，以验证启动路径和环境。

### 09.Q 分档自测与面试追问

#### M09-A01 基础识别

**run_python 默认注册吗？**

<details>
<summary>展开参考答案</summary>

默认关闭。CLI 加 --enable-python 时才把带逐次确认的工具加入注册表。

</details>

#### M09-A02 基础识别

**cwd、timeout、stdin 分别管什么？**

<details>
<summary>展开参考答案</summary>

依次设定起始目录、等待时限、输入来源。脚本标准输入来自 DEVNULL。

</details>

#### M09-A03 基础识别

**为什么用 sys.executable 和参数列表？**

<details>
<summary>展开参考答案</summary>

确保使用当前 Python，含空格的脚本路径也能作为一个独立参数传入，无需解释 shell 文本。

</details>

#### M09-A04 基础识别

**stdout 和 stderr 如何返回？**

<details>
<summary>展开参考答案</summary>

合并到临时文件，进程结束后最多读 4 KiB 正文并解码。

</details>

#### M09-B01 代码推演

**用户输入的确认内容不是 yes，会怎样？**

<details>
<summary>展开参考答案</summary>

函数抛 ToolError，启动进程的调用尚未发生。

</details>

#### M09-B02 代码推演

**脚本退出码是 3，同时打印了文本，会返回什么？**

<details>
<summary>展开参考答案</summary>

抛出包含退出码和有界输出的 ToolError。经统一入口后是一条对应的失败结果。

</details>

#### M09-B03 代码推演

**cwd 在工作区，脚本能访问绝对路径吗？**

<details>
<summary>展开参考答案</summary>

能，是否有权访问取决于当前用户的系统权限。

</details>

#### M09-B04 代码推演

**API Key 没有传给进程，脚本就一定读不到 Key 吗？**

<details>
<summary>展开参考答案</summary>

环境过滤只限制直接继承。脚本仍可能读取当前用户有权访问的配置文件。

</details>

#### M09-C01 面试追问

**如何验证拒绝时根本没启动进程？**

<details>
<summary>展开参考答案</summary>

把 _run_python 替换为 Mock，调用拒绝分支，再 assert_not_called。

</details>

#### M09-C02 面试追问

**超时为何不能承诺清理所有后代进程？**

<details>
<summary>展开参考答案</summary>

当前实现等待并处理直接子进程。脚本自己启动的后代没有统一纳入进程组管理。

</details>

#### M09-C03 面试追问

**输出只回 4 KiB，磁盘也只占 4 KiB 吗？**

<details>
<summary>展开参考答案</summary>

输出先写临时文件。4 KiB 是反馈限制，运行期间临时文件可能更大。

</details>

#### M09-C04 面试追问

**为什么保留脚本执行的用户确认？**

<details>
<summary>展开参考答案</summary>

脚本以当前用户权限运行，所以先把路径交给用户判断。批准后会复查文件身份、大小和时间等信息，发现变化就拒绝。最终复查与 Python 打开脚本之间仍有时间间隔，可信的工作目录仍然重要。

**继续追问**　用户点了确认后，执行的是不是此前看到的文件版本？

</details>

[返回全书目录](#阅读导航) · [下一模块 →](#10-重试规则与指数退避)

---

## 10 重试规则与指数退避

> **本模块目标**　计算重试次数和等待顺序，理解副作用边界。

**小节直达**　[10.1](#101-先判断失败原因再决定要不要重复) · [10.2](#102-包装器为什么接收一个零参数函数) · [10.3](#103-手推默认的三次机会) · [10.4](#104-测试真实请求与重复副作用) · [10.5](#105-还可以怎样改进) · [本模块 12 题](#m10-a01-基础识别)

### 10.1 先判断失败原因，再决定要不要重复

`APIConnectionError`、Python 的连接和超时异常、HTTP 429 及 5xx 属于当前重试范围。HTTP 401、400 和常见编程错误会直接抛出。身份错误通常需要改配置，反复用原请求不会修正它。

### 10.2 包装器为什么接收一个零参数函数

```python
response = call_with_retry(lambda: self.complete(**request))
```

这里传入的是执行请求的办法。重试器每尝试一次就调用一次 `func()`。若先执行 `self.complete(**request)` 再把响应交给重试器，第一次异常已经发生在重试器外面。

[源码 · retry.py · call_with_retry](../MiniAgent/core/retry.py#L16)

### 10.3 手推默认的三次机会

`max_retries=2` 表示初次请求之外最多再试两次。前两次失败时依次等 1 秒、2 秒，第三次仍失败就抛出。`base_delay * 2 ** attempt` 中，`attempt` 从 0 开始。

### 10.4 测试、真实请求与重复副作用

自测替换 `time.sleep`，检查记录的等待参数，所以不用真的等 3 秒。重试器包住模型请求，没有包住文件写入。SDK 的默认重试在 CLI 显式关闭，次数交由项目控制。`max_turns` 和请求重试分别统计。

### 10.5 还可以怎样改进

生产场景会考虑服务器给出的重试时机、指数退避加随机扰动，以及全任务时间预算。对会产生副作用的动作，还要先定义幂等性和重试条件。

### 10.Q 分档自测与面试追问

#### M10-A01 基础识别

**哪些失败会重试？**

<details>
<summary>展开参考答案</summary>

连接与超时异常、HTTP 429 和 5xx。

</details>

#### M10-A02 基础识别

**max_retries=2 最多调用几次？**

<details>
<summary>展开参考答案</summary>

一次初始尝试加两次重试，一共三次。

</details>

#### M10-A03 基础识别

**base_delay 在公式中做什么？**

<details>
<summary>展开参考答案</summary>

是第一个等待时间。下一次等待为它乘以 2。

</details>

#### M10-A04 基础识别

**裸 raise 在 except 中表示什么？**

<details>
<summary>展开参考答案</summary>

将当前捕获的原异常继续抛出。

</details>

#### M10-B01 代码推演

**默认连续三次可重试失败，等待序列是什么？**

<details>
<summary>展开参考答案</summary>

1 秒、2 秒。第三次已没有重试机会，直接抛出。

</details>

#### M10-B02 代码推演

**第一次发生不可重试的 ValueError，会调用几次？**

<details>
<summary>展开参考答案</summary>

一次，无等待。

</details>

#### M10-B03 代码推演

**max_retries=0 或 -1 会怎样？**

<details>
<summary>展开参考答案</summary>

0 表示尝试一次；负数触发 ValueError。

</details>

#### M10-B04 代码推演

**只把 base_delay 设为 0，能验证等待公式吗？**

<details>
<summary>展开参考答案</summary>

不能区分正确与错误的倍数。替换 sleep 并检查收到 1 和 2，才能验证默认序列。

</details>

#### M10-C01 面试追问

**SDK 与外层同时重试，会怎样？**

<details>
<summary>展开参考答案</summary>

外层的一次尝试可能包含多次 SDK 请求，放大时间与尝试数。当前 CLI 把 SDK 重试关掉。

</details>

#### M10-C02 面试追问

**指数退避还有何不足？**

<details>
<summary>展开参考答案</summary>

许多客户端可能同时在相同间隔恢复请求，可以加随机扰动并遵守服务端建议时机。

</details>

#### M10-C03 面试追问

**为什么当前重试边界只包模型请求？**

<details>
<summary>展开参考答案</summary>

工具可能有写文件等副作用。对整轮盲目重试可能重复执行已经完成的动作。

</details>

#### M10-C04 面试追问

**重试耗尽后怎么报错又便于定位？**

<details>
<summary>展开参考答案</summary>

CLI 显示异常类型或 HTTP 状态；日志的 request_failed 用 turn_id、round 和 error_type 做关联。

**继续追问**　要定位每一次失败，下一步还需要记什么？

</details>

[返回全书目录](#阅读导航) · [下一模块 →](#11-jsonl-日志与观测边界)

---

## 11 JSONL 日志与观测边界

> **本模块目标**　按 ID 串起一次工具调用，说明日志的数据范围。

**小节直达**　[11.1](#111-为什么先用结构化事件) · [11.2](#112-从字段到磁盘的一条路径) · [11.3](#113-截断到底截了哪一层) · [11.4](#114-日志失败为什么不打断主流程) · [11.5](#115-日志与会话恢复的区别) · [本模块 12 题](#m11-a01-基础识别)

### 11.1 为什么先用结构化事件

每行都是一个可单独解析的 JSON 对象。一轮任务会有 `user_input`、`tool_call`、`tool_result` 和 `final_answer` 等事件，可以按 `turn_id` 过滤，再用 `tool_call_id` 对照工具开始与结束。

终端和日志共用 Agent 发出的请求轮次、工具名和状态事件。CLI 把 `_print_event` 作为 `on_event` 传给 Agent。Agent 记录事件后调用它，CLI 再把事件翻译成「第几轮、请求了什么工具、执行状态如何」。观察过程不需要额外发模型请求，也不需要输出工具参数和正文。

### 11.2 从字段到磁盘的一条路径

`log_event("tool_result", status="ok", ...)` 先把字段整理成字典，补上事件名与本地时区时间，再用 `json.dumps` 序列化。日志文件按日期命名，以追加模式写入 `MiniAgent/logs`。测试把这个目录换成临时目录。

[源码 · logger.py · log_event](../MiniAgent/core/logger.py#L11)

### 11.3 截断到底截了哪一层

日志帮助理解状态，所以运行时只传元数据，像用户原文、工具参数、文件内容和回答正文都没有传进日志函数。`value[:500]` 再限制顶层字符串字段长度。它是字段限长，不能用来清理嵌套结构或识别敏感信息。

### 11.4 日志失败为什么不打断主流程

目录创建、序列化、写入失败会被捕获，日志缺行时 Agent 仍可继续。结果是一次运行可能没有完整事件记录。测试可以让 `Path.mkdir` 人为抛出 `OSError`，检查 logger 安静返回。

### 11.5 日志与会话恢复的区别

当前日志可以回答「这一轮哪个工具被调用，结果状态是什么」。恢复会话还需要用户消息、助手消息、调用参数、结果和一致的顺序。计划中的请求追踪还要补延迟、请求尝试次数和模型用量等信息。

### 11.Q 分档自测与面试追问

#### M11-A01 基础识别

**JSONL 与一个 JSON 数组有什么区别？**

<details>
<summary>展开参考答案</summary>

每行各自是一条完整记录，可以逐行读或追加。

</details>

#### M11-A02 基础识别

**log_event 怎样形成 record？**

<details>
<summary>展开参考答案</summary>

先处理传入的字段，再补时间戳和事件名，最后编码为单行 JSON。

</details>

#### M11-A03 基础识别

**ensure_ascii=False 有什么作用？**

<details>
<summary>展开参考答案</summary>

中文以原字符写入 UTF-8 文件，更容易直接阅读。

</details>

#### M11-A04 基础识别

**a 与 w 的日志写入模式有何差异？**

<details>
<summary>展开参考答案</summary>

a 在尾部追加；w 打开时会清空既有文件。

</details>

#### M11-B01 代码推演

**500 字符和 501 字符字段怎么处理？**

<details>
<summary>展开参考答案</summary>

前者完整保留，后者取前 500 字符。

</details>

#### M11-B02 代码推演

**哪个字段可以配对一次工具调用？**

<details>
<summary>展开参考答案</summary>

同一轮中用相同 tool_call_id 对照 tool_call 和 tool_result。

</details>

#### M11-B03 代码推演

**磁盘写失败会打断运行吗？**

<details>
<summary>展开参考答案</summary>

当前会捕获常见 I/O 错误，任务继续，日志可能少一条。

</details>

#### M11-B04 代码推演

**log_event('x', ts='自定义') 的时间戳会是什么？**

<details>
<summary>展开参考答案</summary>

最终被 record.update 写入的当前时间覆盖。

</details>

#### M11-C01 面试追问

**为什么日志不能用来恢复会话？**

<details>
<summary>展开参考答案</summary>

它保留事件及状态，缺少消息正文、调用参数与工具结果。

</details>

#### M11-C02 面试追问

**静默日志失败有何代价？**

<details>
<summary>展开参考答案</summary>

任务可继续，但可能没人发现观测中断。要求完整审计时需要明确失败策略。

</details>

#### M11-C03 面试追问

**已有事件日志，未来请求追踪补什么？**

<details>
<summary>展开参考答案</summary>

请求尝试、耗时、用量、完成状态，以及统一关联 ID。

**继续追问**　为什么不能随手把整个请求 JSON 写进日志？

</details>

#### M11-C04 面试追问

**怎样验证日志故障旁路？**

<details>
<summary>展开参考答案</summary>

在测试中让创建目录抛 OSError，调用 log_event 并确认异常没有传播。

</details>

[返回全书目录](#阅读导航) · [下一模块 →](#12-把-selftest-从头读懂)

---

## 12 把 selftest 从头读懂

> **本模块目标**　用准备、执行、断言和清理拆解离线测试。

**小节直达**　[12.1](#121-测试在回答哪一层的问题) · [12.2](#122-unittest-怎样找到测试) · [12.3](#123-如何让模型按剧本回答) · [12.4](#124-如何读同轮多工具与历史断言) · [12.5](#125-文件覆盖与-utf-8-断言分别证明什么) · [12.6](#126-脚本测试何时真的启动子进程) · [12.7](#127-从-sdk-的离线测试读到真实协议) · [12.8](#128-怎样手推-flaky-和重试断言) · [12.9](#129-预期异常为什么算通过) · [12.10](#1210-清理退出码与测试结果) · [12.11](#1211-用一个改动确认自己看懂了) · [本模块 12 题](#m12-a01-基础识别)

### 12.1 测试在回答哪一层的问题

从仓库根目录运行 `python MiniAgent/selftest.py`。一个测试通常有四步：**准备输入、执行动作、比较结果、清理现场**。先找测试名字，再定位 `self.assert...`。断言告诉你作者想证明什么。

| 类 | 在验证什么 | 需要真实模型吗 |
|---|---|---|
| `AgentTests` | 消息顺序、ID 配对、坏响应、轮数、终端进度和 SDK 往返 | 无，使用预设回复或模拟 HTTP |
| `WorkspaceTests` | UTF-8、写入与覆盖、路径、脚本确认、输出和超时 | 无，会运行测试自己写的短脚本 |
| `UtilityTests` | 算术白名单、重试条件、日志失败旁路 | 无 |

### 12.2 unittest 怎样找到测试

文件末尾的 `unittest.main(verbosity=2)` 会在本文件寻找 `unittest.TestCase` 子类，执行名字以 `test_` 开头的方法。每个方法执行前先跑该类的 `setUp`。`self.enterContext(...)` 会登记清理动作，测试成功或失败后都能恢复补丁、清理临时文件。

### 12.3 如何让模型按剧本回答

```python
model = ScriptedModel(
    response(calls=[call("a", "calculate", '{"expression":"2+3"}')]),
    response("结果是 5。"),
)
agent = Agent(assistant.TOOLS, "助手", complete=model.complete, model="fake")
```

这是一个缩小的例子。`ScriptedModel` 用 `iter` 保存准备好的响应，用 `next` 每次取一条。`complete(**request)` 还把这次请求深拷贝到 `self.requests`。你可以在第二轮检查历史，确认第一次的工具结果已经回传。若只保留原列表引用，后来追加的消息会改变你看到的旧请求。

[源码 · selftest.py · class ScriptedModel](../MiniAgent/selftest.py#L38)

### 12.4 如何读同轮多工具与历史断言

找 `test_two_tools_and_followup_use_message_history`，先把下表右列遮住，自行推一次。

| 取哪个记录 | 你应该能看到什么 |
|---|---|
| `model.requests[0]["messages"]` | `system, user`，此时没有模型响应 |
| `model.requests[1]["messages"]` | `system, user, assistant, tool, tool`，两个工具结果分别关联 a、b |
| `model.requests[2]["messages"][-2]` | 上一次最终回答；这一轮新的 user 在它后面 |

测试能证明程序送出了正确的上下文。第三条回复由测试预设，模型实际会不会理解「刚才」需要在线试跑或独立评测。

再看 `test_interrupted_tool_batch_keeps_protocol_and_does_not_replay`。替身工具先记录自己被调用，再在第二项抛出 `KeyboardInterrupt`。测试断言只有两次调用，历史仍有三个配对结果。随后再次调用 Agent，检查下一次请求确实携带这组完整结果。

最后看 `test_cli_progress_reports_requests_and_tool_results_in_order`。剧本在同一轮安排两次计算，先做 `1/0`，再做 `13*17`。第一个失败，第二个仍能成功。`StringIO()` 相当于内存里的终端，`redirect_stdout(output)` 暂时把 `print` 写到那里。`splitlines()` 将捕获的文字拆成列表，断言逐行比较「第一轮请求 → 第一个工具失败 → 第二个工具成功 → 第二轮请求」。这项测试检查你在 Trae 看到的进度。上面的历史断言检查模型下一轮收到的数据。

[源码 · selftest.py · test_two_tools_and_followup_use_message_history](../MiniAgent/selftest.py#L59)

[源码 · selftest.py · test_cli_progress_reports_requests_and_tool_results_in_order](../MiniAgent/selftest.py#L77)

### 12.5 文件覆盖与 UTF-8 断言分别证明什么

`test_write_requires_explicit_overwrite_and_user_confirmation` 先写第一版，再分别验证默认写入、没有确认回调、用户拒绝时都能保住旧内容。最后让确认替身返回 `True`，覆盖并读回第二版。另有测试让批准回调同时修改原文件，验证程序会保留较新的内容。

`test_failed_creation_cleans_up_partial_file` 让替身先写一个字节再抛出 I/O 错误，断言失败后没有残留文件。`test_file_limits_count_bytes_and_keep_valid_unicode` 用 `limit - 1` 个 ASCII 字节接一个汉字，把边界卡在字符中间，断言返回的是完整字符。

[源码 · selftest.py · test_file_limits_count_bytes_and_keep_valid_unicode](../MiniAgent/selftest.py#L349)

### 12.6 脚本测试何时真的启动子进程

拒绝用例和确认期间修改脚本的用例都把 `_run_python` 替换成 Mock，再断言 `assert_not_called()`。允许用例写一个临时 `demo.py`，真正启动本地解释器并检查输出。超时用例写入 `sleep(5)`，只在测试里把限时改成 0.3 秒。测试脚本均由测试自身生成。

[源码 · selftest.py · test_python_is_opt_in_and_denial_does_not_start_a_process](../MiniAgent/selftest.py#L381)

### 12.7 从 SDK 的离线测试读到真实协议

`test_sdk_roundtrip_without_network` 用 `httpx.MockTransport(handler)` 为 SDK 提供本地 HTTP 替身。第一次回两个调用，要求先写文件再读文件。第二次检查送给模型的请求确有读回内容。这同时验证 SDK 数据转换、工具顺序、实际写入和回传格式。预设回复只验证协议与运行时，线上模型选工具的表现要另测。

[源码 · selftest.py · test_sdk_roundtrip_without_network](../MiniAgent/selftest.py#L248)

### 12.8 怎样手推 flaky 和重试断言

迭代器准备 `TimeoutError()`、`ConnectionError()` 和 `"ok"`。前三次调用分别取一个。用 `patch.object(retry.time, "sleep")` 记下等待参数，并断言为 `[1, 2]`。不用真的等，就能验证次数和公式。

[源码 · selftest.py · test_transient_error_retries_with_backoff](../MiniAgent/selftest.py#L435)

### 12.9 预期异常为什么算通过

```python
with self.assertRaises(ToolError):
    write("sub/note.txt", "意外覆盖")
```

这里把「必须拒绝」写成测试。若没有抛出 `ToolError`，断言失败。要验证确实没有误写，还要再读文件，检查旧内容未变。`assertRaisesRegex` 可进一步验证失败原因，避免别的 `ToolError` 让断言意外通过。

### 12.10 清理、退出码与测试结果

正常用例打印 `ok`，断言不符会打印失败信息，未预期异常显示为 `ERROR`。系统禁止创建符号链接时，该用例会标为 `skipped`。终端中的 `Ran` 包含跳过的用例；请同时看最终状态与跳过数量。测试通过时进程退出码是 0，有失败时是非 0。

当前版本在本机的结果是 `Ran 25 tests`、`OK (skipped=1)`，也就是 24 项通过，符号链接用例因系统权限跳过。在允许创建符号链接的环境里，这项会实际执行。

### 12.11 用一个改动确认自己看懂了

先预测：如果暂时删掉 `run` 里保存最终 assistant 的那一步，哪条断言会先出问题？运行时应在第三次请求的历史检查失败。读完后可以在独立练习副本试一次，再恢复。面试时说出测试证明的行为，最后说出它覆盖不到的线上表现。

### 12.Q 分档自测与面试追问

#### M12-A01 基础识别

**测试方法要按哪四步读？**

<details>
<summary>展开参考答案</summary>

准备、执行、断言、清理。

</details>

#### M12-A02 基础识别

**unittest 如何找到这些测试？**

<details>
<summary>展开参考答案</summary>

入口调用 unittest.main，执行 TestCase 子类中以 test_ 开头的方法。

</details>

#### M12-A03 基础识别

**ScriptedModel 做了哪两件事？**

<details>
<summary>展开参考答案</summary>

依次给出预设响应，并保存每次请求的深拷贝供断言使用。

</details>

#### M12-A04 基础识别

**终端里 skipped 算通过吗？**

<details>
<summary>展开参考答案</summary>

它表示该条件下未验证对应行为。整体可能返回成功，但报告时要单列跳过。

</details>

#### M12-B01 代码推演

**输入只有短文本，截断断言会通过吗？**

<details>
<summary>展开参考答案</summary>

应当失败。用例要主动构造超过字节上限的内容。

</details>

#### M12-B02 代码推演

**为什么 UTF-8 用例在 limit - 1 个 ASCII 字节后追加汉字？**

<details>
<summary>展开参考答案</summary>

让字节上限落在多字节字符中间，以验证不会返回半个字符。

</details>

#### M12-B03 代码推演

**为什么两次请求的 messages 需要快照？**

<details>
<summary>展开参考答案</summary>

同一个列表会持续追加。深拷贝后，旧请求保留当时发送的内容。

</details>

#### M12-B04 代码推演

**with self.assertRaises 中的调用抛出预期异常，会怎样？**

<details>
<summary>展开参考答案</summary>

断言通过；没有抛出或抛出其他类型时测试不会通过。

</details>

#### M12-C01 面试追问

**拒绝运行用例和超时用例都真的启动进程吗？**

<details>
<summary>展开参考答案</summary>

拒绝用 Mock 断言启动函数未调用；超时启动本地脚本并缩短测试时限。

</details>

#### M12-C02 面试追问

**SDK 替身能验证什么？**

<details>
<summary>展开参考答案</summary>

让真实 SDK 序列化请求并解析预设响应，同时校验写入、回读与工具结果，HTTP 通过本地替身处理。

</details>

#### M12-C03 面试追问

**优先补什么失败用例来守住主循环？**

<details>
<summary>展开参考答案</summary>

从副作用风险出发，先测截断响应完全不执行工具，再测批次被中断时保留已完成结果且不执行剩余工具。还要检查空响应、缺失或重复 ID、最终回答进入下一轮等协议用例。

**继续追问**　只断言最终一句话为什么不足？

</details>

#### M12-C04 面试追问

**全绿的离线自测能代表模型成功率吗？**

<details>
<summary>展开参考答案</summary>

离线回复是预设的，结果证明程序行为。模型成功率需要定义任务、标准和真实运行样本。

</details>

[返回全书目录](#阅读导航) · [下一模块 →](#13-设计判断当前缺口与十项扩展)

---

## 13 设计判断、当前缺口与十项扩展

> **本模块目标**　按当前完成项与后续验收点介绍项目。

**小节直达**　[13.1](#131-从历史演进提炼判断) · [13.2](#132-已经修好的基线与剩余边界) · [13.3](#133-十项扩展的依赖和最小验收) · [13.4](#134-记忆持久化压缩与-rag) · [13.5](#135-怎样判断架构撑住扩展)

### 13.1 从历史演进提炼判断

最早版本适合观察函数调用原理。现在版把配置和 SDK 放在 CLI，把工具执行入口集中在 `Agent.execute_tool`，让应用工具负责自己的业务校验。旧版自由 shell、`eval` 和行数截断测试已由新版实现替代。旧版源码可从 Git 历史回看。

### 13.2 已经修好的基线与剩余边界

这版在工具执行前拒绝截断的模型响应，在工具批次被中断时保持 ID 配对。覆盖文件和执行脚本都需要终端用户确认，并在批准后复查文件状态。会话仍驻留内存，历史持续增长，轮数上限按逻辑模型请求计算。权限策略、会话恢复和上下文管理留给后续扩展。

### 13.3 十项扩展的依赖和最小验收

| 扩展 | 状态 | 最小验收 |
|---|---|---|
| 统一工具执行 | 已有 | 本地函数集中校验，失败回传能配对，同批其他工具仍能继续 |
| 权限 | 计划 | 同一入口可按能力与目标允许、拒绝或请求确认，拒绝时没有副作用 |
| 局部编辑 | 计划 | 替换点匹配唯一才写入，零处或多处匹配保留原内容 |
| 计划模式 | 计划 | 未确认时，执行层禁止写入；批准后进入执行阶段 |
| 任务清单 | 计划 | 可追踪待做、进行中与完成，并限制非法状态转换 |
| 会话持久化 | 计划 | 重启可读回历史，保留完整工具调用与结果批次 |
| 请求追踪 | 计划 | 同一轮可定位模型调用、重试、工具耗时与用量 |
| 上下文压缩 | 计划 | 保留 system、近期上下文和完整调用批次，达到水位线才触发 |
| 长期记忆 | 计划 | 能显式写入、查找和删除跨会话记忆，避免随意保存敏感内容 |
| MCP | 计划 | 接入一个本地服务器，走完发现工具、授权调用、返回结果和关闭连接 |

按你定的节奏，先完成 FitBot，再回到 MiniAgent。回来可先做权限和局部编辑，再做计划与任务；先确定会话数据格式，再做持久化、压缩和记忆；最后让一个 MCP 工具经过同一套授权与执行路径。

### 13.4 记忆、持久化、压缩与 RAG

持久化负责重启后恢复这段会话。压缩负责控制这次送入模型的上下文规模。长期记忆负责在以后别的会话使用经选择的信息。FitBot 的 RAG 学习重点是检索外部知识供当前回答使用。四种能力有不同的保存时机、使用时机和评测方法。

### 13.5 怎样判断架构撑住扩展

检查新的能力接入后，原来「请求模型 → 校验并执行工具 → 回填结果」的流程能否独立测试。权限应在执行副作用前拦截，压缩应保留协议组块，MCP 远端工具也要进入统一的执行和授权路径。如果一个新需求需要调整边界，就改动对应职责，并用旧用例和新用例验证。

[返回全书目录](#阅读导航) · [下一模块 →](#14-面试表达与场景追问)

---

## 14 面试表达与场景追问

> **本模块目标**　用具体调用流程和测试证据回答面试追问。

**小节直达**　[14.1](#141-三十秒介绍) · [14.2](#142-两分钟按一个问题展开) · [14.3](#143-面试官常用的六种追问方式) · [14.4](#144-三个现场演练) · [14.5](#145-不知道时怎样答)

### 14.1 三十秒介绍

> 我用 Python 手写了一个工具调用 Agent。两种 CLI 应用复用同一个运行时，一种做算术和演示查询，另一种在工作区读写文本。我实现了工具说明生成、参数校验、调用和结果配对、最终回答入历史。测试用模拟模型验证了第一项工具失败时后续工具能继续，还用 SDK 的本地 HTTP 替身走通了同轮先写后读。

### 14.2 两分钟按一个问题展开

可以选「工具失败后，怎么继续这一轮」。先说旧问题，再描述一个实际调用批次。解释为什么要保留相同 `tool_call_id`，以及为什么把校验和异常处理移到 `execute_tool`。最后给一个测试名和它的断言，补一句「线上模型能否选择合适的工具需要另测」。

### 14.3 面试官常用的六种追问方式

| 追问 | 从哪里切入 |
|---|---|
| 为什么不直接用 LangGraph？ | 这里想练请求循环、消息协议和工具执行边界；FitBot 用图编排业务流程 |
| 模型传了坏 JSON 怎么办？ | 单工具失败变成同 ID 的 tool 结果，后续调用继续 |
| 先写后读依赖顺序，为什么不并行？ | 当前按响应顺序执行；引入并发前需定义依赖和副作用 |
| 工作区能限制 Python 访问吗？ | 文件工具各自限制路径；Python 子进程拥有当前用户权限 |
| 重试会重复写文件吗？ | 当前重试只包模型请求；下一轮模型若主动再请求同一工具，仍可能产生新副作用 |
| MCP 放哪里？ | 先适配工具发现和调用，再让这些工具经过共同校验、授权和结果回传 |

### 14.4 三个现场演练

1. 画出第一轮返回两个调用、第二轮给最终回答后的历史。
2. 解释从模型传入 `overwrite=True` 到用户批准后复查、替换文件的全过程。举例说明用户批准后文件发生变化时会怎样。
3. 用一个具体输入说明 API 请求轮数、底层请求尝试、工具调用数分别怎么计数。

### 14.5 不知道时怎样答

如果问到线上任务成功率，可以说明当前跑了哪些离线回归、样本是否来自实际模型、下一步会用哪些任务和预期结果来评测。把证据和推测放在不同的句子里。

[返回全书目录](#阅读导航) · [下一模块 →](#15-每日复习路线与维护卡)

---

## 15 每日复习路线与维护卡

> **本模块目标**　按十四次路线小步复习并维护自己的疑问记录。

**小节直达**　[15.1](#151-十四次学习任务) · [15.2](#152-每次只记录三个短句) · [15.3](#153-十五分钟面试热身) · [15.4](#154-代码更新时同步哪些地方) · [15.5](#155-需要进一步查证时)

### 15.1 十四次学习任务

| 次数 | 目标 | 阅读 | 做题 |
|---|---|---|---|
| 1 | 画出架构地图 | [01.2 先看职责，再看文件](#012-先看职责再看文件) | [M01-A01](#m01-a01-基础识别) · [M01-B02](#m01-b02-代码推演) |
| 2 | 读懂函数与数据 | [02.2 函数对象与函数调用](#022-函数对象与函数调用) | [M02-A02](#m02-a02-基础识别) · [M02-B01](#m02-b01-代码推演) |
| 3 | 走一遍启动过程 | [03.2 import 会执行哪些事](#032-import-会执行哪些事) | [M03-A02](#m03-a02-基础识别) · [M03-B02](#m03-b02-代码推演) |
| 4 | 手工生成工具说明 | [04.3 从一个有默认参数的例子推导](#043-从一个有默认参数的例子推导) | [M04-A02](#m04-a02-基础识别) · [M04-B01](#m04-b01-代码推演) |
| 5 | 推导实例状态 | [05.3 两个实例为什么不串历史](#053-两个实例为什么不串历史) | [M05-A01](#m05-a01-基础识别) · [M05-B01](#m05-b01-代码推演) |
| 6 | 走通正常工具循环 | [06.4 工具分支逐步手推](#064-工具分支逐步手推) | [M06-A03](#m06-a03-基础识别) · [M06-B01](#m06-b01-代码推演) |
| 7 | 检查最终回答、失败与终止 | [06.6 最终回答怎样进入历史](#066-最终回答怎样进入历史) | [M06-B03](#m06-b03-代码推演) · [M06-C02](#m06-c02-面试追问) |
| 8 | 辨清演示工具能力 | [07.2 天气工具就是字典查询](#072-天气工具就是字典查询) | [M07-A01](#m07-a01-基础识别) · [M07-B03](#m07-b03-代码推演) |
| 9 | 理解文件路径与读写 | [08.2 路径检查究竟做了哪两件事](#082-路径检查究竟做了哪两件事) | [M08-B01](#m08-b01-代码推演) · [M08-B03](#m08-b03-代码推演) |
| 10 | 解释脚本启动与权限 | [09.3 subprocess 的参数各管一件事](#093-subprocess-的参数各管一件事) | [M09-A02](#m09-a02-基础识别) · [M09-C01](#m09-c01-面试追问) |
| 11 | 计算重试和日志 | [10.3 手推默认的三次机会](#103-手推默认的三次机会) · [再看日志的落盘路径](#112-从字段到磁盘的一条路径) | [M10-B01](#m10-b01-代码推演) · [M10-C01](#m10-c01-面试追问) · [M11-B02](#m11-b02-代码推演) |
| 12 | 拆解预设模型与历史断言 | [12.2 unittest 怎样找到测试](#122-unittest-怎样找到测试) · [再看历史断言](#124-如何读同轮多工具与历史断言) | [M12-A03](#m12-a03-基础识别) · [M12-B03](#m12-b03-代码推演) |
| 13 | 手推重试与预期异常 | [12.8 怎样手推 flaky 和重试断言](#128-怎样手推-flaky-和重试断言) | [M12-B04](#m12-b04-代码推演) · [M10-B01](#m10-b01-代码推演) |
| 14 | 口述项目并接追问 | [14.1 三十秒介绍](#141-三十秒介绍) · [核对已完成项与执行边界](#132-已经修好的基线与剩余边界) | 口述三十秒介绍 |

### 15.2 每次只记录三个短句

记录「我能解释的一个流程」「我能预测的一个边界」「我下次要验证的一个疑问」。例如，第一轮两次工具调用会保留同一条 assistant；首轮请求失败会移除用户消息；下一次查清后续轮失败为什么保留历史。

### 15.3 十五分钟面试热身

三分钟画架构，五分钟手推调用和错误分支，五分钟口述一个验证用例，最后两分钟讲清当前执行边界与计划。

### 15.4 代码更新时同步哪些地方

先看 README 的运行命令和能力表，再看相应章节、题库和 HTML 目录。改了测试时也要改第 12 章的示例和断言说明。遇到扩展新增状态时，把「计划」和「通过了哪些验收」写清楚。

### 15.5 需要进一步查证时

从源码和离线用例找本项目行为，从服务官方文档查供应商协议，从真实请求或独立评测验证模型表现。 [DeepSeek 工具调用文档](https://api-docs.deepseek.com/guides/tool_calls/)

[返回全书目录](#阅读导航)
