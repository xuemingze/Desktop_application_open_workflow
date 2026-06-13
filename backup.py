"""
代码改动前自动备份
- 备份: python backup.py
- 列出: python backup.py --list
- 恢复: python backup.py --restore <filename.bak>
- 全部删除: python backup.py --clean
"""
import os
import sys
import shutil
import time
from pathlib import Path

BACKUP_DIR = Path(__file__).parent / "backups"
CORE_FILES = ["desktop_auto.py", "workflow_panel.py", "mcp_embedded.py", "image_match.py"]


def make_backup() -> Path:
    """给所有核心文件做带时间戳的备份"""
    BACKUP_DIR.mkdir(exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    backup_subdir = BACKUP_DIR / f"snapshot_{ts}"
    backup_subdir.mkdir(parents=True, exist_ok=True)
    for fname in CORE_FILES:
        src = Path(__file__).parent / fname
        if src.exists():
            shutil.copy2(src, backup_subdir / fname)
    print(f"[备份] 已创建: {backup_subdir.name}/")
    for f in CORE_FILES:
        if (backup_subdir / f).exists():
            print(f"  - {f}")
    return backup_subdir


def list_backups():
    if not BACKUP_DIR.exists():
        print("无备份")
        return
    subs = sorted(BACKUP_DIR.iterdir())
    if not subs:
        print("无备份")
        return
    print(f"共 {len(subs)} 个备份:\n")
    for sub in subs:
        if sub.is_dir():
            size = sum(f.stat().st_size for f in sub.iterdir())
            print(f"  {sub.name}  ({size/1024:.1f} KB)")


def restore(snapshot_name: str):
    target = BACKUP_DIR / snapshot_name
    if not target.exists():
        print(f"备份不存在: {snapshot_name}")
        list_backups()
        return
    for fname in CORE_FILES:
        src = target / fname
        dst = Path(__file__).parent / fname
        if src.exists():
            shutil.copy2(src, dst)
            print(f"  [恢复] {fname}")
    print(f"[完成] 从 {snapshot_name} 恢复")


def clean_all():
    if not BACKUP_DIR.exists():
        print("无备份,无需清理")
        return
    n = sum(1 for _ in BACKUP_DIR.iterdir())
    shutil.rmtree(BACKUP_DIR)
    print(f"[清理] 已删除 {n} 个备份目录")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "--list" or cmd == "-l":
            list_backups()
        elif cmd == "--clean" or cmd == "-c":
            clean_all()
        elif cmd == "--restore" or cmd == "-r":
            if len(sys.argv) > 2:
                restore(sys.argv[2])
            else:
                print("用法: python backup.py --restore <snapshot_name>")
                list_backups()
        else:
            print(f"未知命令: {cmd}")
    else:
        make_backup()
