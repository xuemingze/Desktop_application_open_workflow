"""
代码改动前自动备份 + 一键回档
================================

工作流:
- 备份 (默认备份所有项目源码): python backup.py
- 备份指定文件:                python backup.py --files desktop_auto.py tools_tab.py
- 列出所有备份:                python backup.py --list
- 一键回档到最新备份:          python backup.py --rollback
- 回档到指定备份:              python backup.py --rollback snapshot_20260616_xxx
- 与当前文件对比差异:          python backup.py --diff snapshot_20260616_xxx
- 清理旧备份 (保留最近 N 个):  python backup.py --clean 10
- 强制删除所有备份:            python backup.py --clean-all

设计原则:
- 自动扫描所有 .py / .json / .spec / .md 源码文件
- 备份目录: backups/snapshot_YYYYMMDD_HHMMSS/
- 备份名带简短描述: snapshot_YYYYMMDD_HHMMSS_<desc>/
- 每次回档前自动再备份一次当前状态 (防止回档后回不来)
"""
from __future__ import annotations

import os
import sys
import shutil
import time
import difflib
import argparse
from pathlib import Path
from typing import Optional

# Windows GBK 兼容: 强制 UTF-8 输出
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).parent
BACKUP_DIR = ROOT / "backups"

# 项目源文件扩展名
SOURCE_EXTS = {".py", ".json", ".spec", ".md", ".yml", ".yaml", ".toml", ".txt", ".ini", ".cfg"}
# 排除目录
EXCLUDE_DIRS = {"backups", "build", "dist", "__pycache__", ".venv", "venv", ".git", "samples"}
# 排除的文件
EXCLUDE_FILES = {"app_icon.ico", "app_icon_256_v2.png", "app_icon_512_v2.png"}


def _scan_project_files(extra_excludes: Optional[set[str]] = None) -> list[Path]:
    """扫描项目源文件 (排除 EXCLUDE_DIRS / EXCLUDE_FILES / extra)"""
    excludes = EXCLUDE_FILES | (extra_excludes or set())
    files: list[Path] = []
    for p in ROOT.iterdir():
        if p.is_file():
            if p.suffix.lower() in SOURCE_EXTS and p.name not in excludes:
                files.append(p)
        elif p.is_dir() and p.name not in EXCLUDE_DIRS and not p.name.startswith("."):
            for sub in p.rglob("*"):
                if sub.is_file() and sub.suffix.lower() in SOURCE_EXTS:
                    if not any(part in EXCLUDE_DIRS for part in sub.relative_to(ROOT).parts):
                        if sub.name not in excludes:
                            files.append(sub)
    return sorted(files)


def _next_snapshot_name(desc: str = "") -> Path:
    """生成下一个快照名: snapshot_YYYYMMDD_HHMMSS[_desc]"""
    ts = time.strftime("%Y%m%d_%H%M%S")
    # 描述清洗: 只保留字母数字下划线中划线, 限长
    if desc:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in desc)[:40]
        name = f"snapshot_{ts}_{safe}"
    else:
        name = f"snapshot_{ts}"
    return BACKUP_DIR / name


def make_backup(files: Optional[list[str]] = None, desc: str = "") -> Path:
    """给文件做带时间戳的备份

    Args:
        files: 指定要备份的文件名列表 (None = 自动扫描所有项目源文件)
        desc:  备份描述 (会拼到目录名后)

    Returns:
        备份目录路径
    """
    BACKUP_DIR.mkdir(exist_ok=True)

    if files:
        targets = []
        for f in files:
            p = ROOT / f
            if not p.exists():
                print(f"  ⚠️  跳过不存在的文件: {f}")
                continue
            targets.append(p)
    else:
        targets = _scan_project_files()

    if not targets:
        print("❌ 没有可备份的文件")
        return None

    snapshot = _next_snapshot_name(desc)
    # 防重名: 同一秒内递增
    counter = 1
    while snapshot.exists():
        snapshot = BACKUP_DIR / f"{snapshot.name}_{counter}"
        counter += 1
    snapshot.mkdir(parents=True)

    copied = 0
    for src in targets:
        rel = src.relative_to(ROOT)
        dst = snapshot / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied += 1

    size_kb = sum(f.stat().st_size for f in snapshot.rglob("*") if f.is_file()) / 1024
    print(f"[备份] ✅ {snapshot.name}/  ({copied} 个文件, {size_kb:.1f} KB)")
    return snapshot


