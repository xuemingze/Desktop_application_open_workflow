"""
PyInstaller EXE 兼容性补丁 - jsonschema_specifications

问题:
  mcp -> jsonschema -> jsonschema_specifications 启动时会遍历
  sys._MEIPASS/jsonschema_specifications/schemas。
  某些 PyInstaller 单文件包在全新机器上会缺这个实体目录,导致 FileNotFoundError。

策略:
  1. 不提前 import jsonschema_specifications,避免触发它的 __init__。
  2. 在 frozen 环境里,优先确保 sys._MEIPASS/jsonschema_specifications/schemas 目录存在。
  3. 如果目录缺失,尝试从已打包资源/源码 site-packages 复制。

必须在 import mcp / import jsonschema 之前调用。
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def _safe_reconfigure_stdio() -> None:
    if sys.platform != "win32":
        return
    for stream_name in ("stdout", "stderr"):
        try:
            stream = getattr(sys, stream_name, None)
            if stream and hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def _copytree_merge(src: Path, dst: Path) -> bool:
    if not src.exists() or not src.is_dir():
        return False
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.rglob("*"):
        rel = item.relative_to(src)
        target = dst / rel
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                shutil.copy2(item, target)
    return True


def ensure_jsonschema_specifications_schemas() -> bool:
    """确保 frozen 临时目录里存在 jsonschema_specifications/schemas。"""
    meipass = getattr(sys, "_MEIPASS", None)
    if not meipass:
        return True

    target = Path(meipass) / "jsonschema_specifications" / "schemas"
    if target.exists() and any(target.iterdir()):
        return True

    candidates = []

    # 1. 单文件解包目录旁边可能已有包目录
    candidates.append(Path(meipass) / "jsonschema_specifications" / "schemas")

    # 2. 源码/开发环境常见路径
    here = Path(__file__).resolve().parent
    candidates.append(here / ".venv" / "Lib" / "site-packages" / "jsonschema_specifications" / "schemas")
    candidates.append(here.parent / ".venv" / "Lib" / "site-packages" / "jsonschema_specifications" / "schemas")

    # 3. sys.path 中可见的 site-packages
    for p in map(Path, sys.path):
        candidates.append(p / "jsonschema_specifications" / "schemas")

    for src in candidates:
        try:
            src = src.resolve()
        except Exception:
            continue
        if src == target:
            continue
        try:
            if _copytree_merge(src, target):
                return target.exists() and any(target.iterdir())
        except Exception:
            continue

    # 最后至少创建空目录,让错误从 FileNotFoundError 变成更明确的数据缺失
    try:
        target.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return target.exists() and any(target.iterdir())


def patch_jsonschema_specifications() -> bool:
    """入口函数: 兼容旧调用名。"""
    _safe_reconfigure_stdio()
    return ensure_jsonschema_specifications_schemas()


if __name__ == "__main__":
    ok = patch_jsonschema_specifications()
    print(f"jsonschema_specifications schemas: {'OK' if ok else 'MISSING'}")
