from apps.assistant import SYSTEM_PROMPT,get_weather, calculate, get_time, get_stock_price   
from core.agent import Agent   


if __name__ == "__main__":
    # ★ 新建一个 Agent 对象。这一行之后，agent 就带着自己的记忆了
    agent = Agent(tools=[get_weather, calculate, get_time, get_stock_price],system_prompt=SYSTEM_PROMPT)

    print("你的第一个 Agent 启动了，输入 q 退出\n")

    # while True = 无限循环，靠 break 退出
    while True:
        q = input("你: ")      # input() 会暂停程序，等你从键盘输入
        if q == "q":
            break              # 跳出循环，程序结束
        agent.run(q)           # 注意：调用的是【这个对象】的方法