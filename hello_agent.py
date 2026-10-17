"""
================================================================================
 My First Agent —— 逐行讲解版
================================================================================

【这个文件在干什么】

让大模型（DeepSeek）拥有"动手能力"：
  用户提问 → 模型判断"我需要查点东西" → 调用 Python 函数 → 拿到真实数据
  → 模型基于真实数据回答用户

核心就是一个循环，业界叫 ReAct（Reasoning + Acting）：
  思考 → 调工具 → 看结果 → 再思考 → …… → 回答

【读代码的顺序建议】

按 ① ② ③ ④ 的顺序看，别从上往下硬读。
 ① 工具函数        —— 真正干活的代码
 ② @tool 装饰器    —— 自动把函数翻译成"工具说明书"（关键：模型看不懂 Python，只看得懂文字）
 ③ 主循环          —— Agent 的心脏
 ④ __main__        —— 程序入口
"""

# ------------------------------------------------------------------------------
# 导入：把别人写好的代码拿过来用
# ------------------------------------------------------------------------------
import os                          # 用来读环境变量（API Key 存在系统环境里）
import json                        # 模型返回的工具参数是 JSON 字符串，要解析成 Python 字典
from openai import OpenAI          # OpenAI 官方库。DeepSeek 兼容它的格式，所以直接复用
from dotenv import load_dotenv     # 用来读取 .env 文件里的配置
import datetime
import inspect                     # 用来读取函数的参数结构（装饰器里要用）
# load_dotenv() 会去当前目录找 .env 文件，把里面的 DEEPSEEK_API_KEY=xxx
# 加载成环境变量。之后 os.getenv() 才读得到。
#
# 为什么要这么绕？因为 API Key 是机密，不能写死在代码里。
# 写死的话，你一推 GitHub，全世界的爬虫都能看到你的 Key 并拿去刷钱。
load_dotenv()

# 创建客户端：相当于"拨号连接"到 DeepSeek 的服务器
# base_url 是关键——OpenAI 的库默认连 api.openai.com，
# 这里我们改成 DeepSeek 的地址，就变成调 DeepSeek 了
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)

# ==============================================================================
# 工具注册机制：用 @tool 装饰器自动生成 JSON 描述并登记
# ==============================================================================

TOOL_SCHEMAS = []      # 给模型看的"工具说明书"列表
TOOL_MAP = {}          # 执行时用的"名字 → 函数"映射

TYPE_MAP = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
}


def tool(func):
    """把一个函数注册成 Agent 可用的工具"""
    name = func.__name__
    description = func.__doc__ or ""

    sig = inspect.signature(func)
    properties = {}
    required = []

    for param_name, param in sig.parameters.items():
        json_type = TYPE_MAP.get(param.annotation, "string")
        properties[param_name] = {"type": json_type}
        if param.default is inspect.Parameter.empty:
            required.append(param_name)

    TOOL_SCHEMAS.append({
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    })

    TOOL_MAP[name] = func          # 顺手注册"名字 → 函数"映射，执行时靠它找到函数

    return func




# ==============================================================================
# ① 工具函数：真正干活的 Python 代码
# ==============================================================================
#
# 这些就是普通函数，没有任何魔法。模型不会直接执行它们——
# 是【我们的代码】执行它们，然后把结果告诉模型。这点必须先想清楚。
@tool
def get_weather(city: str):
    """查询城市天气"""
    # 这是个字典 dict：用 "键" 找 "值"，类似 Java 的 Map
    data = {
        "北京": "晴，26度，微风",
        "上海": "多云，30度，湿度大",
        "杭州": "小雨，24度，记得带伞",
    }
    # .get(键, 默认值)：找不到这个城市时返回默认值，不会报错
    # f"..." 是 f-string，把变量 {city} 直接嵌进字符串
    return data.get(city, f"{city}：暂无数据")

@tool
def calculate(expression: str):
    """计算数学表达式"""
    # try/except 是"出错也不崩"的写法：
    #   try    里出错 → 跳到 except，而不是让整个程序挂掉
    # 为什么必须包一层？因为用户可能输入 "hello"，eval 会炸，
    # 不捕获的话 Agent 直接崩溃退出
    try:
        # eval("1+1") 会把字符串当代码执行，返回结果
        # ⚠️ 真实项目绝对不能用 eval——用户可以输入删库命令。
        #    这里只是学习演示。生产环境要用专门的数学解析库。
        return str(eval(expression))   # 必须转成字符串！下面会解释为什么
    except Exception as e:
        return f"算错了：{e}"

@tool
def get_time():
    """返回当前时间"""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

@tool
def get_stock_price(code: str):
    """查询股票价格"""
    return f"{code}：100元"


# ==============================================================================
# ③ Agent 类：把"状态"和"行为"打包在一起
# ==============================================================================
#
# 【为什么要有类？】
#
# 之前 MESSAGES / TOOL_SCHEMAS / TOOL_MAP 都放在【模块级】，是全局变量。
# 全局 = 整个程序只有一份 = 你的程序里只能有一个 Agent。
#
# 如果我想同时跑两个 Agent —— 比如一个"天气助手"、一个"股票助手" ——
# 它们会共用同一份对话记忆，互相污染。
#
# 类的解法：把状态放进【实例】里。每个 Agent 对象有自己的 messages。
#   agent1 = Agent()   ← 一份记忆
#   agent2 = Agent()   ← 另一份记忆，互不干扰
#
# 【self 是什么？】
#   self 就是"当前正在被调用的那个对象"。
#   agent1.run() 时 self = agent1；agent2.run() 时 self = agent2。
#   所以 self.messages 拿到的，永远是"这个对象自己的"记忆。


