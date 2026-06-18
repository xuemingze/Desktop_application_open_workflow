# mcp_file_tools.py
# 功能: 双 MCP 路由共用的文件工具 Schema 与执行分发层

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from file_tools import read_file_content_sync, open_system_file_sync

FILE_TOOL_NAMES = {"read_file_content", "open_system_file"}

FILE_TOOL_SCHEMAS = [
    {
        "name": "read_file_content",
        "description": "安全读取文本文件内容。用于排查报错、查看日志、理解配置/Markdown/代码片段。长文件会按 max_lines/max_chars 自动截断。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件的绝对路径"},
                "max_lines": {"type": "integer", "description": "最大读取行数，默认 200，最大 2000"},
                "max_chars": {"type": "integer", "description": "最大读取字符数，默认 10000，最大 50000"},
                "read_from_tail": {"type": "boolean", "description": "是否读取文件尾部。读取 .log 最新报错时建议设为 true"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "open_system_file",
        "description": "调用 Windows 默认程序打开文件，或在资源管理器中定位文件。可执行/脚本类文件默认不会直接运行，只允许 explorer 定位。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件或目录的绝对路径"},
                "method": {
                    "type": "string",
                    "enum": ["default", "explorer"],
                    "description": "default: 默认应用打开; explorer: 在资源管理器中定位/打开目录",
                },
            },
            "required": ["path"],
        },
    },
]


def _safe_int(value, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _emit(cb: Optional[Callable[[str], None]], msg: str) -> None:
    if not cb:
        return
    try:
        cb(msg)
    except Exception:
        pass


def handle_file_tool(name: str, arguments: dict | None, log_cb=None, toast_cb=None) -> dict:
    """统一处理文件类 MCP 工具。

    返回 dict，调用方负责 json.dumps 并包装成 MCP TextContent。
    """
    arguments = arguments or {}

    if name == "read_file_content":
        path = arguments.get("path", "")
        max_lines = _safe_int(arguments.get("max_lines", 200), 200)
        max_chars = _safe_int(arguments.get("max_chars", 10000), 10000)
        read_from_tail = bool(arguments.get("read_from_tail", False))

        msg = f"🔍 AI 正在读取文件: {Path(str(path)).name or path}"
        _emit(log_cb, msg)
        _emit(toast_cb, msg)

        return read_file_content_sync(path, max_lines=max_lines, max_chars=max_chars, read_from_tail=read_from_tail)

    if name == "open_system_file":
        path = arguments.get("path", "")
        method = arguments.get("method", "default")

        msg = f"📂 AI 正在打开/定位文件: {Path(str(path)).name or path} ({method})"
        _emit(log_cb, msg)
        _emit(toast_cb, msg)

        return open_system_file_sync(path, method=method)

    return {"ok": False, "error": f"未知的文件工具: {name}"}
