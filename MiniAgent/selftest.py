r"""
工具箱自检脚本

用法：
    cd C:\Users\11192\agent-study\MiniAgent
    C:\Users\11192\agent-study\.venv\Scripts\python.exe selftest.py

什么时候用：
    每次改完 apps/coding_agent.py，跑一遍。全绿才算改对了。

为什么要有这个东西：
    改代码最怕"改好了 A，弄坏了 B"。
    有自检脚本，你改完跑一下，5 秒知道有没有弄坏别的东西。
"""

import os
import sys
import json


from apps.coding_agent import read_file, write_file, run_command
from apps.coding_agent import WORKSPACE, MAX_READ_LINES

# ---------------------------------------------------------------- 测试框架

PASSED = 0
FAILED = 0
DETAILS = []


def check(name, condition, detail=""):
    """一个断言。condition 为 True 算通过。"""
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print("  [PASS] %s" % name)
    else:
        FAILED += 1
        print("  [FAIL] %s" % name)
        if detail:
            print("         实际: %r" % (detail,))


def section(title):
    print()
    print("-" * 62)
    print(title)
    print("-" * 62)


# ---------------------------------------------------------------- 准备

LONG_FILE = "long.txt"
OVERRIDE_FILE = "override.txt"
CMD_FILE = "hello.py"

# 造一个 120 行的文件（比 MAX_READ_LINES=50 多）
long_content = "".join("第 %d 行\n" % i for i in range(1, 121))
write_file(LONG_FILE, long_content)

print("=" * 62)
print("coding_agent 自检")
print("=" * 62)
print("workspace: %s" % WORKSPACE)
print("MAX_READ_LINES = %d" % MAX_READ_LINES)


# ---------------------------------------------------------------- 1. 读

section("1. read_file —— 读正常文件")

write_file("simple.txt", "第一行\n第二行\n第三行\n")
r = read_file("simple.txt")
check("能读到内容", "第一行" in r, r)
check("内容完整（3 行都在）", all(x in r for x in ("第一行", "第二行", "第三行")), r)
check("返回值是字符串", isinstance(r, str), type(r))


section("2. read_file —— 截断（关键：MAX_READ_LINES 生效了吗）")

r = read_file(LONG_FILE)
lines_in_result = len([l for l in r.splitlines() if l.startswith("第 ")])
check("文件有 120 行，只返回 %d 行" % MAX_READ_LINES,
      lines_in_result == MAX_READ_LINES, "%d 行" % lines_in_result)
check("截断时给了提示", "共 120 行" in r or "只显示前" in r, r[-60:])


section("3. read_file —— 错误处理")

r = read_file("does_not_exist.txt")
check("文件不存在时不崩，返回提示", "不存在" in r, r)


section("4. read_file —— 路径安全 ★")

r = read_file("../../.env")
check("读 ../../.env 被拒绝", "拒绝" in r, r)
r = read_file("../core/agent.py")
check("读 ../core/agent.py 被拒绝", "拒绝" in r, r)
r = read_file("simple.txt")
check("读 workspace 内文件正常", "第一行" in r, r)


# ---------------------------------------------------------------- 2. 写

section("5. write_file —— 新建")

if os.path.exists(os.path.join(WORKSPACE, OVERRIDE_FILE)):
    os.remove(os.path.join(WORKSPACE, OVERRIDE_FILE))
r = write_file(OVERRIDE_FILE, "内容 A")
check("返回成功提示", "已写入" in r, r)
check("没误报'已覆盖'", "已覆盖" not in r, r)
check("文件真的存在", os.path.exists(os.path.join(WORKSPACE, OVERRIDE_FILE)))


section("6. write_file —— 覆盖（改造任务 3）")

r = write_file(OVERRIDE_FILE, "内容 B")
check("第二次写入时提示'已覆盖'", "已覆盖" in r, r)
# 注意：read_file 现在会追加"（共 N 行）"后缀，所以用 startswith 判断，不能用 ==
check("内容被覆盖了", read_file(OVERRIDE_FILE).startswith("内容 B"), read_file(OVERRIDE_FILE))


section("7. write_file —— 自动建子目录")

r = write_file("sub/dir/a.txt", "深层文件")
check("能自动建目录并写入", "已写入" in r, r)
check("文件真的存在", os.path.exists(os.path.join(WORKSPACE, "sub", "dir", "a.txt")))


section("8. write_file —— 路径安全 ★")

