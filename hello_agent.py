import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)

# ============ 1. 工具：真正能干活的 Python 函数 ============

def get_weather(city):
    data = {
        "北京": "晴，26度，微风",
        "上海": "多云，30度，湿度大",
        "杭州": "小雨，24度，记得带伞",
    }
    return data.get(city, f"{city}：暂无数据")

def calculate(expression):
    # 注意：eval 只能在学习时这么玩，真实项目里绝对不能用
    try:
        return str(eval(expression))
    except Exception as e:
        return f"算错了：{e}"

# ============ 2. 告诉模型"你有哪些工具可以用" ============

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查询指定城市的天气",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名称，例如 北京"}
                },
                "required": ["city"],
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
                    "expression": {"type": "string", "description": "数学表达式"}
                },
                "required": ["expression"],
            },
        },
    },
]

tool_map = {
    "get_weather": get_weather,
    "calculate": calculate,
}

# ============ 3. Agent 主循环（核心） ============

def run_agent(user_input):
    messages = [
        {"role": "system", "content": "你是一个有用的助手。需要查天气或算数时，必须调用工具，不许自己编答案。"},
        {"role": "user", "content": user_input},
    ]

    for turn in range(5):  # 最多转 5 轮，防止死循环
        print(f"\n--- 第 {turn + 1} 轮 ---")

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            tools=tools,
        )
        msg = response.choices[0].message

        # 情况 A：模型说"我要调工具"
        if msg.tool_calls:
            messages.append(msg)
            for tool_call in msg.tool_calls:
                name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)
                print(f"  模型要调工具: {name}({args})")

                result = tool_map[name](**args)
                print(f"  工具返回: {result}")

                # 把工具结果塞回对话，让模型看到
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })
            continue  # 回到循环开头，让模型继续思考

        # 情况 B：模型给出最终答案
        print(f"\n最终回答: {msg.content}")
        return msg.content

    return "超过最大轮数了"

if __name__ == "__main__":
    print("你的第一个 Agent 启动了，输入 q 退出\n")
    while True:
        q = input("你: ")
        if q == "q":
            break
        run_agent(q)