def list_backups(verbose: bool = False):
    """列出所有备份"""
    if not BACKUP_DIR.exists():
        print("无备份")
        return
    subs = sorted([p for p in BACKUP_DIR.iterdir() if p.is_dir()])
    if not subs:
        print("无备份")
        return
    print(f"共 {len(subs)} 个备份:\n")
    for sub in subs:
        files = list(sub.rglob("*"))
        file_count = sum(1 for f in files if f.is_file())
        size = sum(f.stat().st_size for f in files if f.is_file())
        marker = " 🟢最新" if sub == subs[-1] else ""
        print(f"  {sub.name}  ({file_count} 文件, {size/1024:.1f} KB){marker}")
        if verbose:
            for f in sorted(files):
                if f.is_file():
                    rel = f.relative_to(sub)
                    print(f"      - {rel}")


def _resolve_snapshot(name: str) -> Optional[Path]:
    """解析快照名, 支持短名匹配"""
    if not BACKUP_DIR.exists():
        return None
    if name == "latest" or name == "last":
        subs = sorted([p for p in BACKUP_DIR.iterdir() if p.is_dir()])
        return subs[-1] if subs else None
    # 完整名
    target = BACKUP_DIR / name
    if target.exists():
        return target
    # 短名匹配 (后缀匹配)
    matches = [p for p in BACKUP_DIR.iterdir() if p.is_dir() and p.name.endswith(name)]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print(f"⚠️  短名 '{name}' 匹配到多个备份, 请用完整名:")
        for m in matches:
            print(f"   {m.name}")
        return None
    return None


def rollback(snapshot_name: str = "latest", auto_backup: bool = True) -> bool:
    """回档到指定快照

    Args:
        snapshot_name: "latest" / 完整名 / 短名后缀
        auto_backup:   回档前是否先备份当前状态
    """
    snapshot = _resolve_snapshot(snapshot_name)
    if snapshot is None:
        print(f"❌ 找不到备份: {snapshot_name}")
        print("可用备份:")
        list_backups()
        return False

    if auto_backup:
        print("🔒 回档前先备份当前状态...")
        make_backup(desc=f"before_rollback_{snapshot.name}")

    print(f"⏪ 从 {snapshot.name} 恢复...")
    restored = 0
    for src in snapshot.rglob("*"):
        if src.is_file():
            rel = src.relative_to(snapshot)
            dst = ROOT / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            restored += 1
    print(f"✅ 回档完成: {restored} 个文件已恢复")
    return True


def show_diff(snapshot_name: str = "latest"):
    """显示当前文件与指定快照的差异"""
    snapshot = _resolve_snapshot(snapshot_name)
    if snapshot is None:
        print(f"❌ 找不到备份: {snapshot_name}")
        return

    print(f"🔍 当前 vs {snapshot.name}:\n")
    has_diff = False
    for snap_file in sorted(snapshot.rglob("*")):
        if not snap_file.is_file():
            continue
        rel = snap_file.relative_to(snapshot)
        cur_file = ROOT / rel
        if not cur_file.exists():
            print(f"  ➕ 仅快照有: {rel}")
            has_diff = True
            continue
        snap_text = snap_file.read_text("utf-8", errors="replace")
        cur_text = cur_file.read_text("utf-8", errors="replace")
        if snap_text == cur_text:
            continue
        has_diff = True
        print(f"  📝 {rel}")
        # 显示 diff
        diff = list(difflib.unified_diff(
            snap_text.splitlines(keepends=True),
            cur_text.splitlines(keepends=True),
            fromfile=f"{snapshot.name}/{rel}",
            tofile=f"current/{rel}",
            n=2,
        ))
        for line in diff[:50]:  # 限长
            print(f"    {line.rstrip()}")
        if len(diff) > 50:
            print(f"    ... (还有 {len(diff)-50} 行)")
        print()
    if not has_diff:
        print("  ✅ 无差异")


