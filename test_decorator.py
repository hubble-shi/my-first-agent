def log(func):
    def wrapper(*args, **kwargs):
        print(f"[日志] 即将调用{func.__name__}, 参数为{args}, {kwargs}")
        result=func(*args, **kwargs)
        print(f"[日志] 调用{func.__name__} 调用结束, 返回值为{result}")
        return result
    return wrapper


@log
def say_hello():
    print("你好，我是被装饰的函数")

@log
def add(a, b):
    return a + b

@log
def greet(name, greeting="你好"):
    return f"{greeting}，{name}"

say_hello()
print("---")
print("计算结果:", add(3, 5))
print("---")
print(greet("Hubble", greeting="早上好"))