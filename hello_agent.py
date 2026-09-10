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
 ② tools 描述      —— 告诉模型有哪些工具（关键：模型看不懂 Python，只看得懂文字）
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
# ① 工具函数：真正干活的 Python 代码
# ==============================================================================
#
# 这些就是普通函数，没有任何魔法。模型不会直接执行它们——
# 是【我们的代码】执行它们，然后把结果告诉模型。这点必须先想清楚。

def get_weather(city):
    """查询城市天气（这里用假数据，真实项目里会去调天气 API）"""
    # 这是个字典 dict：用 "键" 找 "值"，类似 Java 的 Map
    data = {
        "北京": "晴，26度，微风",
        "上海": "多云，30度，湿度大",
        "杭州": "小雨，24度，记得带伞",
    }
    # .get(键, 默认值)：找不到这个城市时返回默认值，不会报错
    # f"..." 是 f-string，把变量 {city} 直接嵌进字符串里
    return data.get(city, f"{city}：暂无数据")


def calculate(expression):
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

def get_time():
    """返回当前时间"""
    return datetime.datetime.now().strftime("%Y-%m-%d %Hh:%M:%S")

# ==============================================================================
# ② tools：告诉模型"你有哪些工具可以使用"
# ==============================================================================
#
# 【这是整个 Agent 最反直觉的地方，务必理解】
#
# 模型根本看不到、也看不懂你的 Python 函数。它只收到一段文字。
# 所以你必须【用自然语言 + JSON 格式】描述一遍你的工具有哪些、怎么用。
#
# 模型做的事情本质上是：
#   "我读了这些工具描述，我觉得该用 get_weather，参数是 city=杭州"
#   → 它返回这个【意图】，不是真的调用
#   → 真正执行的是我们的 Python 代码
#
# 这个描述写得越清楚，模型选工具越准。description 别偷懒。

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",                          # 必须和 Python 函数名对应
            "description": "查询指定城市的天气",              # 这句话模型会读到
            "parameters": {                                  # 参数的 JSON Schema 描述
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称，例如 北京",  # 给例子能显著提升准确率
                    }
                },
                "required": ["city"],                        # 必填参数
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "计算一个数学表达式，例如 123 * 456",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "数学表达式",
                    }
                },
                "required": ["expression"],
            },
        },
    },
{
    "type": "function",
    "function": {
        "name": "get_time",
        "description": "返回当前的日期和时间。当用户问'现在几点''今天几号'时使用",
        "parameters": {
            "type": "object",
            "properties": {},        # 空字典 = 没有参数
            "required": [],          # 空列表 = 没有必填
        },
    },
},
]

# 工具名(字符串) → 函数对象 的映射表
#
# 为什么需要它？
#   模型返回的是字符串 "get_weather"，但我们要执行的是【函数对象】get_weather。
#   字符串和函数是两回事，所以需要一张表把名字翻译成真正的函数。
#
# 注意这里写的是 get_weather 而不是 get_weather()：
#   不带括号 = 函数本身（存起来待用）
#   带括号   = 立刻调用它
tool_map = {
    "get_weather": get_weather,
    "calculate": calculate,
    "get_time": get_time,
}


# ==============================================================================
# ③ 主循环：Agent 的心脏
# ==============================================================================

def run_agent(user_input):
    """
    处理一次用户提问，返回最终答案。

    messages 是整个对话历史。每一轮都把新消息 append 进去，
    模型每次看到的都是【完整历史】，所以它才有"记忆"。
    """
    # 三个角色：
    #   system    —— 设定模型的行为准则（最高优先级）
    #   user      —— 用户说的话
    #   assistant —— 模型说的话
    #   tool      —— 工具的执行结果（下面会遇到）
    messages = [
        {
            "role": "system",
            # 这句话至关重要！它逼着模型去调工具而不是瞎编。
            # 去掉这句，模型很可能直接编一个"杭州今天晴，25度"出来。
            "content": "你是一个有用的助手。需要查天气或算数时，必须调用工具，不许自己编答案。",
        },
        {"role": "user", "content": user_input},
    ]

    # range(5) = 最多循环 5 轮
    # 为什么要有上限？
    #   1. 防止死循环（模型可能一直调工具不收敛）
    #   2. 控制成本（每一轮都要花钱 + 花时间）
    # 真实项目里一般设 5-10 轮，并加上超时和 token 预算
    for turn in range(5):
        print(f"\n--- 第 {turn + 1} 轮 ---")

        # 发请求给模型。注意 tools=tools —— 把工具清单一起发过去，
        # 模型才知道自己能用什么
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            tools=tools,
        )
        # response 是个大对象，真正的回复藏在 choices[0].message 里
        msg = response.choices[0].message

        # ---- 分支 A：模型说"我要调工具" -------------------------------------
        # msg.tool_calls 是模型返回的调用请求列表。
        # ⚠️ 是列表！模型可能一次要调多个工具（比如同时查北京和上海）。
        #    所以必须用 for 遍历，不能只取 [0]，否则会丢数据。
        if msg.tool_calls:
            # 先把"模型想调工具"这个意图也存进历史。
            # 不存的话，后面塞工具结果时模型会对不上号、直接报错。
            messages.append(msg)

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
                result = tool_map[name](**args)
                print(f"  工具返回: {result}")

                # 把工具结果塞回对话历史，让模型在下一轮能看到
                messages.append({
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

        # ---- 分支 B：模型给出了最终答案 -------------------------------------
        # 走到这里说明 msg.tool_calls 是空的，模型认为信息够了，可以直接回答
        print(f"\n最终回答: {msg.content}")
        return msg.content

    # 循环跑满 5 轮还没返回，说明模型卡住了
    return "超过最大轮数了"


# ==============================================================================
# ④ 程序入口
# ==============================================================================
#
# if __name__ == "__main__": 的含义：
#   - 直接运行这个文件（python hello_agent.py）→ __name__ 等于 "__main__"，执行下面的代码
#   - 被别的文件 import 时              → __name__ 等于文件名，【不】执行下面的代码
#
# 为什么要加这层判断？
#   以后你想在别的项目里 import run_agent 复用它，
#   没有这行的话，一 import 就会立刻启动命令行对话，很烦。
#   这是 Python 的标准写法，记住就行。
if __name__ == "__main__":
    print("你的第一个 Agent 启动了，输入 q 退出\n")

    # while True = 无限循环，靠 break 退出
    while True:
        q = input("你: ")      # input() 会暂停程序，等你从键盘输入
        if q == "q":
            break              # 跳出循环，程序结束
        run_agent(q)