def clean_old(keep: int = 10):
    """清理旧备份, 保留最近 N 个"""
    if not BACKUP_DIR.exists():
        print("无备份")
        return
    subs = sorted([p for p in BACKUP_DIR.iterdir() if p.is_dir()])
    if len(subs) <= keep:
        print(f"备份数 {len(subs)} <= {keep}, 无需清理")
        return
    to_remove = subs[:-keep]
    for sub in to_remove:
        shutil.rmtree(sub)
        print(f"  🗑️  删除: {sub.name}")
    print(f"✅ 清理完成, 保留最新 {keep} 个备份")


def clean_all():
    """强制删除所有备份"""
    if not BACKUP_DIR.exists():
        print("无备份")
        return
    n = sum(1 for _ in BACKUP_DIR.iterdir())
    confirm = input(f"⚠️  确认删除全部 {n} 个备份? (y/N): ").strip().lower()
    if confirm != "y":
        print("已取消")
        return
    shutil.rmtree(BACKUP_DIR)
    print(f"🗑️  已删除 {n} 个备份目录")


def main():
    parser = argparse.ArgumentParser(
        description="代码改动前自动备份 + 一键回档",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python backup.py                                    # 备份所有项目源文件
  python backup.py -d "fix: 修复托盘"                  # 备份 + 描述
  python backup.py --files desktop_auto.py tools_tab.py  # 备份指定文件
  python backup.py --list                             # 列出所有备份
  python backup.py --list -v                          # 详细列出
  python backup.py --diff                             # 当前 vs 最新备份
  python backup.py --diff snapshot_20260616_xxx       # 当前 vs 指定备份
  python backup.py --rollback                         # 一键回档到最新备份
  python backup.py --rollback snapshot_20260616_xxx   # 回档到指定备份
  python backup.py --clean 10                         # 清理旧备份, 保留最近10个
        """,
    )
    parser.add_argument("-d", "--desc", default="", help="备份描述 (拼到目录名)")
    parser.add_argument("--files", nargs="+", help="指定要备份的文件名")
    parser.add_argument("--list", "-l", action="store_true", help="列出所有备份")
    parser.add_argument("-v", "--verbose", action="store_true", help="详细输出")
    parser.add_argument("--diff", metavar="SNAPSHOT", nargs="?", const="latest", help="显示与指定快照的差异 (默认: 最新)")
    parser.add_argument("--rollback", metavar="SNAPSHOT", nargs="?", const="latest", help="回档到指定快照 (默认: 最新)")
    parser.add_argument("--no-auto-backup", action="store_true", help="回档前不再自动备份")
    parser.add_argument("--clean", type=int, metavar="N", nargs="?", const=5, help="清理旧备份, 保留最近N个 (默认5)")
    parser.add_argument("--clean-all", action="store_true", help="强制删除所有备份")

    args = parser.parse_args()

    if args.list:
        list_backups(verbose=args.verbose)
    elif args.diff is not None:
        show_diff(args.diff)
    elif args.rollback is not None:
        rollback(args.rollback, auto_backup=not args.no_auto_backup)
    elif args.clean is not None:
        clean_old(args.clean)
    elif args.clean_all:
        clean_all()
    else:
        make_backup(files=args.files, desc=args.desc)


if __name__ == "__main__":
    main()
