import inspect

# 全局工具注册表：所有被 @tool 装饰的函数都会登记到这里
TOOL_REGISTRY = []

# Python 类型 → JSON schema 类型的映射
TYPE_MAP = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
}


def tool(func):
    """把一个普通函数注册成 Agent 可用的工具"""

    # ① 工具名（你已经会了）
    name = func.__name__

    # ② 描述（文档字符串，没有就空字符串）
    description = func.__doc__ or ""

    # ③ 参数信息
    sig = inspect.signature(func)
    properties = {}
    required = []

    for param_name, param in sig.parameters.items():

        # TODO 1: 把 param.annotation 通过 TYPE_MAP 翻译成 JSON 类型
        #         提示：TYPE_MAP.get(param.annotation, "string")
        json_type = TYPE_MAP.get(param.annotation, "string")

        # TODO 2: 组装这个参数的 schema
        #         提示：properties[param_name] = {"type": json_type}
        properties[param_name] = {"type": json_type}

        # TODO 3: 判断是否必填，是的话加到 required 里
        #         提示：if param.default is inspect.Parameter.empty:
        if param.default is inspect.Parameter.empty:
            required.append(param_name)

    # ④ 组装完整结构并注册
    TOOL_REGISTRY.append({
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

    # ⑤ 把原函数还回去（别忘了这行！）
    return func


# ============ 测试 ============

@tool
def get_weather(city: str):
    """查询指定城市的天气"""
    return f"{city}：晴"


@tool
def add(a: int, b: int, precision: int = 0):
    """两数相加"""
    return a + b


@tool
def search(keyword: str, limit: int = 10, fuzzy: bool = False):     # ← 移上来
    """搜索内容"""
    return f"搜索 {keyword}"


# 最后才打印
import json
print(json.dumps(TOOL_REGISTRY, ensure_ascii=False, indent=2))