class Agent:
    """一个 Agent 实例：有自己的行为准则、自己的对话记忆"""

    def __init__(self, system_prompt=None, max_turns=5):
        """
        __init__ 在【创建对象】时自动执行一次，负责装上初始状态。
        """
        if system_prompt is None:
            system_prompt = (
                "你是一个有用的助手。需要查天气或算数时或者查股票价格时，"
                "必须调用工具，不许自己编答案。"
            )

        self.system_prompt = system_prompt
        self.max_turns = max_turns

        # ★ 关键：每个 Agent 自己的记忆，从 system 那条开始
        #   注意是 self.messages，不是以前那个全局的 MESSAGES
        self.messages = [
            {"role": "system", "content": self.system_prompt},
        ]

    def run(self, user_input):
        """
        处理一次用户提问，返回最终答案。

        self.messages 是整个对话历史。每一轮都把新消息 append 进去，
        模型每次看到的都是【完整历史】，所以它才有"记忆"。
        """
        # 四个角色：
        #   system    —— 设定模型的行为准则（最高优先级）
        #   user      —— 用户说的话
        #   assistant —— 模型说的话
        #   tool      —— 工具的执行结果（下面会遇到）
        #
        # ⚠️ 往【自己这个对象】的记忆里追加，不是往全局变量里
        self.messages.append({"role": "user", "content": user_input})

        # self.max_turns = 最多循环几轮
        # 为什么要有上限？
        #   1. 防止死循环（模型可能一直调工具不收敛）
        #   2. 控制成本（每一轮都要花钱 + 花时间）
        # 真实项目里一般设 5-10 轮，并加上超时和 token 预算
        for turn in range(self.max_turns):
            print(f"\n--- 第 {turn + 1} 轮 ---")

            # 发请求给模型。tools=TOOL_SCHEMAS 把工具清单一起发过去，
            # 模型才知道自己能用什么
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=self.messages,
                tools=TOOL_SCHEMAS,
            )
            # response 是个大对象，真正的回复藏在 choices[0].message 里
            msg = response.choices[0].message

            # ---- 分支 A：模型说"我要调工具" ---------------------------------
            # msg.tool_calls 是模型返回的调用请求列表。
            # ⚠️ 是列表！模型可能一次要调多个工具（比如同时查北京和上海）。
            #    所以必须用 for 遍历，不能只取 [0]，否则会丢数据。
            if msg.tool_calls:
                # 先把"模型想调工具"这个意图也存进历史。
                # 不存的话，后面塞工具结果时模型会对不上号、直接报错。
                self.messages.append(msg)

                for tool_call in msg.tool_calls:
                    name = tool_call.function.name       # 字符串，如 "get_weather"

                    # 模型返回的参数是 JSON 字符串：'{"city": "杭州"}'
                    # json.loads 把它转成 Python 字典：{"city": "杭州"}
                    args = json.loads(tool_call.function.arguments)
                    print(f"  模型要调工具: {name}({args})")

                    # 【关键行】**args 里的 ** 是"字典解包"
                    #   args = {"city": "杭州"}
                    #   get_weather(**args)  等价于  get_weather(city="杭州")
                    # 去掉 ** 就变成传一整个字典当第一个参数，会报错。
                    result = TOOL_MAP[name](**args)      # 按名字找到函数并执行
                    print(f"  工具返回: {result}")

                    # 把工具结果塞回对话历史，让模型在下一轮能看到
                    self.messages.append({
                        "role": "tool",                  # 角色是 tool，不是 user
                        "tool_call_id": tool_call.id,    # 告诉模型：这是你刚才那次调用的结果
                        "content": result,               # 必须是字符串！所以上面 calculate 用了 str()
                    })
                    # tool_call_id 为什么必须带？
                    #   一次请求可能有多个调用，模型要靠这个 ID 把结果和调用对上号。
                    #   少了它，模型会困惑"这结果是谁的"，然后开始瞎编。

                # continue = 立刻回到循环开头，再问一次模型
                # 为什么必须 continue？
                #   没有这行的话，代码会继续往下走到 return msg.content，
                #   而此时 msg.content 是空的（模型在等工具结果），直接返回 None。
                continue

            # ---- 分支 B：模型给出了最终答案 ---------------------------------
            # 走到这里说明 msg.tool_calls 是空的，模型认为信息够了，可以直接回答
            print(f"\n最终回答: {msg.content}")
            return msg.content

        # 循环跑满还没返回，说明模型卡住了
        return f"超过最大轮数了（{self.max_turns} 轮）"


# ==============================================================================
# ④ 程序入口
# ==============================================================================
#
# if __name__ == "__main__": 的含义：
#   - 直接运行这个文件（python hello_agent.py）→ __name__ 等于 "__main__"，执行下面的代码
#   - 被别的文件 import 时              → __name__ 等于文件名，【不】执行下面的代码
#
# 为什么要加这层判断？
#   以后你想在别的项目里 import Agent 复用它，
#   没有这行的话，一 import 就会立刻启动命令行对话，很烦。
#   这是 Python 的标准写法，记住就行。
if __name__ == "__main__":
    # ★ 新建一个 Agent 对象。这一行之后，agent 就带着自己的记忆了
    agent = Agent()

    print("你的第一个 Agent 启动了，输入 q 退出\n")

    # while True = 无限循环，靠 break 退出
    while True:
        q = input("你: ")      # input() 会暂停程序，等你从键盘输入
        if q == "q":
            break              # 跳出循环，程序结束
        agent.run(q)           # 注意：调用的是【这个对象】的方法
