import os                          # 用来读环境变量（API Key 存在系统环境里）
import json                        # 模型返回的工具参数是 JSON 字符串，要解析成 Python 字典
from openai import OpenAI          # OpenAI 官方库。DeepSeek 兼容它的格式，所以直接复用
from dotenv import load_dotenv     # 用来读取 .env 文件里的配置
import inspect                     # 用来读取函数的参数结构（装饰器里要用）
from core.retry import call_with_retry
from core.logger import log_event

load_dotenv()

# 创建客户端：相当于"拨号连接"到 DeepSeek 的服务器
# base_url 是关键——OpenAI 的库默认连 api.openai.com，
# 这里我们改成 DeepSeek 的地址，就变成调 DeepSeek 了
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)
#1"https://api.deepseek.com"
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

    # ★ 关键变化：不再往全局列表里塞，而是挂在函数自己身上
    #   函数是对象，可以像这样给它加属性
    func._schema = {
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
    }


    return func

class Agent:
    """一个 Agent 实例：有自己的行为准则、自己的对话记忆"""

    def __init__(self, tools, system_prompt, max_turns=5):
        """
    __init__ 在【创建对象】时自动执行一次，负责装上初始状态。

    tools          —— 这个 Agent 能用的工具列表
    system_prompt  —— 这个 Agent 的角色（必填：框架不知道该给你什么角色）
    max_turns      —— 最多循环几轮
    """



        self.system_prompt = system_prompt
        self.max_turns = max_turns

        # ★ 这个 Agent 自己的工具（两样东西，各有用处）
        #   self.tools   : 名字 -> 函数，执行工具时用
        #   self.schemas : 说明书列表，发给模型看
        self.tools = {}
        self.schemas = []
        for f in tools:
            self.tools[f.__name__] = f
            self.schemas.append(f._schema)

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
        log_event("user_input", content=user_input)


        # self.max_turns = 最多循环几轮
        # 为什么要有上限？
        #   1. 防止死循环（模型可能一直调工具不收敛）
        #   2. 控制成本（每一轮都要花钱 + 花时间）
        # 真实项目里一般设 5-10 轮，并加上超时和 token 预算
        for turn in range(self.max_turns):
            print(f"\n--- 第 {turn + 1} 轮 ---")

            response = call_with_retry(
                lambda: client.chat.completions.create(
                    model="deepseek-chat",
                    messages=self.messages,
                    tools=self.schemas,
                )
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
                    log_event("tool_call", tool=name, args=args)

                    # 【关键行】**args 里的 ** 是"字典解包"
                    #   args = {"city": "杭州"}
                    #   get_weather(**args)  等价于  get_weather(city="杭州")
                    # 去掉 ** 就变成传一整个字典当第一个参数，会报错。
                    result = self.tools[name](**args)      # 按名字找到函数并执行
                    print(f"  工具返回: {result}")
                    log_event("tool_result", tool=name, result=str(result))

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
            log_event("final_answer", content=str(msg.content))
            return msg.content

        # 循环跑满还没返回，说明模型卡住了
        log_event("max_turns_exceeded", max_turns=self.max_turns)
        return f"超过最大轮数了（{self.max_turns} 轮）"