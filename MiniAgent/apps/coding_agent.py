"""Workspace tools created separately for each coding agent."""

import codecs
import itertools
import ntpath
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path, PureWindowsPath

from core.agent import ToolError, tool

SYSTEM_PROMPT = (
    "你是编程助手。文件路径相对于工作区，使用 list_files 和 read_file 查看文件，"
    "使用 write_file 写入完整文本。覆盖已有文件前先读内容，并通过终端获得用户确认。"
    "如果注册了 run_python，可请求运行工作区里的 Python 脚本。"
    "根据工具返回的实际结果汇报，尤其要区分成功、拒绝和失败。"
)

MAX_FILE_BYTES = 16 * 1024
MAX_OUTPUT_BYTES = 4 * 1024
MAX_LIST_ENTRIES = 100
TIMEOUT_SECONDS = 15
_is_windows_reserved = getattr(ntpath, "isreserved", lambda part: PureWindowsPath(part).is_reserved())


def _workspace_path(root, path):
    windows_path = PureWindowsPath(path)
    relative = Path(path)
    if (
        not path or relative.anchor or windows_path.anchor or ":" in path
        or any(ord(char) < 32 or 127 <= ord(char) < 160 for char in path)
        or ".." in relative.parts or ".." in windows_path.parts
        or any(part.endswith((" ", ".")) or _is_windows_reserved(part) for part in windows_path.parts)
    ):
        raise ToolError("请使用工作区内的相对路径。")

    try:
        target = (root / relative).resolve()
    except (OSError, RuntimeError, ValueError) as exc:
        raise ToolError("路径无法解析。") from exc
    if not target.is_relative_to(root):
        raise ToolError("路径指向工作区外。")
    return target


def _bounded_read(stream, limit, errors):
    data = stream.read(limit + 1)
    truncated = len(data) > limit
    decoder = codecs.getincrementaldecoder("utf-8")(errors=errors)
    text = decoder.decode(data[:limit], final=not truncated)
    return text + (f"\n… 已截断至前 {limit} 字节。" if truncated else "")


def _create_file(target, data):
    created = None
    try:
        with target.open("xb") as file:
            created = os.fstat(file.fileno())
            file.write(data)
    except (OSError, KeyboardInterrupt):
        if created is not None:
            try:
                if os.path.samestat(created, target.lstat()):
                    target.unlink()
            except OSError:
                pass
        raise


def _file_revision(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _check_file_unchanged(target, original):
    try:
        current = target.lstat()
    except FileNotFoundError as exc:
        raise ToolError("确认后发现文件已变动，请重新检查。") from exc
    if target.resolve() != target or _file_revision(current) != _file_revision(original):
        raise ToolError("确认后发现文件已变动，请重新检查。")


def _write_text(target, data, approve_overwrite):
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        _create_file(target, data)
        return
    except FileExistsError:
        if approve_overwrite is None:
            raise

    original = target.lstat()
    if not stat.S_ISREG(original.st_mode):
        raise ToolError("只能覆盖工作区内的普通文件。")
    if not approve_overwrite(target):
        raise ToolError("用户拒绝覆盖文件。")
    _check_file_unchanged(target, original)

    staged = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as file:
            staged = Path(file.name)
            file.write(data)
        if os.name == "posix":
            staged.chmod(original.st_mode & 0o777)
        _check_file_unchanged(target, original)
        staged.replace(target)
    finally:
        if staged is not None:
            staged.unlink(missing_ok=True)


def build_tools(workspace, *, approve_overwrite=None, approve_python=None):
    """Bind file tools to one workspace and optionally expose script execution."""
    root = Path(workspace).resolve()

    @tool
    def list_files(path: str = "."):
        """列出工作区内一个目录的直接子项，最多 100 项。"""
        target = _workspace_path(root, path)
        try:
            with os.scandir(target) as entries:
                items = list(itertools.islice(entries, MAX_LIST_ENTRIES + 1))
                names = [
                    item.name + ("/" if item.is_dir(follow_symlinks=False) else "")
                    for item in items[:MAX_LIST_ENTRIES]
                ]
        except OSError as exc:
            raise ToolError("无法列出这个目录。") from exc
        if len(items) > MAX_LIST_ENTRIES:
            names.append("… 仅显示前 100 项。")
        return "\n".join(names) or "目录为空。"

    @tool
    def read_file(path: str):
        """读取工作区内的 UTF-8 文本文件，最多返回 16 KiB。"""
        target = _workspace_path(root, path)
        try:
            if not target.is_file():
                raise ToolError("只能读取工作区内的普通文件。")
            with target.open("rb") as file:
                return _bounded_read(file, MAX_FILE_BYTES, "strict")
        except UnicodeDecodeError as exc:
            raise ToolError("文件不是有效的 UTF-8 文本。") from exc
        except OSError as exc:
            raise ToolError("无法读取文件。") from exc

    @tool
    def write_file(path: str, content: str, overwrite: bool = False):
        """写入工作区文件，最多 16 KiB。覆盖已有文件须传 overwrite=true 并得到用户确认。"""
        target = _workspace_path(root, path)
        try:
            if target == root or target.is_dir():
                raise ToolError("请选择工作区内的文件路径。")
            data = content.encode("utf-8")
            if len(data) > MAX_FILE_BYTES:
                raise ToolError("写入内容超过 16 KiB。")
            _write_text(target, data, approve_overwrite if overwrite else None)
        except FileExistsError as exc:
            raise ToolError("文件已存在。请先读取，覆盖时须显式请求并经用户确认。") from exc
        except (OSError, UnicodeEncodeError) as exc:
            raise ToolError("无法写入文件。") from exc
        return f"已写入 {path}（{len(data)} 字节）。"

    tools = [list_files, read_file, write_file]
    if approve_python is None:
        return tools

    @tool
    def run_python(path: str):
        """经用户确认后运行工作区内的 Python 脚本，限时 15 秒。"""
        target = _workspace_path(root, path)
        try:
            original = target.lstat()
            if target.suffix.lower() != ".py" or not stat.S_ISREG(original.st_mode):
                raise ToolError("只能运行工作区内已存在的 .py 文件。")
            if not approve_python(target):
                raise ToolError("用户拒绝运行脚本。")
            _check_file_unchanged(target, original)
        except OSError as exc:
            raise ToolError("无法检查待运行的脚本。") from exc
        return _run_python(target, root)

    return [*tools, run_python]


def _run_python(target, root):
    inherited = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "TMPDIR"}
    environment = {key: value for key, value in os.environ.items() if key.upper() in inherited}
    try:
        with tempfile.TemporaryFile() as output:
            process = subprocess.run(
                [sys.executable, "-X", "utf8", "-u", str(target)],
                cwd=root,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=subprocess.STDOUT,
                timeout=TIMEOUT_SECONDS,
                check=False,
            )
            output.seek(0)
            text = _bounded_read(output, MAX_OUTPUT_BYTES, "replace")
    except subprocess.TimeoutExpired as exc:
        raise ToolError(f"脚本超过 {TIMEOUT_SECONDS} 秒运行上限。") from exc
    except OSError as exc:
        raise ToolError("无法启动 Python 脚本。") from exc
    if process.returncode:
        raise ToolError(f"脚本退出码 {process.returncode}。\n{text}")
    return text or "脚本执行完成，无输出。"