r = write_file("../../hack.txt", "恶意写入")
check("写 ../../hack.txt 被拒绝", "拒绝" in r, r)
check("workspace 外没有生成文件",
      not os.path.exists(os.path.join(os.path.dirname(WORKSPACE), "hack.txt")))


# ---------------------------------------------------------------- 3. 执行

section("9. run_command —— 正常命令")

r = run_command("echo hello")
check("有输出", "hello" in r, r)


section("10. run_command —— 中文输出（编码坑）")

r = run_command("echo 你好世界")
check("中文不乱码", "你好世界" in r, r)


section("11. run_command —— 失败命令")

r = run_command("nonexistent_command_xyz")
check("失败时有提示", "失败" in r or "返回码" in r, r)


section("12. run_command —— 超时")

r = run_command("ping 127.0.0.1 -n 30")
check("超时被捕获，没崩", "超时" in r, r[:60])
section("12.5 run_command —— 危险命令拦截 ★")

r = run_command("del /s /q x")
check("del /s 被拒绝", "拒绝" in r, r)

r = run_command("DEL  /S  /Q x")
check("大写+多空格也拦得住", "拒绝" in r, r)

r = run_command("del/s/q x")
check("紧凑写法也拦得住", "拒绝" in r, r)

r = run_command("format c:")
check("format 被拒绝", "拒绝" in r, r)

r = run_command("dir")
check("正常命令不被误杀", "拒绝" not in r, r)



section("13. 串联：写文件 → 执行它 ★★")

write_file(CMD_FILE, "print('Hello from generated file')\n")
r = run_command("python %s" % CMD_FILE)
check("生成的 py 文件能被跑起来", "Hello from generated file" in r, r)


section("14. run_command —— cwd 是否在 workspace")

r = run_command("cd")
check("命令在 workspace 里执行", "workspace" in r.lower(), r)

# ---------------------------------------------------------------- 6.1 / 6.2 补测

section("15. 日志模块（6.2）")

import glob
from core.logger import log_event, LOG_DIR

log_event("selftest_marker", note="hello")

files = glob.glob(os.path.join(LOG_DIR, "*.jsonl"))
check("日志文件已生成", len(files) > 0, files)

last_line = open(sorted(files)[-1], encoding="utf-8").read().strip().splitlines()[-1]
try:
    last_record = json.loads(last_line)
    check("最后一行是合法 JSON", True)
except Exception as e:
    last_record = {}
    check("最后一行是合法 JSON", False, str(e))

check("最后一条是 selftest_marker", last_record.get("event") == "selftest_marker", last_record)


section("16. 重试逻辑（6.1）")

from core.retry import call_with_retry, is_retryable

# 用 base_delay=0 跑，只测逻辑不测等待，否则自检会多花 3 秒
counter = {"n": 0}


def flaky():
    counter["n"] += 1
    if counter["n"] < 3:
        raise ConnectionError("假的网络错误")
    return "ok"


check("失败 2 次后成功", call_with_retry(flaky, max_retries=2, base_delay=0) == "ok", counter["n"])
check("总共调用了 3 次（1 次正常 + 2 次重试）", counter["n"] == 3, counter["n"])


def always_fail():
    raise ConnectionError("一直失败")


try:
    call_with_retry(always_fail, max_retries=1, base_delay=0)
    check("重试用完后会抛出", False, "没有抛异常")
except ConnectionError:
    check("重试用完后会抛出", True)


check("ConnectionError 判定为可重试", is_retryable(ConnectionError("x")) is True)
check("ValueError 判定为不可重试", is_retryable(ValueError("x")) is False)




# ---------------------------------------------------------------- 收尾

section("清理测试文件")

for f in (LONG_FILE, OVERRIDE_FILE, CMD_FILE, "simple.txt"):
    p = os.path.join(WORKSPACE, f)
    if os.path.exists(p):
        os.remove(p)
import shutil
sub = os.path.join(WORKSPACE, "sub")
if os.path.exists(sub):
    shutil.rmtree(sub)
print("  已清理")


# ---------------------------------------------------------------- 结果

print()
print("=" * 62)
print("结果：%d 通过 / %d 失败" % (PASSED, FAILED))
print("=" * 62)

if FAILED == 0:
    print()
    print("  ✅ 全部通过")
    sys.exit(0)
else:
    print()
    print("  ❌ 有 %d 项失败，往上翻看 [FAIL] 那几行" % FAILED)
    sys.exit(1)
