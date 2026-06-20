"""统一的数据目录解析。

任何模块需要读写运行时数据，都应从这里导入 USER_DATA_DIR，
避免各自硬编码 Path.home() / "桌面自动化助手"，也避免从 desktop_auto 导入造成循环依赖。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

APP_DATA_DIR_NAME = "桌面自动化助手"
MIGRATION_PENDING_FILE = ".migration_pending.json"
DEFAULT_USER_DATA_DIR = Path.home() / APP_DATA_DIR_NAME

if getattr(sys, "frozen", False):
    RUNTIME_DIR = Path(sys.executable).parent
else:
    RUNTIME_DIR = Path(__file__).parent


def _has_pending_migration(path: Path) -> bool:
    """目标目录存在 pending 标记时，允许启动阶段先识别为迁移目标。"""
    try:
        return (path / MIGRATION_PENDING_FILE).exists()
    except Exception:
        return False


def _is_pointer_only_dir(path: Path) -> bool:
    """目标目录只有指针/迁移日志时，说明只是占位，不能视为迁移完成。"""
    try:
        if not path.exists() or not path.is_dir():
            return False
        entries = {p.name for p in path.iterdir()}
        if "data_dir.json" not in entries:
            return False
        allowed_placeholder_files = {"data_dir.json", ".moved_to", "migrate_error.log", "migrate_tool.bat", MIGRATION_PENDING_FILE}
        return entries.issubset(allowed_placeholder_files)
    except Exception:
        return False


def _read_text_compat(path: Path) -> str:
    """兼容旧 BAT 写出的 ANSI/mbcs 指针文件。"""
    for enc in ("utf-8-sig", "utf-8", "mbcs", "gbk", "cp936"):
        try:
            return path.read_text(encoding=enc)
        except Exception:
            pass
    return path.read_text(errors="replace")


def resolve_user_data_dir() -> Path:
    """读取迁移后的数据目录；不存在配置时回到默认目录。"""
    candidates = [
        DEFAULT_USER_DATA_DIR / "data_dir.json",
        RUNTIME_DIR / "data_dir.json",  # 兼容旧测试/打包位置
    ]
    for cfg_path in candidates:
        try:
            if cfg_path.exists():
                data = json.loads(_read_text_compat(cfg_path))
                raw = (data.get("path") or "").strip()
                if raw:
                    target = Path(raw).expanduser().resolve()
                    if _has_pending_migration(target) or not _is_pointer_only_dir(target):
                        return target
        except Exception:
            pass

    try:
        marker = DEFAULT_USER_DATA_DIR / ".moved_to"
        if marker.exists():
            raw = _read_text_compat(marker).strip()
            if raw:
                target = Path(raw).expanduser().resolve()
                if _has_pending_migration(target) or not _is_pointer_only_dir(target):
                    return target
    except Exception:
        pass

    return DEFAULT_USER_DATA_DIR


def normalize_data_dir_target(selected: Path | str) -> Path:
    """用户选择父目录时，自动落到 <父目录>/桌面自动化助手。"""
    p = Path(selected).expanduser().resolve()
    if p.name != APP_DATA_DIR_NAME:
        p = (p / APP_DATA_DIR_NAME).resolve()
    return p


def write_data_dir_pointer(target: Path | str) -> None:
    """写入默认目录和目标目录的迁移指针。"""
    target_path = normalize_data_dir_target(target)
    DEFAULT_USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    target_path.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"path": str(target_path)}, ensure_ascii=False, indent=2)
    (DEFAULT_USER_DATA_DIR / "data_dir.json").write_text(payload, encoding="utf-8")
    (DEFAULT_USER_DATA_DIR / ".moved_to").write_text(str(target_path), encoding="utf-8")
    (target_path / "data_dir.json").write_text(payload, encoding="utf-8")


USER_DATA_DIR = resolve_user_data_dir()
try:
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass
