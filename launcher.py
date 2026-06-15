"""
桌面自动化助手 - 一键启动/关闭启动器
=====================================
- start   : 启动 GUI
- stop    : 关闭 GUI
- status  : 查看状态
- restart : 重启 GUI

用法:
    python launcher.py start
    python launcher.py stop
    python launcher.py status
    python launcher.py restart
"""
import sys
import os
import time
import subprocess
from pathlib import Path

# Windows GBK 兼容: 强制 stdout 用 UTF-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# EXE 名称 (跟 PyInstaller 打包配置一致)
EXE_NAME = "桌面自动化助手.exe"
EXE_DIR = Path(__file__).parent / "dist"
EXE_PATH = EXE_DIR / EXE_NAME


def _find_pid() -> list:
    """查找正在运行的 EXE 进程"""
    pids = []
    try:
        # 用 tasklist 找 EXE 进程
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {EXE_NAME}", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, encoding="gbk", errors="ignore"
        )
        for line in result.stdout.strip().split("\n"):
            line = line.strip().strip('"')
            if not line or "INFO:" in line:
                continue
            parts = line.split('","')
            if len(parts) >= 2:
                try:
                    pids.append(int(parts[1]))
                except ValueError:
                    pass
    except Exception as e:
        print(f"[WARN] 查询进程失败: {e}")
    return pids


def status() -> int:
    """查看状态: 返回 0 = 未运行, 1 = 正在运行"""
    pids = _find_pid()
    if pids:
        print(f"✅ 正在运行 (PID: {', '.join(str(p) for p in pids)})")
        return 1
    else:
        print("⏸️  未运行")
        return 0


def start(background: bool = True) -> bool:
    """启动 GUI"""
    if not EXE_PATH.exists():
        print(f"❌ EXE 不存在: {EXE_PATH}")
        print(f"   请先打包: python -m PyInstaller --clean build.spec")
        return False

    pids = _find_pid()
    if pids:
        print(f"⚠️  已在运行 (PID: {', '.join(str(p) for p in pids)})")
        return True

    print(f"🚀 启动: {EXE_PATH}")
    if background:
        # 后台启动,不阻塞当前进程
        subprocess.Popen(
            [str(EXE_PATH)],
            cwd=str(EXE_DIR),
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        )
    else:
        # 前台启动
        subprocess.run([str(EXE_PATH)], cwd=str(EXE_DIR))

    # 等待并验证
    time.sleep(2)
    pids = _find_pid()
    if pids:
        print(f"✅ 启动成功 (PID: {', '.join(str(p) for p in pids)})")
        return True
    else:
        print("❌ 启动失败 (进程未在运行)")
        return False


def stop(force: bool = False) -> bool:
    """关闭 GUI"""
    pids = _find_pid()
    if not pids:
        print("⏸️  未运行,无需关闭")
        return True

    print(f"🛑 关闭进程 (PID: {', '.join(str(p) for p in pids)})")
    for pid in pids:
        try:
            # 先优雅关闭
            if not force:
                subprocess.run(
                    ["taskkill", "/PID", str(pid)],
                    capture_output=True, timeout=5
                )
            else:
                # 强制关闭
                subprocess.run(
                    ["taskkill", "/F", "/PID", str(pid)],
                    capture_output=True, timeout=5
                )
        except Exception as e:
            print(f"  [WARN] 关闭 PID={pid} 失败: {e}")

    # 等待并验证
    time.sleep(1)
    pids = _find_pid()
    if not pids:
        print("✅ 关闭成功")
        return True
    else:
        # 还在,可能需要强制
        if not force:
            print(f"⚠️  部分进程未关闭,尝试强制结束 (剩余 PID: {pids})")
            return stop(force=True)
        else:
            print(f"❌ 关闭失败 (剩余 PID: {pids})")
            return False


def restart() -> bool:
    """重启 GUI"""
    print("🔄 重启...")
    if not stop():
        return False
    time.sleep(1)
    return start()


def install_shortcut() -> bool:
    """在桌面创建快捷方式 (点击弹出菜单对话框)"""
    try:
        import win32com.client  # noqa: F401
        from pathlib import Path as _P

        # 查找 pythonw.exe 路径
        py_dir = _P(sys.executable).parent
        pyw = py_dir / "pythonw.exe"
        if not pyw.exists():
            # 开发模式,可能不在 venv 里
            pyw = py_dir / "python.exe"

        menu_script = (_P(__file__).parent / "launcher_menu.py").absolute()
        icon = _P(__file__).parent / "app_icon.ico"
        desktop = _P.home() / "Desktop"

        shell = win32com.client.Dispatch("WScript.Shell")

        # 1. 桌面助手 快捷方式 (弹出菜单对话框)
        menu_path = desktop / "桌面助手.lnk"
        sc = shell.CreateShortCut(str(menu_path))
        sc.TargetPath = str(pyw)
        sc.Arguments = f'"{menu_script}"'
        sc.WorkingDirectory = str(menu_script.parent)
        sc.IconLocation = str(icon) if icon.exists() else ""
        sc.Description = "桌面自动化助手 (启动/停止)"
        sc.WindowStyle = 7  # 最小化启动 (后台)
        sc.save()
        print(f"✅ 菜单快捷方式: {menu_path}")

        return True
    except Exception as e:
        print(f"❌ 创建失败: {e}")
        return False


def uninstall_shortcut() -> bool:
    """删除桌面的桌面助手快捷方式"""
    desktop = Path.home() / "Desktop"
    removed = 0
    for name in ("桌面助手.lnk", "桌面助手-启动.lnk", "桌面助手-关闭.lnk", "桌面助手-状态.lnk"):
        p = desktop / name
        if p.exists():
            try:
                p.unlink()
                print(f"🗑️  已删除: {p}")
                removed += 1
            except Exception as e:
                print(f"⚠️  删除失败 {p}: {e}")
    if removed == 0:
        print("未找到桌面快捷方式")
    return True


def show_help() -> None:
    """显示帮助"""
    print(__doc__)
    print("快捷命令:")
    print(f"  python {Path(__file__).name} start         # 启动 GUI")
    print(f"  python {Path(__file__).name} stop          # 关闭 GUI")
    print(f"  python {Path(__file__).name} status        # 查看状态")
    print(f"  python {Path(__file__).name} restart       # 重启 GUI")
    print(f"  python {Path(__file__).name} force-stop    # 强制关闭")
    print(f"  python {Path(__file__).name} install       # 创建桌面快捷方式")
    print(f"  python {Path(__file__).name} uninstall     # 删除桌面快捷方式")


def main() -> int:
    if len(sys.argv) < 2:
        show_help()
        return 0

    cmd = sys.argv[1].lower()
    if cmd in ("start", "启动", "s"):
        return 0 if start() else 1
    elif cmd in ("stop", "关闭", "k", "kill"):
        return 0 if stop() else 1
    elif cmd in ("force-stop", "force_kill", "强制关闭"):
        return 0 if stop(force=True) else 1
    elif cmd in ("status", "状态", "st"):
        return status()
    elif cmd in ("restart", "重启", "r"):
        return 0 if restart() else 1
    elif cmd in ("install", "安装"):
        return 0 if install_shortcut() else 1
    elif cmd in ("uninstall", "卸载"):
        return 0 if uninstall_shortcut() else 1
    elif cmd in ("help", "--help", "-h", "帮助"):
        show_help()
        return 0
    else:
        print(f"❌ 未知命令: {cmd}")
        show_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
