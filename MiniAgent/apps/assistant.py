"""Small demonstration tools for the same Agent runtime."""

import ast
import datetime
import math
import operator

from core.agent import ToolError, tool

SYSTEM_PROMPT = (
    "你是一个演示助手。算数、查时间、天气或股票时使用对应工具。"
    "天气和股票工具返回固定演示数据，请向用户说明。"
)

_BINARY = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_MAX_NUMBER = 10 ** 12


def _arithmetic(node):
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        result = node.value
    elif isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
        result = _BINARY[type(node.op)](_arithmetic(node.left), _arithmetic(node.right))
    elif isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        result = _UNARY[type(node.op)](_arithmetic(node.operand))
    else:
        raise ToolError("仅支持数字、括号和 + - * / // % 运算。")
    if abs(result) > _MAX_NUMBER or not math.isfinite(result):
        raise ToolError("数值超出计算范围。")
    return result


@tool
def calculate(expression: str):
    """计算长度不超过 128 字符的算术表达式，支持 + - * / // %。"""
    if len(expression) > 128:
        raise ToolError("表达式过长。")
    try:
        tree = ast.parse(expression.strip(), mode="eval")
        return str(_arithmetic(tree.body))
    except SyntaxError as exc:
        raise ToolError("算术表达式格式不正确。") from exc
    except ZeroDivisionError as exc:
        raise ToolError("除数不能为零。") from exc


@tool
def get_weather(city: str):
    """读取城市的固定天气样例。"""
    data = {"北京": "晴，26 度", "上海": "多云，30 度", "杭州": "小雨，24 度"}
    return f"演示数据：{city}，{data.get(city, '暂无数据')}"


@tool
def get_time():
    """返回本机时间和时区偏移。"""
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


@tool
def get_stock_price(code: str):
    """返回证券代码的固定价格样例。"""
    return f"演示数据：{code}，100 元"


TOOLS = [get_weather, calculate, get_time, get_stock_price]
