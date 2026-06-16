"""
开机启动管理 - Windows 注册表方式
================================

通过 HKCU\Software\Microsoft\Windows\CurrentVersion\Run 读写启动项。
无需管理员权限,推荐位置。

使用:
    from autostart import is_autostart_enabled, enable_autostart, disable_autostart
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional


# 注册表项名 (在 HKCU\Software\Microsoft\Windows\CurrentVersion\Run 下)
APP_NAME = "DesktopAutoAssistant"
APP_DISPLAY = "桌面自动化助手"


def _get_exe_path() -> Optional[str]:
    """获取 EXE 路径(打包后用 sys.executable,开发模式用最近一次打包的 EXE)"""
    if getattr(sys, "frozen", False):
        return sys.executable
    # 开发模式:查找 dist 下最新的 EXE
    dist = Path(__file__).parent / "dist"
    if not dist.exists():
        return None
    exes = sorted(dist.glob("*.exe"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not exes:
        return None
    return str(exes[0])


def _get_run_command() -> Optional[str]:
    """构造注册表中要写入的命令行

    打包后开机自启时,默认 --background (启动后最小化到托盘)
    """
    exe = _get_exe_path()
    if not exe:
        return None
    return f'"{exe}" --background'


def is_autostart_enabled() -> bool:
    """检查是否已启用开机启动"""
    if sys.platform != "win32":
        return False
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_READ,
        ) as key:
            try:
                value, _ = winreg.QueryValueEx(key, APP_NAME)
                return bool(value)
            except FileNotFoundError:
                return False
    except Exception:
        return False


def enable_autostart() -> tuple[bool, str]:
    """
    启用开机启动

    Returns:
        (success, message)
    """
    if sys.platform != "win32":
        return False, "❌ 当前平台不是 Windows"

    cmd = _get_run_command()
    if not cmd:
        return False, "❌ 找不到 EXE 文件,请先打包"

    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE,
        ) as key:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
        return True, f"✅ 已启用开机启动\n启动命令: {cmd}"
    except Exception as e:
        return False, f"❌ 写入注册表失败: {e}"


def disable_autostart() -> tuple[bool, str]:
    """
    禁用开机启动

    Returns:
        (success, message)
    """
    if sys.platform != "win32":
        return False, "❌ 当前平台不是 Windows"

    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE,
        ) as key:
            try:
                winreg.DeleteValue(key, APP_NAME)
                return True, "✅ 已禁用开机启动"
            except FileNotFoundError:
                return True, "ℹ️ 开机启动本来就是关闭的"
    except Exception as e:
        return False, f"❌ 写入注册表失败: {e}"


def get_autostart_command() -> Optional[str]:
    """获取当前注册表中的启动命令(用于显示)"""
    if sys.platform != "win32":
        return None
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_READ,
        ) as key:
            try:
                value, _ = winreg.QueryValueEx(key, APP_NAME)
                return str(value) if value else None
            except FileNotFoundError:
                return None
    except Exception:
        return None


if __name__ == "__main__":
    # 简单测试
    print("EXE path:", _get_exe_path())
    print("Run command:", _get_run_command())
    print("Currently enabled:", is_autostart_enabled())
    print("Current command:", get_autostart_command())
