# file_tools.py
# 功能: 为 MCP/AI 提供安全的文件读取与本地打开能力

from __future__ import annotations

import os
import subprocess
from collections import deque
from pathlib import Path

MAX_FILE_BYTES = 20 * 1024 * 1024
DEFAULT_MAX_LINES = 200
DEFAULT_MAX_CHARS = 10_000
MAX_LINES_LIMIT = 2_000
MAX_CHARS_LIMIT = 50_000
READABLE_ENCODINGS = ("utf-8-sig", "utf-8", "gbk", "utf-16", "latin-1")
DANGEROUS_OPEN_EXTS = {
    ".exe", ".bat", ".cmd", ".com", ".msi", ".msp", ".scr",
    ".ps1", ".vbs", ".vbe", ".js", ".jse", ".wsf", ".wsh",
    ".jar", ".reg",
}


def _clamp_int(value, default: int, minimum: int, maximum: int) -> int:
    try:
        num = int(value)
    except Exception:
        num = default
    return max(minimum, min(num, maximum))


def _normalize_path(path: str) -> Path:
    return Path(str(path or "").strip()).expanduser()


def _looks_binary(raw: bytes) -> bool:
    if not raw:
        return False
    if b"\x00" in raw[:4096]:
        return True
    return False


def _decode_bytes(raw: bytes) -> tuple[str | None, str | None]:
    if _looks_binary(raw):
        return None, None
    for enc in READABLE_ENCODINGS:
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return None, None


def read_file_content_sync(
    path: str,
    max_lines: int = DEFAULT_MAX_LINES,
    max_chars: int = DEFAULT_MAX_CHARS,
    read_from_tail: bool = False,
) -> dict:
    """安全读取文本文件内容。

    - 文件必须存在且是普通文件。
    - 超过 20MB 拒绝读取，避免撑爆内存/上下文。
    - max_lines 和 max_chars 双重限制输出规模。
    - read_from_tail=True 适合读取日志尾部。
    """
    p = _normalize_path(path)
    max_lines = _clamp_int(max_lines, DEFAULT_MAX_LINES, 1, MAX_LINES_LIMIT)
    max_chars = _clamp_int(max_chars, DEFAULT_MAX_CHARS, 100, MAX_CHARS_LIMIT)

    if not str(p):
        return {"ok": False, "error": "path 为空", "path": path}
    if not p.exists():
        return {"ok": False, "error": f"文件不存在: {p}", "path": str(p)}
    if not p.is_file():
        return {"ok": False, "error": f"路径不是文件: {p}", "path": str(p)}

    try:
        file_size = p.stat().st_size
    except OSError as e:
        return {"ok": False, "error": f"无法读取文件信息: {e}", "path": str(p)}

    if file_size > MAX_FILE_BYTES:
        return {
            "ok": False,
            "error": f"文件体积过大 ({file_size / 1024 / 1024:.1f}MB)，已超过 20MB 安全限制。请使用 open_system_file 在本地打开查看。",
            "path": str(p),
            "file_size": file_size,
        }

    try:
        raw = p.read_bytes()
    except OSError as e:
        return {"ok": False, "error": f"读取失败: {e}", "path": str(p), "file_size": file_size}

    text, encoding = _decode_bytes(raw)
    if text is None:
        return {
            "ok": False,
            "error": "无法解析文件编码，或疑似二进制文件。请使用 open_system_file 在本地打开。",
            "path": str(p),
            "file_size": file_size,
        }

    all_lines = text.splitlines(keepends=True)
    total_lines = len(all_lines)
    if read_from_tail:
        selected_lines = list(deque(all_lines, maxlen=max_lines))
    else:
        selected_lines = all_lines[:max_lines]

    content = "".join(selected_lines)
    char_truncated = len(content) > max_chars
    if char_truncated:
        if read_from_tail:
            content = content[-max_chars:]
        else:
            content = content[:max_chars]

    return {
        "ok": True,
        "path": str(p),
        "file_size": file_size,
        "encoding": encoding,
        "content": content,
        "lines_read": len(selected_lines),
        "total_lines": total_lines,
        "truncated": total_lines > max_lines or char_truncated,
        "char_truncated": char_truncated,
        "read_from_tail": bool(read_from_tail),
    }


def open_system_file_sync(path: str, method: str = "default") -> dict:
    """使用系统默认程序打开文件，或在资源管理器中定位。

    安全策略：default 不直接打开可执行/脚本类文件，避免“打开文件”变成“执行程序”。
    这类文件请使用 method=explorer 定位后由用户手动决定是否运行。
    """
    p = _normalize_path(path)
    method = (method or "default").strip().lower()

    if method not in {"default", "explorer"}:
        return {"ok": False, "error": f"不支持的打开方式: {method}", "path": str(p)}
    if not str(p):
        return {"ok": False, "error": "path 为空", "path": path}
    if not p.exists():
        return {"ok": False, "error": f"文件不存在: {p}", "path": str(p)}

    try:
        if method == "explorer":
            if p.is_dir():
                subprocess.Popen(["explorer.exe", str(p)])
            else:
                subprocess.Popen(["explorer.exe", f"/select,{str(p)}"])
            return {"ok": True, "msg": f"已在资源管理器中定位: {p}", "path": str(p), "method": method}

        if p.suffix.lower() in DANGEROUS_OPEN_EXTS:
            return {
                "ok": False,
                "error": f"为安全起见，拒绝直接打开可执行/脚本文件: {p.suffix}。请使用 method=explorer 定位后手动打开。",
                "path": str(p),
                "method": method,
            }

        os.startfile(str(p))
        return {"ok": True, "msg": f"已调用系统默认程序打开: {p}", "path": str(p), "method": method}
    except Exception as e:
        return {"ok": False, "error": f"打开失败: {e}", "path": str(p), "method": method}
