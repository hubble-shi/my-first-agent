import time
from openai import (
    APIConnectionError,   # 网络连不上 / DNS 失败 / 连接被重置
    APITimeoutError,      # 请求超时
    RateLimitError,       # 429 限流
    InternalServerError,  # 500 服务端内部错误
    APIError,             # 其他带 status_code 的 API 错误（用来兜底判断 5xx）
)


def is_retryable(e: Exception) -> bool:
    """判断错误是否可重试。

    可重试的（瞬时错误）：
      - 网络连接错误、超时
      - 429 限流（等一会儿可能就好）
      - 5xx 服务端错误
    不可重试的（请求本身有问题）：
      - 401 认证失败、403 无权限、404 不存在、400 参数错误
      - 其他非 5xx 的 API 错误
    """
    # 内置的瞬时错误：有些底层库（requests / socket）会直接抛原生异常，
    # 不是 openai 包装过的类型。这些同样该重试。
    if isinstance(e, (ConnectionError, TimeoutError)):
        return True

    # 明确属于"瞬时错误"的类型
    if isinstance(e, (APIConnectionError, APITimeoutError, RateLimitError, InternalServerError)):
        return True

    # 兜底：其他 APIError 只重试 5xx
    if isinstance(e, APIError):
        code = getattr(e, "status_code", None)
        if code is not None and code >= 500:
            return True

    return False


def call_with_retry(func, max_retries=2, base_delay=1):
    """
    func 是零参数可调用；返回它的结果。

    失败且可重试时，等一会儿再试，最多重试 max_retries 次。
    不可重试的错误立刻抛出；重试用完仍失败，抛出最后一次的错误。
    """
    # 为什么要 +1：max_retries=2 表示"重试 2 次"，
    # 加上第一次正常尝试，总共是 3 次机会
    for attempt in range(max_retries + 1):
        try:
            return func()

        except Exception as e:
            # ① 不可重试的错误（参数错、鉴权失败等）—— 立刻抛，别浪费时间
            if not is_retryable(e):
                raise

            # ② 次数已经用完 —— 抛出最后一次的错误给上层
            if attempt == max_retries:
                raise

            # ③ 指数退避：第 1 次等 base_delay，第 2 次等 2 倍，第 3 次等 4 倍...
            #    为什么要等而不是立刻重试：服务端已经不舒服了，
            #    一秒内发三次请求只会让它更难受（这就是雪崩）
            wait = base_delay * (2 ** attempt)
            print(f"  [重试] 第 {attempt + 1}/{max_retries} 次，等 {wait}s 后重来：{e}")
            time.sleep(wait)

