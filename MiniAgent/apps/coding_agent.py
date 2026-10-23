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
from core.logger import log_event

SYSTEM_PROMPT = (
    "你是一个编程助手，可以读写文件、执行命令。\n"
    "所有文件操作都在 workspace 目录内进行。\n"
    "path 直接写相对路径（如 hello.py），不要加 workspace/ 前缀。\n"
    "\n"
    "【运行环境】\n"
    "- 操作系统：Windows\n"
    "- 命令行：cmd\n"
    "- Python 命令：python（不是 python3，也不是 py）\n"
    "- 执行命令前，先想清楚这条命令会做什么。\n"
    "- 需要多步操作时，一步一步来，每步都确认结果。"
)


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
MAX_READ_LINES = 200

# 命令输出最多返回多少字符（同上）
MAX_OUTPUT_CHARS = 2000

# 命令最多跑多少秒（防止 ping 这种卡死）
TIMEOUT = 15

# 危险命令黑名单（归一化后做子串匹配）
# ⚠️ 这只是"减速带"，不是"墙" —— 详见 README 里的安全说明
DANGEROUS_PATTERNS = (
    "format",        # 格式化磁盘
    "del ",          # 删除
    "erase ",        # 删除（另一种写法）
    "rmdir",         # 删目录
    "rd ",           # 删目录（简写）
    "shutdown",      # 关机
    "taskkill",      # 杀进程
    "reg delete",    # 删注册表
    "bcdedit",       # 改启动配置
    "diskpart",      # 磁盘分区
)



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

def _normalize_command(cmd: str) -> str:
    """
    把命令归一化，防止各种写法绕过黑名单。

    'DEL  /S  /Q x'  ->  'del / s / q x'
    'del/s/q x'      ->  'del / s / q x'

    注意：只用于匹配，不影响实际执行的命令。
    """
    n = cmd.lower().replace("/", " / ")
    return " ".join(n.split())


def _check_command(cmd: str):
    """
    检查命令是否危险。
    返回命中的危险模式；安全返回 None。
    """
    n = _normalize_command(cmd)
    for p in DANGEROUS_PATTERNS:
        if p in n:
            return p.strip()
    return None



# ==============================================================================
# 工具一：读文件
# ==============================================================================


@tool
def read_file(path: str):
    """读取文件内容。
    path 是【相对 workspace 的路径】，例如 "test.txt"。
    不要写 "workspace/" 前缀。最多返回前 200 行。"""

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
    """把内容写入文件（会覆盖原内容）。
    path 是【相对 workspace 的路径】，例如 "hello.py"。
    不要写 "workspace/" 前缀。"""


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

    # ★ 第一步：安全检查。危险命令直接拒绝，不进入 subprocess
    hit = _check_command(command)
    if hit:
        log_event("command_blocked", command=command, pattern=hit)
        return (
            f"拒绝执行：这条命令包含危险操作（{hit}）。"
            "它会破坏系统或数据，我无法执行。"
            "如果你确实需要，请自己手动操作。"
        )

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
