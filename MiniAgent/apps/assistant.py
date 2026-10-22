import datetime
from core.agent import tool
SYSTEM_PROMPT = (
    "你是一个有用的助手。需要查天气、算数或查股票价格时，"
    "必须调用工具，不许自己编答案。"
)

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