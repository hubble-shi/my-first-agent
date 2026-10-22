"""
Coding Agent 的三个工具：读文件 / 写文件 / 执行命令

【这个文件和 assistant.py 的区别】

assistant.py 的工具是"查东西"——查天气、算数。查错了大不了答案不对。
这个文件的工具是"动东西"——读文件、写文件、跑命令。做错了会丢数据、会删代码。

所以这个文件里多了两样东西：
  ① 路径检查（_safe_path）—— 不许跑出 workspace 目录
  ② 错误捕获（try/except）—— 出错了返回一句话，不许崩
"""

import os
import subprocess
from core.agent import tool


# ==============================================================================
# 常量：三个"刹车"
# ==============================================================================

# __file__     = ...\MiniAgent\apps\coding_agent.py
# dirname 一次  = ...\MiniAgent\apps
# dirname 两次  = ...\MiniAgent
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ...\MiniAgent\workspace —— 所有文件操作都限制在这里
WORKSPACE = os.path.join(BASE_DIR, "workspace")

# 读文件最多返回多少行（防止一个大日志文件撑爆上下文）
MAX_READ_LINES = 50

# 命令输出最多返回多少字符（同上）
MAX_OUTPUT_CHARS = 2000

# 命令最多跑多少秒（防止 ping 这种卡死）
TIMEOUT = 15


# ==============================================================================
# 内部辅助函数：不是工具，模型看不到，只给下面三个工具用
# 名字前面加下划线 _ 是 Python 的约定，意思是"内部用的，别在外面调"
# ==============================================================================


def _safe_path(path):
    """
    把用户给的路径，变成 workspace 内的绝对路径。

    返回：
        合法的绝对路径 -> 返回那个路径
        想跑到 workspace 外面 -> 返回 None（调用方据此拒绝）
    """
    # abspath 会把 ".." 和 "." 都算掉，得到干净的绝对路径
    # 比如 join(WORKSPACE, "../../.env") 再 abspath
    #   -> C:\Users\11192\agent-study\.env
    full = os.path.abspath(os.path.join(WORKSPACE, path))

    # startswith 后面加 os.sep（反斜杠）是关键：
    #   不加的话，"...\MiniAgent\workspace_evil\x" 也会被认为是合法的
    #   加了之后，必须正好以 "...\MiniAgent\workspace\" 开头才算
    # 后面那个 `or full == WORKSPACE` 是为了允许访问 workspace 目录本身
    if not full.startswith(WORKSPACE + os.sep) and full != WORKSPACE:
        return None

    return full


def _decode(raw_bytes):
    """
    把命令输出的 bytes 变成字符串。

    【为什么要这么麻烦】
    Windows 命令行输出是 GBK 编码，不是 UTF-8。
    直接用 utf-8 解码会得到乱码，甚至让 subprocess 的后台线程崩掉，
    导致 r.stderr 变成 None。

    策略：先试 utf-8，失败再试 gbk，都不行就替换坏字符（不崩）。
    """
    for enc in ("utf-8", "gbk"):
        try:
            return raw_bytes.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw_bytes.decode("utf-8", errors="replace")


# ==============================================================================
# 工具一：读文件
# ==============================================================================


@tool
def read_file(path: str):
    """读取指定文件的内容（最多返回前 200 行）"""

    # 第一步：安全检查。跑出 workspace 就拒绝
    full = _safe_path(path)
    if full is None:
        return "拒绝访问：路径超出工作目录"

    # 第二步：读文件
    # with 会自动关文件；try/except 保证"文件不存在"时返回提示而不是崩掉
    try:
        with open(full, encoding="utf-8") as f:
            lines = f.readlines()          # 列表，每个元素是一行（带 \n）
    except FileNotFoundError:
        return f"文件不存在：{path}"
    except UnicodeDecodeError:
        return f"读取失败：{path} 不是文本文件，或编码不支持"

    # 第三步：截断
    # 文件有 5 万行时，全塞进 messages 会把上下文撑爆
    if len(lines) > MAX_READ_LINES:
        body = "".join(lines[:MAX_READ_LINES])     # 列表 -> 字符串
        return body + f"\n\n...（文件共 {len(lines)} 行，只显示前 {MAX_READ_LINES} 行）"

    return "".join(lines)+ f"\n\n（共 {len(lines)} 行）"


# ==============================================================================
# 工具二：写文件
# ==============================================================================


@tool
def write_file(path: str, content: str):
    """把内容写入指定文件（会覆盖原内容）"""

    full = _safe_path(path)
    if full is None:
        return "拒绝访问：路径超出工作目录"

    try:
        # 如果目标是 workspace\sub\a.txt，而 sub 目录不存在，先把它建出来
        parent = os.path.dirname(full)
        if parent and not os.path.exists(parent):
            os.makedirs(parent, exist_ok=True)
        
        existed = os.path.exists(full)

        # "w" = 写入模式，文件已存在会被清空
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)
        
        size = len(content.encode("utf-8"))
        suffix = "，已覆盖" if existed else ""
        return f"已写入 {path}（{size} 字节{suffix}）"
    except OSError as e:
        # OSError 覆盖了权限不足、磁盘满、路径非法等各种文件系统错误
        return f"写入失败：{e}"



# ==============================================================================
# 工具三：执行命令
# ==============================================================================


@tool
def run_command(command: str):
    """在 workspace 目录下执行一条命令，返回输出"""

    try:
        r = subprocess.run(
            command,              # 要执行的命令，比如 "dir" 或 "python main.py"
            shell=True,           # 让系统 shell 解释（dir / echo 是 shell 内建命令）
            capture_output=True,  # 把输出抓回来，而不是直接打印到屏幕
            timeout=TIMEOUT,      # 超时就杀掉，抛 TimeoutExpired
            cwd=WORKSPACE,        # 在 workspace 里执行，不是在你的项目根目录
            # 注意：这里不写 text=True 和 encoding —— 见 _decode 的注释
        )
    except subprocess.TimeoutExpired:
        return f"命令执行超时（{TIMEOUT} 秒）：{command}"

    # 拿到的是 bytes，自己解码
    out = _decode(r.stdout)
    err = _decode(r.stderr)

    # returncode：0 = 成功，非 0 = 失败
    if r.returncode == 0:
        text = out or "(命令执行成功，但没有任何输出)"
    else:
        # 失败时优先看 stderr（错误信息），有些命令也会往 stdout 写错误
        text = f"命令失败（返回码 {r.returncode}）\n{err or out}"

    # 截断，防止 "dir C:\" 这种命令返回几千行
    if len(text) > MAX_OUTPUT_CHARS:
        text = text[:MAX_OUTPUT_CHARS] + f"\n\n...（输出过长，只显示前 {MAX_OUTPUT_CHARS} 字符）"

    return text
