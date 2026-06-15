"""
桌面自动化助手 (PySide6)

功能:
1. 扫描桌面所有 .lnk 快捷方式
2. 选中后:既支持「直接启动」(稳定),也支持「图像识别点击」(通用)
3. 图像识别支持多模板(普通/悬停/选中),Win10 高 DPI / 多屏兼容
4. 程序启动后用 pywinauto 等窗口就绪,不再硬 sleep
5. 自带截图框选工具,可以直接把桌面图标保存为模板
6. 操作日志实时显示在 UI 中

依赖:
    pip install PySide6 pyautogui pillow pyperclip pywinauto opencv-python pywin32
"""

from __future__ import annotations

# 提前 import GUI 必需辅助模块,让 PyInstaller 能扫描到它们的依赖。
# 注意: 不要在 GUI 普通启动时提前 import mcp_embedded。
# mcp_embedded 会导入 mcp/jsonschema,在全新虚拟机/单 EXE 环境里一旦数据文件缺失会导致 GUI 启动直接崩溃。
# MCP 只在 --mcp 模式或工具页实际需要时懒加载。
import backup  # noqa: F401
import image_match  # noqa: F401
import workflow_panel  # noqa: F401
import search_panel  # noqa: F401
import tools_tab  # noqa: F401

import os
import sys
import time
import ctypes
import logging
import json
import subprocess
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

_SINGLE_INSTANCE_MEMORY = None

# 确保脚本所在目录在 sys.path 首位 (便携 Python 可能不加)
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

# 0. 环境自检: 缺包时用当前 python 自动装,避免 ModuleNotFoundError
# 打包后 (PyInstaller) 不需要这个检查,直接跳过
def _ensure_dependencies() -> None:
    # 打包后冻结环境跳过: 没有 pip / 不能安装依赖
    if getattr(sys, 'frozen', False):
        return
    import importlib
    missing = []
    for mod, pkg in [
        ("pyautogui", "pyautogui"),
        ("pyperclip", "pyperclip"),
        ("win32com", "pywin32"),
        ("PIL", "Pillow"),
        ("PySide6", "PySide6"),
        ("psutil", "psutil"),
    ]:
        try:
            importlib.import_module(mod)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"[env] 缺依赖,自动安装: {missing}", flush=True)
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", *missing],
            )
        except Exception as e:
            print(f"[env] 自动安装失败: {e}\n请手动: pip install {' '.join(missing)}", flush=True)
            sys.exit(1)

_ensure_dependencies()
# ============================================================
# CLI 参数路由网关 (必须在任何 GUI 初始化之前执行)
# ============================================================
def _cli_router() -> None:
    """
    命令行参数路由网关
    
    处理 --install-shortcut / --remove-shortcut 等无头任务,
    执行完毕后直接 sys.exit(), 不加载 GUI。
    """
    args = [a.lower() for a in sys.argv[1:]]
    
    if not args:
        return
    
    if any(a in args for a in ('--install-shortcut', '--install')):
        _do_install_shortcut()
        sys.exit(0)
    
    if any(a in args for a in ('--remove-shortcut', '--uninstall')):
        _do_remove_shortcut()
        sys.exit(0)
    
    if '--mcp' in args:
        return
    
    # --silent-task 是桌面快捷方式入口: 不在这里退出,交给 main() 的单实例逻辑处理。
    # 如果没有实例在运行,正常打开 GUI;如果已有实例,切换到已有窗口后退出。

def _do_install_shortcut() -> None:
    """在桌面创建快捷方式, 目标指向当前 EXE 并携带 --silent-task 参数"""
    try:
        import win32com.client
        desktop = Path.home() / "Desktop"
        exe_path = sys.executable
        icon_path = Path(__file__).parent / "app_icon.ico"
        
        shell = win32com.client.Dispatch("WScript.Shell")
        
        shortcut_path = desktop / "桌面助手.lnk"
        sc = shell.CreateShortCut(str(shortcut_path))
        sc.TargetPath = str(exe_path)
        sc.Arguments = "--silent-task"
        sc.WorkingDirectory = str(Path(exe_path).parent)
        if icon_path.exists():
            sc.IconLocation = str(icon_path)
        sc.Description = "桌面自动化助手"
        sc.WindowStyle = 1
        sc.save()
        print(f"[CLI] 桌面快捷方式已创建: {shortcut_path}")
    except Exception as e:
        print(f"[CLI] 创建快捷方式失败: {e}")
def _do_remove_shortcut() -> None:
    """删除桌面快捷方式"""
    desktop = Path.home() / "Desktop"
    shortcut_path = desktop / "桌面助手.lnk"
    if shortcut_path.exists():
        shortcut_path.unlink()
        print(f"[CLI] 已删除: {shortcut_path}")
    else:
        print(f"[CLI] 快捷方式不存在: {shortcut_path}")
def _do_silent_task(args: list[str]) -> None:
    """静默执行任务模式 (预留)。当前作为桌面快捷方式启动入口。"""
    print("[CLI] 静默任务模式启动")
    print("[CLI] 静默任务完成")


def _forward_to_running_instance(argv: list[str]) -> bool:
    """已有实例运行时,尽量把主窗口切到前台。"""
    try:
        import win32con
        import win32gui

        title_keyword = "桌面自动化助手"
        matches = []

        def enum_handler(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return
            title = win32gui.GetWindowText(hwnd)
            if title_keyword in title:
                matches.append(hwnd)

        win32gui.EnumWindows(enum_handler, None)
        if not matches:
            print("[单实例] 未找到已运行窗口")
            return False

        hwnd = matches[0]
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        except Exception:
            pass
        try:
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            pass
        print(f"[单实例] 已切换到窗口: {win32gui.GetWindowText(hwnd)}")
        return True
    except Exception as e:
        print(f"[单实例] 转发/激活失败: {e}")
        return False


# ============================================================
# 单实例锁 (QSharedMemory)
# ============================================================
def _try_acquire_single_instance() -> bool:
    """
    尝试获取单实例锁。
    返回 True 表示当前进程是主实例, 可以继续加载 GUI。
    返回 False 表示已有主实例在运行, 当前进程应退出。
    """
    try:
        from PySide6.QtCore import QSharedMemory, QSystemSemaphore
        
        semaphore = QSystemSemaphore("desktop_auto_semaphore", 1)
        semaphore.acquire()
        
        shared_mem = QSharedMemory("desktop_auto_single_instance")
        if shared_mem.attach():
            semaphore.release()
            return False
        
        if not shared_mem.create(1):
            # 极少数情况下 create 失败但并非已有实例,保守允许启动,避免锁异常导致打不开。
            semaphore.release()
            return True
        # 必须挂到模块全局变量上,否则 QSharedMemory 对象被回收后锁会释放。
        global _SINGLE_INSTANCE_MEMORY
        _SINGLE_INSTANCE_MEMORY = shared_mem
        semaphore.release()
        return True
    except Exception:
        return True
_cli_router()
import pyautogui
import pyperclip
import win32com.client
from PIL import Image
from PySide6.QtCore import Qt, QRect, QPoint, QThread, Signal
from PySide6.QtGui import QPixmap, QImage, QPainter, QPen, QColor, QGuiApplication
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QListWidgetItem, QLabel, QTextEdit,
    QFileDialog, QMessageBox, QStatusBar, QGroupBox, QRadioButton,
    QButtonGroup, QCheckBox, QSpinBox, QLineEdit, QComboBox, QInputDialog
)

# ---------------------------------------------------------------------------
# 1. Windows DPI / 多屏 初始化(必须在 QApplication 之前)
# ---------------------------------------------------------------------------
def enable_high_dpi() -> None:
    """Win10+ 高 DPI 感知,坐标不再偏移"""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor V2
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

enable_high_dpi()

# pyautogui 全局安全配置
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.3

# ---------------------------------------------------------------------------
# 2. 日志
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("desktop_auto")


# ---------------------------------------------------------------------------
# 3. 数据模型
# ---------------------------------------------------------------------------
@dataclass
class ShortcutInfo:
    name: str
    target: str
    lnk_path: str
    work_dir: str = ""
    icon_samples: list[str] = field(default_factory=list)  # 多模板路径


# ---------------------------------------------------------------------------
# 4. 桌面快捷方式扫描
# ---------------------------------------------------------------------------
def get_real_desktop() -> Path:
    """通过注册表取真实桌面路径(支持 OneDrive 重定向 / 多用户)"""
    try:
        from winreg import HKEY_CURRENT_USER, OpenKey, QueryValueEx
        with OpenKey(
            HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
        ) as k:
            return Path(QueryValueEx(k, "Desktop")[0])
    except Exception:
        return Path(os.environ["USERPROFILE"]) / "Desktop"


def scan_desktop_shortcuts() -> list[ShortcutInfo]:
    """扫描桌面所有 .lnk 快捷方式,容错处理每个文件
    + 追加自定义应用 (custom_apps.json)"""
    desktop = get_real_desktop()
    if not desktop.exists():
        log.warning(f"桌面路径不存在: {desktop}")
        return []

    try:
        shell = win32com.client.Dispatch("WScript.Shell")
    except Exception as e:
        log.error(f"WScript.Shell 初始化失败: {e}")
        return []

    out: list[ShortcutInfo] = []
    for lnk in desktop.glob("*.lnk"):
        try:
            sc = shell.CreateShortCut(str(lnk))
            info = ShortcutInfo(
                name=lnk.stem,
                target=sc.TargetPath or "",
                lnk_path=str(lnk),
                work_dir=sc.WorkingDirectory or "",
            )
            out.append(info)
        except Exception as e:
            log.warning(f"跳过 {lnk.name}: {e}")

    # 追加用户自定义应用
    for custom in load_custom_apps():
        out.append(ShortcutInfo(
            name=custom.get("name", Path(custom["target"]).stem),
            target=custom.get("target", ""),
            lnk_path="",  # 自定义不是快捷方式
            work_dir=custom.get("work_dir", ""),
        ))
    return out


# 运行时目录(支持 EXE 打包:用 EXE 所在目录而不是临时解压目录)
import sys as _sys
if getattr(_sys, 'frozen', False):
    RUNTIME_DIR = Path(_sys.executable).parent
else:
    RUNTIME_DIR = Path(__file__).parent


# 自定义应用管理
CUSTOM_APPS_FILE = RUNTIME_DIR / "custom_apps.json"


def load_custom_apps() -> list[dict]:
    """加载 custom_apps.json"""
    if not CUSTOM_APPS_FILE.exists():
        return []
    try:
        return json.loads(CUSTOM_APPS_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning(f"custom_apps.json 读取失败: {e}")
        return []


def save_custom_apps(apps: list[dict]) -> None:
    """保存到 custom_apps.json"""
    CUSTOM_APPS_FILE.write_text(
        json.dumps(apps, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def add_custom_app(name: str, target: str, work_dir: str = "") -> dict:
    """添加一个自定义应用(同名/同 target 视为重复,返回已有)"""
    if not target or not Path(target).exists():
        raise FileNotFoundError(f"目标不存在: {target}")
    apps = load_custom_apps()
    # 去重: 同 target (不区分大小写) 不重复
    for a in apps:
        if a["target"].lower() == target.lower():
            return a
    app = {
        "name": name.strip() or Path(target).stem,
        "target": target,
        "work_dir": work_dir or str(Path(target).parent),
    }
    apps.append(app)
    save_custom_apps(apps)
    return app


def remove_custom_app(target: str) -> bool:
    """删除指定 target 的自定义应用"""
    apps = load_custom_apps()
    new_apps = [a for a in apps if a["target"].lower() != target.lower()]
    if len(new_apps) < len(apps):
        save_custom_apps(new_apps)
        return True
    return False


# ---------------------------------------------------------------------------
# 5. 启动程序(后台线程跑,UI 不卡)
# ---------------------------------------------------------------------------
class LaunchWorker(QThread):
    """执行启动 + 等待窗口 + 键鼠交互的工作线程"""
    log_signal = Signal(str)
    finished_signal = Signal(bool, str)

    def __init__(self, info: ShortcutInfo, mode: str, do_notepad: bool, extra_args: str = "", coord: dict = None):
        super().__init__()
        self.info = info
        self.mode = mode          # "direct" | "shell" | "image"
        self.do_notepad = do_notepad
        self.extra_args = self._parse_args(extra_args)
        self.coord = coord or {}  # 坐标点击参数: {"x", "y", "click_type"}
        self._cancel = False

    @staticmethod
    def _parse_args(text: str) -> list[str]:
        """按空格分隔,但保留引号里的整体。简单实现: shlex.split"""
        import shlex
        try:
            return shlex.split(text) if text.strip() else []
        except Exception:
            return text.split()

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        try:
            if self.mode == "direct":
                self._launch_direct()
            elif self.mode == "shell":
                self._launch_shell()
            elif self.mode == "image":
                self._launch_by_image()
            elif self.mode == "desktop":
                self._launch_desktop_click()
            else:
                raise ValueError(f"未知模式: {self.mode}")
            if self.do_notepad and not self._cancel:
                self._interact_notepad()
            self.finished_signal.emit(True, "执行完成")
        except Exception as e:
            log.exception("执行失败")
            self.finished_signal.emit(False, str(e))

    # ---- 5.1 直接启动 (Popen 方式) ----
    def _launch_direct(self) -> None:
        info = self.info
        if not info.target or not Path(info.target).exists():
            raise FileNotFoundError(f"目标程序不存在: {info.target}")
        self.log_signal.emit(f"🚀 直接启动 (Popen): {info.target}")
        # Electron / 资源敏感型应用必须传 cwd,否则找不到资源崩
        # 优先用快捷方式里的 WorkingDirectory,退化用 target 所在目录
        cwd = info.work_dir if info.work_dir and Path(info.work_dir).is_dir() else str(Path(info.target).parent)
        if cwd != info.work_dir:
            self.log_signal.emit(f"   📂 使用工作目录: {cwd}")
        # CREATE_NO_WINDOW=0x08000000 避免控制台程序弹黑窗;GUI 客户端会正常弹窗口
        # 不要用 DETACHED_PROCESS(0x00000008),会启动但不显示 GUI
        subprocess.Popen(
            [info.target],
            cwd=cwd,
            creationflags=0x08000000,
        )
        self._wait_window_ready(info.name, timeout=20)

    # ---- 5.1b Shell 启动 (走 cmd /c start,完全脱离 Python 进程上下文) ----
    def _launch_shell(self) -> None:
        info = self.info
        if not info.target or not Path(info.target).exists():
            raise FileNotFoundError(f"目标程序不存在: {info.target}")
        self.log_signal.emit(f"🚀 Shell 启动: {info.target}")
        cwd = info.work_dir if info.work_dir and Path(info.work_dir).is_dir() else str(Path(info.target).parent)
        self.log_signal.emit(f"   📂 工作目录: {cwd}")
        # 每个参数独立加引号
        args_parts = ['"{}"'.format(info.target)]
        for a in self.extra_args:
            args_parts.append('"{}"'.format(a) if " " in a else a)
        args_str = " ".join(args_parts)
        if self.extra_args:
            self.log_signal.emit(f"   🎛️ 启动参数: {' '.join(self.extra_args)}")
        cmd_str = 'cd /d "{}" && {}'.format(cwd, args_str)
        self.log_signal.emit(f"   🔧 执行: cmd /c {cmd_str}")
        # CREATE_NEW_CONSOLE = 0x00000010,给 GUI 应用一个独立控制台
        subprocess.Popen(
            ["cmd", "/c", cmd_str],
            creationflags=0x00000010,
        )
        self._wait_window_ready(info.name, timeout=20)

    # ---- 5.2 图像识别启动 ----
    def _launch_by_image(self) -> None:
        info = self.info
        # 优先使用用户输入的坐标 (从 MainWindow 传入)
        x = self.coord.get("x", 0)
        y = self.coord.get("y", 0)
        click_type = self.coord.get("click_type", "left_double")
        samples = [s for s in info.icon_samples if Path(s).exists()]

        # 如果有坐标,优先按坐标点击
        if x > 0 or y > 0:
            self.log_signal.emit(f"🎯 坐标点击模式: ({x}, {y}) 类型={click_type}")
            import pyautogui as pa
            self.log_signal.emit(f"   按 Win+D 显示桌面...")
            pa.hotkey('win', 'd')
            time.sleep(0.5)
            if click_type == "left_double":
                pa.doubleClick(x, y)
            elif click_type == "right_single":
                pa.click(x, y, button="right")
            else:
                pa.click(x, y)
            self.log_signal.emit(f"   ✅ 已点击")
            self._wait_window_ready(info.name, timeout=20)
            return

        # 退化: 有模板就报模板 (已不一定能匹配了)
        if not samples:
            raise FileNotFoundError("请先设置坐标(X>0 或 Y>0)或加载图标模板")
        self.log_signal.emit(f"⚠️ 未设置坐标,使用模板匹配 (可能失败)")
        # 后面的逻辑保留作为兑底
        center = None
        for sample in samples:
            try:
                box = pyautogui.locateOnScreen(sample, confidence=0.7, grayscale=False)
                if box:
                    center = pyautogui.center(box)
                    self.log_signal.emit(f"✅ 命中模板: {Path(sample).name} @ {center}")
                    break
            except Exception as e:
                self.log_signal.emit(f"⚠️ 模板 {Path(sample).name} 识别失败: {e}")
        if not center:
            raise RuntimeError("屏幕上找不到该图标,请设置坐标 (X>0 或 Y>0)")
        pyautogui.click(center)
        self._wait_window_ready(info.name, timeout=20)

    # ---- 5.2b 拟人化: 双击桌面快捷方式 (3 段降级) ----
    def _launch_desktop_click(self) -> None:
        info = self.info
        self.log_signal.emit(f"🖱️ 鼠标双击桌面图标: {info.name}")
        
        # B. 先用截图模板匹配(最精准)
        try:
            self._launch_desktop_click_by_image(info)
            self._wait_window_ready(info.name, timeout=20)
            return
        except Exception as e:
            self.log_signal.emit(f"   ⚠️ 模板匹配失败: {e}")
        
        # A. 走 IShellFolder API 拿真实图标位置
        logical_idx = None
        try:
            logical_idx = self._launch_desktop_click_via_shell(info)  # A 段内部已执行双击
            self._wait_window_ready(info.name, timeout=20)
            return
        except Exception as e:
            self.log_signal.emit(f"   ⚠️ IShellFolder 方式失败: {e}")
        # C. 网格猜测 (如果 A 拿到了 logical_idx,就能猜)
        try:
            if logical_idx is None:
                # 走 IShellFolder 拿 idx (不调 ListView,只取名字+idx)
                logical_idx = self._fetch_logical_idx_only(info)
            if logical_idx is not None:
                self._click_at_logical_idx(logical_idx)
            else:
                raise RuntimeError("连 logical_idx 都没拿到")
            self._wait_window_ready(info.name, timeout=20)
            return
        except Exception as e:
            self.log_signal.emit(f"   ⚠️ 网格猜测失败: {e}")
        # 最后兜底: 通过 explorer.exe 启动(绕过 runtime 环境限制)
        try:
            self._launch_via_explorer(info)
            self._wait_window_ready(info.name, timeout=20)
            return
        except Exception as e:
            self.log_signal.emit(f"   ⚠️ explorer 兜底失败: {e}")
        raise RuntimeError("3 段降级全部失败")

    def _launch_desktop_click_via_shell(self, info):
        """A 段: 走 IShellFolder + ListView 拿真实坐标"""
        # 最小化所有窗口,露出干净桌面
        self.log_signal.emit(f"   🪟 最小化所有窗口露出桌面...")
        import pyautogui
        import time
        pyautogui.hotkey('win', 'd')  # Win+D 显示桌面
        time.sleep(0.3)

        # 1) 枚举桌面项目,按 name 拿到 PIDL 的"逻辑位置"
        from win32com.shell import shell as win32shell

        self.log_signal.emit(f"   📂 枚举桌面 IShellFolder...")
        try:
            desktop_folder = win32shell.SHGetDesktopFolder()
        except Exception as e:
            raise RuntimeError(f"拿不到 desktop folder: {e}")

        # flag = 0x70 = FOLDERS(0x20) | NONFOLDERS(0x40) | CHECKING_FOR_CHILDREN(0x10)
        # 0x30 漏掉了 .lnk 以外的快捷方式,必须用 0x70
        enum = desktop_folder.EnumObjects(0, 0x70)
        # pywin32 的 Next 返回 [[pidl_bytes]],pidl 在 [0][0]
        items = []
        i = 0
        while True:
            wrapped = enum.Next(1)
            if not wrapped:
                break
            pidl = wrapped[0][0]
            # GetDisplayNameOf 需要 wrapped[0] 整体
            name_obj = desktop_folder.GetDisplayNameOf(wrapped[0], 0x1)
            if isinstance(name_obj, list):
                name_obj = name_obj[0]
            items.append((str(name_obj), i))
            i += 1

        self.log_signal.emit(f"   共 {len(items)} 个桌面项目")

        # 找匹配项
        target_logical_idx = -1
        for name, idx in items:
            n = name.lower().strip().rstrip('.lnk')
            want = info.name.lower().strip().rstrip('.lnk')
            if n == want or want in n or n in want:
                target_logical_idx = idx
                self.log_signal.emit(f"   🎯 匹配 {idx}: {name}")
                break

        if target_logical_idx < 0:
            raise RuntimeError(f"桌面 IShellFolder 找不到 {info.name}")

        # 2) 找 ListView,按逻辑 idx 拿位置 (每次都重新枚举,不缓存)
        self._desktop_listview = None
        import ctypes
        import ctypes.wintypes
        user32 = ctypes.windll.user32
        GetClassNameW = user32.GetClassNameW
        GetWindowRect = user32.GetWindowRect
        FindWindowW = user32.FindWindowW
        SendMessage = user32.SendMessageW
        EnumChildWindows = user32.EnumChildWindows

        # 用可变对象实现闭包变量修改(避免 global 问题)
        defvw_container = {'hwnd': None}

        def cb_child(hwnd, l):
            cls = ctypes.create_unicode_buffer(256)
            GetClassNameW(hwnd, cls, 256)
            if cls.value == "SysListView32":
                defvw_container['hwnd'] = hwnd
                return False
            return True

        EnumChildProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
        cb_fn = EnumChildProc(cb_child)

        self.log_signal.emit(f"   🔍 查找 Progman...")
        progman = FindWindowW("Progman", None)
        if progman:
            self.log_signal.emit(f"   ✅ 找到 Progman,枚举子窗口...")
            EnumChildWindows(progman, cb_fn, 0)
        else:
            self.log_signal.emit(f"   ⚠️ Progman 未找到")
        
        if not defvw_container['hwnd']:
            self.log_signal.emit(f"   🔍 Progman 下没找到 SysListView32,枚举 WorkerW...")

            def cb_top(hwnd, l):
                cls = ctypes.create_unicode_buffer(256)
                GetClassNameW(hwnd, cls, 256)
                if cls.value == "WorkerW":
                    EnumChildWindows(hwnd, cb_fn, 0)
                return not bool(defvw_container['hwnd'])

            user32.EnumWindows(EnumChildProc(cb_top), 0)
        
        defvw = defvw_container['hwnd']
        self.log_signal.emit(f"   📋 ListView 查找结果: hwnd={defvw}")
        if not defvw:
            # ListView 找不到,但 logical_idx 仍然有效 -> 交给调用者走网格兜底
            self.log_signal.emit(f"   ⚠️ 桌面 ListView 找不到,退到网格估算 (idx={target_logical_idx})")
            raise RuntimeError("ListView 找不到,logical_idx 仍可用")
        else:
            self.log_signal.emit(f"   ✅ 找到 ListView hwnd={defvw}, idx={target_logical_idx}")

        # 3) 纯后台点击: 给 SysListView32 发送 WM_LBUTTONDBLCLK 消息
        # LVM_GETITEMPOSITION 经常返回 0,0,用网格估算图标在 ListView 内的客户区坐标
        LVM_GETITEMPOSITION = 0x1010
        WM_LBUTTONDOWN = 0x0201
        WM_LBUTTONUP = 0x0202
        WM_LBUTTONDBLCLK = 0x0203
        MK_LBUTTON = 0x0001

        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        pt = POINT()
        SendMessage(defvw, LVM_GETITEMPOSITION, target_logical_idx, ctypes.byref(pt))

        if pt.x == 0 and pt.y == 0:
            # 兜底: 用桌面图标常见网格 (Win10 默认: 75x95 网格)
            self.log_signal.emit(f"   ⚠️ LVM_GETITEMPOSITION 返回 0,0,改用网格估算")
            col = target_logical_idx % 8
            row = target_logical_idx // 8
            pt.x = 30 + col * 95 + 16  # 图标中心
            pt.y = 30 + row * 100 + 16
            self.log_signal.emit(f"   📍 A段网格估算(客户区坐标): ({pt.x}, {pt.y}) (idx={target_logical_idx})")
        else:
            pt.x += 16  # 图标中心
            pt.y += 16
            self.log_signal.emit(f"   📍 A段真实坐标(客户区坐标): ({pt.x}, {pt.y})")

        # 计算 lParam: 低位 x,高位 y
        lparam = (pt.y << 16) | (pt.x & 0xFFFF)
        
        # 纯后台点击: 发送消息到 SysListView32 窗口
        self.log_signal.emit(f"   🖱️ 后台双击 (SendMessage) hwnd={hex(defvw)}")
        # 发送双击消息序列 (模拟真实双击)
        SendMessage(defvw, WM_LBUTTONDOWN, MK_LBUTTON, lparam)
        time.sleep(0.05)
        SendMessage(defvw, WM_LBUTTONUP, 0, lparam)
        time.sleep(0.05)
        SendMessage(defvw, WM_LBUTTONDBLCLK, MK_LBUTTON, lparam)
        time.sleep(0.05)
        SendMessage(defvw, WM_LBUTTONUP, 0, lparam)
        
        self.log_signal.emit(f"   ✅ 后台双击完成")
        return target_logical_idx

    def _launch_via_explorer(self, info) -> None:
        """备选: 通过 explorer.exe 间接打开快捷方式,绕过 runtime 环境限制"""
        import subprocess
        self.log_signal.emit(f"   🚀 通过 explorer.exe 启动: {info.name}")
        try:
            # 走 shell=True 调用 explorer.exe 去打开快捷方式
            cmd = f'explorer.exe "{info.lnk_path}"'
            subprocess.Popen(cmd, shell=True)
            self.log_signal.emit(f"   ✅ explorer 调用完成")
        except Exception as e:
            self.log_signal.emit(f"   ⚠️ explorer 启动失败: {e}")
            raise

    def _launch_desktop_click_by_image(self, info) -> None:
        """B 段: 从 samples/ 找 info.name 开头的 PNG 作为模板,locateOnScreen 后双击"""
        self.log_signal.emit(f"   📸 找桌面截图模板...")
        sample_dir = Path("samples")
        candidates = list(sample_dir.glob(f"{info.name}_*.png")) if sample_dir.exists() else []
        if not candidates:
            raise FileNotFoundError(
                f"请先用「截图框选」工具对桌面 {info.name} 图标截一张图,保存到 samples/ 目录"
            )
        
        # 最小化所有窗口,露出干净桌面
        self.log_signal.emit(f"   🪟 最小化所有窗口露出桌面...")
        import pyautogui
        pyautogui.hotkey('win', 'd')  # Win+D 显示桌面
        import time
        time.sleep(0.5)
        
        self.log_signal.emit(f"   找到 {len(candidates)} 个模板,开始匹配...")
        for c in candidates:
            try:
                self.log_signal.emit(f"   🔍 匹配模板: {c.name}")
                # 先截全屏保存调试
                screen = pyautogui.screenshot()
                debug_path = Path("samples") / "_debug_screen.png"
                screen.save(str(debug_path))
                self.log_signal.emit(f"   📸 全屏截图已保存: {debug_path}")
                
                box = pyautogui.locateOnScreen(str(c), confidence=0.6)  # 降低阈值
                if box:
                    center = pyautogui.center(box)
                    self.log_signal.emit(f"   ✅ 找到: {c.name} @ {center}")
                    time.sleep(0.2)
                    pyautogui.doubleClick(center)
                    self.log_signal.emit(f"   ✅ 双击完成")
                    return
                else:
                    self.log_signal.emit(f"   ❌ 未匹配: {c.name}")
            except Exception as e:
                self.log_signal.emit(f"   ⚠️ 匹配异常 {c.name}: {e}")
                continue
        raise RuntimeError("截图匹配也没找到")

    def _fetch_logical_idx_only(self, info) -> Optional[int]:
        """只走 IShellFolder 枚举,拿到目标在 ListView 中的逻辑 idx,不调 ListView"""
        from win32com.shell import shell as win32shell

        self.log_signal.emit(f"   📂 C 段: 仅枚举 IShellFolder...")
        try:
            desktop_folder = win32shell.SHGetDesktopFolder()
        except Exception as e:
            self.log_signal.emit(f"   ⚠️ 拿不到 desktop folder: {e}")
            return None

        enum = desktop_folder.EnumObjects(0, 0x70)
        i = 0
        while True:
            wrapped = enum.Next(1)
            if not wrapped:
                break
            name_obj = desktop_folder.GetDisplayNameOf(wrapped[0], 0x1)
            if isinstance(name_obj, list):
                name_obj = name_obj[0]
            name = str(name_obj).lower().strip().rstrip('.lnk')
            want = info.name.lower().strip().rstrip('.lnk')
            if name == want or want in name or name in want:
                self.log_signal.emit(f"   🎯 C 段匹配 idx={i}: {name_obj}")
                return i
            i += 1
        return None

    def _click_at_logical_idx(self, logical_idx: int) -> None:
        """拿到 logical_idx 后,用网格估算屏幕坐标并双击"""
        import ctypes
        import ctypes.wintypes
        user32 = ctypes.windll.user32
        GetClassNameW = user32.GetClassNameW
        GetWindowRect = user32.GetWindowRect
        FindWindowW = user32.FindWindowW
        SendMessage = user32.SendMessageW
        EnumChildWindows = user32.EnumChildWindows

        # 找 ListView (用可变对象修复闭包变量问题)
        defvw_container = {'hwnd': None}
        EnumChildProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)

        def cb_child(hwnd, l):
            cls = ctypes.create_unicode_buffer(256)
            GetClassNameW(hwnd, cls, 256)
            if cls.value == "SysListView32":
                defvw_container['hwnd'] = hwnd
                return False
            return True

        cb_fn = EnumChildProc(cb_child)
        progman = FindWindowW("Progman", None)
        if progman:
            EnumChildWindows(progman, cb_fn, 0)
        if not defvw_container['hwnd']:
            def cb_top(hwnd, l):
                cls = ctypes.create_unicode_buffer(256)
                GetClassNameW(hwnd, cls, 256)
                if cls.value == "WorkerW":
                    EnumChildWindows(hwnd, cb_fn, 0)
                return not bool(defvw_container['hwnd'])
            user32.EnumWindows(EnumChildProc(cb_top), 0)
        
        defvw = defvw_container['hwnd']

        # 拿 ListView 屏幕坐标
        rect = ctypes.wintypes.RECT()
        if defvw:
            GetWindowRect(defvw, ctypes.byref(rect))
        else:
            # 完全没 ListView,用主屏
            user32.GetWindowRect(FindWindowW("Shell_TrayWnd", None), ctypes.byref(rect))
            rect.left = 0
            rect.top = 0
            rect.right = 1920
            rect.bottom = 1080

        # 网格估算 (Win10 默认: 75x95, 8 列) - 客户区坐标
        COLS = 8
        COL_W = 95
        ROW_H = 100
        col = logical_idx % COLS
        row = logical_idx // COLS
        pt_x = 20 + col * COL_W + 16  # 客户区坐标(图标中心)
        pt_y = 20 + row * ROW_H + 16
        self.log_signal.emit(f"   📍 网格估算 (idx={logical_idx}, col={col}, row={row})")
        
        if defvw:
            # 纯后台点击: 给 SysListView32 发送 WM_LBUTTONDBLCLK 消息
            WM_LBUTTONDOWN = 0x0201
            WM_LBUTTONUP = 0x0202
            WM_LBUTTONDBLCLK = 0x0203
            MK_LBUTTON = 0x0001
            lparam = (pt_y << 16) | (pt_x & 0xFFFF)
            
            self.log_signal.emit(f"   🖱️ C段后台双击 (SendMessage) hwnd={hex(defvw)}")
            SendMessage(defvw, WM_LBUTTONDOWN, MK_LBUTTON, lparam)
            time.sleep(0.05)
            SendMessage(defvw, WM_LBUTTONUP, 0, lparam)
            time.sleep(0.05)
            SendMessage(defvw, WM_LBUTTONDBLCLK, MK_LBUTTON, lparam)
            time.sleep(0.05)
            SendMessage(defvw, WM_LBUTTONUP, 0, lparam)
            self.log_signal.emit(f"   ✅ 后台双击完成")
        else:
            # 退化: 鼠标移动点击
            click_x = rect.left + pt_x
            click_y = rect.top + pt_y
            self.log_signal.emit(f"   🖱️ 鼠标双击坐标: ({click_x}, {click_y})")
            time.sleep(0.3)
            pyautogui.moveTo(click_x, click_y, duration=0.2)
            time.sleep(0.2)
            pyautogui.doubleClick()
            self.log_signal.emit(f"   ✅ 双击完成")

    # ---- 5.3 等窗口就绪 (三段式: psutil 找进程 > pywinauto 找窗口 > 退化等待) ----
    def _wait_window_ready(self, hint: str, timeout: float) -> None:
        self.log_signal.emit(f"⏳ 等待窗口就绪 (hint={hint})...")

        # 解析快捷方式目标路径 (如果是 .lnk)
        target_exe = hint.lower() + ".exe"
        if self.info.lnk_path and str(self.info.lnk_path).lower().endswith('.lnk'):
            try:
                import win32com.client
                shell = win32com.client.Dispatch('WScript.Shell')
                shortcut = shell.CreateShortCut(str(self.info.lnk_path))
                if shortcut.TargetPath:
                    target_exe = Path(shortcut.TargetPath).name.lower()
                    self.log_signal.emit(f"   📝 解析快捷方式目标: {target_exe}")
            except Exception as e:
                self.log_signal.emit(f"   ⚠️ 快捷方式解析失败: {e}")
        elif self.info.target:
            target_exe = Path(self.info.target).name.lower()
        
        self.log_signal.emit(f"   🔍 查找进程名: {target_exe}")

        # 1) 首选: 用 psutil 按可执行文件名找进程,且需要「持续存活」才算
        deadline = time.time() + timeout
        STABLE_SECONDS = 1.5  # 进程必须持续存在 1.5s 才算真就绪
        try:
            import psutil
            first_seen = None
            while time.time() < deadline:
                alive = [
                    (p.info["pid"], p.info["name"])
                    for p in psutil.process_iter(["pid", "name"])
                    if (p.info["name"] or "").lower() == target_exe
                ]
                if alive:
                    if first_seen is None:
                        first_seen = time.time()
                    elif time.time() - first_seen >= STABLE_SECONDS:
                        pid, name = alive[0]
                        self.log_signal.emit(
                            f"✅ 进程已运行 {STABLE_SECONDS}s+: {name} (PID={pid})"
                        )
                        return
                else:
                    # 中途消失了 -> 秒退
                    if first_seen is not None:
                        self.log_signal.emit(
                            f"❌ 进程 {target_exe} 启动后秒退!请手动双击该 exe 验证能否起起。"
                        )
                        return
                    first_seen = None
                time.sleep(0.3)
            # 超时
            if first_seen is not None:
                self.log_signal.emit(
                    f"⚠️ 进程 {target_exe} 存在但未达稳定阈值,可能仍在加载中..."
                )
            else:
                self.log_signal.emit(
                    f"❌ {timeout}s 内未发现进程 {target_exe} 运行。\n"
                    f"   可能原因: exe 自身崩溃 / 缺 DLL / 杀毒拦截 / 需管理员权限。\n"
                    f"   建议: 手动双击该快捷方式测试是否能起来。"
                )
        except Exception as e:
            self.log_signal.emit(f"⚠️ psutil 检查失败: {e}")

        # 2) 备选: pywinauto 找窗口 (app 实际启动但窗口可能被延后)
        self.log_signal.emit("🔎 未按进程名命中,退化用 pywinauto 找窗口标题...")
        try:
            from pywinauto import Application, timings
            timings.wait_until_passes(
                min(timeout, 5), 0.5,
                lambda: Application(backend="win32").connect(
                    title_re=f".*{hint}.*", timeout=0.5
                ),
            )
            self.log_signal.emit("✅ 窗口标题已就绪")
            return
        except Exception:
            pass

        # 3) 最后退化: 固定等一下,让用户感知“程序启动了”
        self.log_signal.emit("⚠️ 未命中进程/窗口,固定等待 2s")
        time.sleep(2)

    # ---- 5.4 记事本交互(中文走剪贴板) ----
    def _interact_notepad(self) -> None:
        self.log_signal.emit("📝 开始键鼠交互(记事本)")
        time.sleep(1)
        pyperclip.copy(
            "这是通过 Python 自动模拟键鼠输入的测试文本！\n"
            "支持中文、换行、快捷键 Ctrl+S / Ctrl+V"
        )
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.5)
        pyautogui.hotkey("ctrl", "s")
        time.sleep(0.8)
        pyautogui.typewrite("auto_test.txt", interval=0.05)
        pyautogui.press("enter")
        self.log_signal.emit("✅ 交互完成")


# ---------------------------------------------------------------------------
# 6. 全屏截图 + 框选(手动做模板)
# ---------------------------------------------------------------------------
class SnippingWindow(QWidget):
    """全屏覆盖窗口,鼠标拖拽框选一块区域并保存为 PNG。

    关键: 统一使用“逻辑坐标” (DPI-缩放后),避免在 125%/150% 屏幕上坐标偏移。
    截图时拿真实物理像素,但画到 widget 上时按 devicePixelRatio 缩放。
    保存时使用选中区在物理像素图中的子区域(坐标*ratio)。
    """

    captured = Signal(QRect)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setCursor(Qt.CrossCursor)

        screen = QGuiApplication.primaryScreen()
        # 物理像素图 (高 DPI 下分辨率会高)
        self._full_pixmap: QPixmap = screen.grabWindow(0)
        self._dpr: float = screen.devicePixelRatio()
        # widget 覆盖整个屏幕(逻辑坐标)
        self.setGeometry(screen.geometry())

        self._start: Optional[QPoint] = None
        self._end: Optional[QPoint] = None

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        # 画原图,但拉伸到 widget 逻辑尺寸 (画出来跟屏幕一样)
        p.drawPixmap(self.rect(), self._full_pixmap)
        # 画一个半透明黑色遮罩
        p.fillRect(self.rect(), QColor(0, 0, 0, 80))
        if self._start and self._end:
            rect = QRect(self._start, self._end).normalized()
            # 逻辑坐标下的选区 → 物理像素子区域
            phys_rect = QRect(
                int(rect.left() * self._dpr),
                int(rect.top() * self._dpr),
                int(rect.width() * self._dpr),
                int(rect.height() * self._dpr),
            )
            cropped = self._full_pixmap.copy(phys_rect)
            p.drawPixmap(rect.topLeft(), cropped)
            pen = QPen(QColor(0, 200, 255), 2, Qt.SolidLine)
            p.setPen(pen)
            p.drawRect(rect)

    def mousePressEvent(self, ev) -> None:
        # ev.position() 已经是逻辑坐标,转 QPoint 即可
        self._start = ev.position().toPoint()
        self._end = self._start
        self.update()

    def mouseMoveEvent(self, ev) -> None:
        self._end = ev.position().toPoint()
        self.update()

    def mouseReleaseEvent(self, ev) -> None:
        self._end = ev.position().toPoint()
        rect = QRect(self._start, self._end).normalized()
        # 发射物理像素坐标,让调用者直接用 .copy(rect)
        phys_rect = QRect(
            int(rect.left() * self._dpr),
            int(rect.top() * self._dpr),
            int(rect.width() * self._dpr),
            int(rect.height() * self._dpr),
        )
        self.captured.emit(phys_rect)
        self.close()

    def keyPressEvent(self, ev) -> None:
        if ev.key() == Qt.Key_Escape:
            self.close()


# ---------------------------------------------------------------------------
# 7. 主窗口
# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("桌面自动化助手")
        self.resize(960, 640)

        self.shortcuts: list[ShortcutInfo] = []
        self.worker: Optional[LaunchWorker] = None
        self.state: dict = self._load_state()  # 记忆上次启动的 PID

        # ===== 左侧:快捷方式列表 =====
        self.list_widget = QListWidget(self)
        self.list_widget.setMinimumWidth(260)
        self.list_widget.setUniformItemSizes(True)  # 固定行高,不会压扁
        self.list_widget.setWordWrap(False)
        self.list_widget.setStyleSheet(
            "QListWidget { font-size: 13px; }"
            "QListWidget::item { height: 26px; padding: 2px; }"
        )
        self.list_widget.itemSelectionChanged.connect(self._on_select)

        # ===== 右侧:控制面板 =====
        self.info_label = QLabel("选中一个快捷方式", self)
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("color: #555;")

        # 启动方式 radio (顺序按推荐度: 鼠标双击 > Popen > Shell > 图像)
        self.mode_group = QButtonGroup(self)
        self.radio_direct = QRadioButton("🚀 直接启动 (Popen,最优先,最稳定)", self)
        self.radio_desktop = QRadioButton("🖱️ 鼠标双击桌面图标 (备选)", self)
        self.radio_shellexec = QRadioButton("Shell 启动 (cmd /c,特殊场景)", self)
        self.radio_image = QRadioButton("📸 图像识别点击 (最后兜底)", self)
        self.radio_direct.setChecked(True)
        self.mode_group.addButton(self.radio_desktop, 1)
        self.mode_group.addButton(self.radio_direct, 2)
        self.mode_group.addButton(self.radio_shellexec, 3)
        self.mode_group.addButton(self.radio_image, 4)

        self.chk_notepad = QCheckBox("启动后模拟键鼠交互 (仅记事本生效)", self)

        self.samples_label = QLabel("当前模板: 无", self)
        self.samples_label.setWordWrap(True)

        self.btn_refresh = QPushButton("🔄 刷新桌面", self)
        self.btn_snipping = QPushButton("✂️ 截图框选为模板", self)
        self.btn_load_samples = QPushButton("📂 从文件加载模板", self)
        self.btn_run = QPushButton("▶  执行", self)
        self.btn_run.setStyleSheet("font-weight: bold; padding: 6px; min-height: 24px;")
        self.btn_stop = QPushButton("⏹  停止", self)
        self.btn_stop.setStyleSheet("min-height: 24px;")
        self.btn_stop.setEnabled(False)

        # 启动参数(Electron / Chromium 沙箱绕过)
        self.args_edit = QLineEdit(self)
        self.args_edit.setPlaceholderText("--no-sandbox --disable-gpu --no-stdio-init ...")
        self.args_edit.setClearButtonEnabled(True)

        # ===== 清理残留进程 =====
        self.cleanup_kw = QLineEdit(self)
        self.cleanup_kw.setPlaceholderText("aipy  lobe  mobax  ... (空格分隔多个关键词)")
        self.cleanup_kw.setClearButtonEnabled(True)
        self.btn_cleanup = QPushButton("🧹 清理残留进程", self)
        self.btn_cleanup.setStyleSheet(
            "QPushButton { background:#f59e0b; color:white; font-weight:bold; padding:6px; min-height: 24px; }"
            "QPushButton:hover { background:#d97706; }"
        )

        right = QWidget(self)
        # 右侧选项卡布局: 快速启动 | 工作流
        from PySide6.QtWidgets import QTabWidget
        self.right_tabs = QTabWidget(right)

        # === Tab 1: 快速启动 (原内容) ===
        quick_tab = QWidget()
        rv = QVBoxLayout(quick_tab)
        rv.setContentsMargins(4, 4, 4, 4)
        rv.setSpacing(6)

        rv.addWidget(QLabel("目标信息:"))
        rv.addWidget(self.info_label)
        gb = QGroupBox("启动方式 (4 选 1)", quick_tab)
        gv = QVBoxLayout(gb)
        gv.addWidget(self.radio_desktop)
        gv.addWidget(self.radio_direct)
        gv.addWidget(self.radio_shellexec)
        gv.addWidget(self.radio_image)
        gb.setMinimumHeight(150)
        rv.addWidget(gb)
        rv.addWidget(self.chk_notepad)
        rv.addWidget(QLabel("图标模板 (图像模式需要,其他模式可选):"))
        rv.addWidget(self.samples_label)
        hb = QHBoxLayout()
        hb.addWidget(self.btn_snipping)
        hb.addWidget(self.btn_load_samples)
        rv.addLayout(hb)
        # ===== 坐标点击 (代替图像识别) =====
        coord_group = QGroupBox("🎯 坐标点击 (图像模式可选,免截图)")
        cg_v = QVBoxLayout(coord_group)
        coord_row = QHBoxLayout()
        coord_row.addWidget(QLabel("X:"))
        self.coord_x = QSpinBox()
        self.coord_x.setRange(0, 9999)
        coord_row.addWidget(self.coord_x)
        coord_row.addWidget(QLabel("Y:"))
        self.coord_y = QSpinBox()
        self.coord_y.setRange(0, 9999)
        coord_row.addWidget(self.coord_y)
        coord_row.addWidget(QLabel("点击:"))
        self.coord_click_type = QComboBox()
        self.coord_click_type.addItem("双击 (默认)", "left_double")
        self.coord_click_type.addItem("左键单击", "left_single")
        self.coord_click_type.addItem("右键单击", "right_single")
        coord_row.addWidget(self.coord_click_type)
        coord_row.addStretch()
        cg_v.addLayout(coord_row)
        capture_row = QHBoxLayout()
        self.btn_capture_coord = QPushButton("🎯 捕捉坐标 (Win+D 后 3秒)")
        self.btn_capture_coord.setStyleSheet(
            "QPushButton { background:#0891b2; color:white; padding:6px; font-weight:bold; }"
            "QPushButton:hover { background:#0e7490; }"
            "QPushButton:disabled { background:#9ca3af; }"
        )
        capture_row.addWidget(self.btn_capture_coord)
        self.coord_status = QLabel("")
        self.coord_status.setStyleSheet("color:#666; font-size:11px;")
        capture_row.addWidget(self.coord_status)
        capture_row.addStretch()
        cg_v.addLayout(capture_row)
        rv.addWidget(coord_group)
        rv.addWidget(QLabel("启动参数 (空格分隔,可选):"))
        rv.addWidget(self.args_edit)
        rv.addStretch(1)
        rv.addWidget(self.btn_run)
        rv.addWidget(self.btn_stop)

        # 一键启停区域 (已替换为工作流面板)
        onekey_box = QGroupBox("一键启停 (批量) - 已升级为工作流", quick_tab)
        obv = QVBoxLayout(onekey_box)
        obv.addWidget(QLabel("💡 请使用下方「工作流」面板"))
        obv.addWidget(QLabel("(支持: 启动软件、截图匹配点击、按键、等待、坐标点击)"))
        rv.addWidget(onekey_box)

        # 清理残留
        clean_box = QGroupBox("🧹 清理历史残留 (按进程名关键词)", quick_tab)
        cv = QVBoxLayout(clean_box)
        cv.addWidget(QLabel("关键词:"))
        cv.addWidget(self.cleanup_kw)
        cv.addWidget(self.btn_cleanup)
        clean_box.setMinimumHeight(130)
        rv.addWidget(clean_box)

        # ===== (MCP Server 控制已转移到【工具】标签页) =====

        # === Tab 2: 工作流 ===
        from workflow_panel import WorkflowEditor
        self.workflow_editor = WorkflowEditor(self)
        workflow_tab = QWidget()
        wv = QVBoxLayout(workflow_tab)
        wv.setContentsMargins(0, 0, 0, 0)
        wv.addWidget(self.workflow_editor)

        # === Tab 2: 文件搜索 ===
        try:
            from search_panel import SearchPanel
            self.search_panel = SearchPanel(self)
            self.right_tabs.addTab(self.search_panel, "🔍 文件搜索")
        except Exception as e:
            log.warning(f"文件搜索标签加载失败: {e}")

        # 添加到选项卡
        self.right_tabs.addTab(quick_tab, "🚀 快速启动")
        self.right_tabs.addTab(workflow_tab, "🔄 工作流")
        # === Tab 4: 工具 (MCP server 控制 + 简介) ===
        try:
            from tools_tab import ToolsTab
            self.tools_tab = ToolsTab(self)
            self.right_tabs.addTab(self.tools_tab, "🛠️ 工具")
        except Exception as e:
            log.warning(f"工具标签加载失败: {e}")

        # 设置选项卡
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(self.right_tabs)

        # ===== 底部:日志 =====
        self.log_view = QTextEdit(self)
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet(
            "background:#1e1e1e;color:#dcdcdc;font-family:Consolas,monospace;"
        )

        # ===== 整体布局: 用 QSplitter 干调拖动划分,避免嵌套后 stretch 失效 =====
        from PySide6.QtWidgets import QSplitter, QScrollArea
        # 右侧包到 QScrollArea,防止 widget 重叠
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setWidget(right)
        scroll.setMinimumWidth(560)

        # ===== 左侧: 快捷方式列表 + 重新扫描按钮 =====
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)
        # 头部: 标题 + 重新扫描
        header_row = QHBoxLayout()
        header_row.setContentsMargins(4, 4, 4, 0)
        list_title = QLabel("桌面快捷方式:")
        list_title.setStyleSheet("font-weight: bold;")
        header_row.addWidget(list_title)
        header_row.addStretch()
        # 自定义添加按钮
        self.btn_add_custom = QPushButton("➕", self)
        self.btn_add_custom.setStyleSheet("padding: 2px 8px; min-height: 22px; font-weight: bold; color: #10b981;")
        self.btn_add_custom.setToolTip("添加自定义启动程序")
        header_row.addWidget(self.btn_add_custom)
        # 删除自定义按钮
        self.btn_remove_custom = QPushButton("🗑", self)
        self.btn_remove_custom.setStyleSheet("padding: 2px 8px; min-height: 22px; font-weight: bold; color: #dc2626;")
        self.btn_remove_custom.setToolTip("删除当前选中的自定义程序 (仅删除自定义添加的)")
        header_row.addWidget(self.btn_remove_custom)
        # 重新扫描
        self.btn_refresh.setStyleSheet("padding: 2px 8px; min-height: 22px;")
        self.btn_refresh.setToolTip("重新扫描桌面快捷方式")
        header_row.addWidget(self.btn_refresh)
        left_layout.addLayout(header_row)
        left_layout.addWidget(self.list_widget)

        splitter = QSplitter(Qt.Horizontal, self)
        splitter.addWidget(left_panel)
        splitter.addWidget(scroll)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([500, 820])  # 右侧宽一些

        outer = QWidget(self)
        ov = QVBoxLayout(outer)
        ov.setContentsMargins(6, 6, 6, 6)
        ov.addWidget(splitter, 3)
        ov.addWidget(QLabel("操作日志:"))
        ov.addWidget(self.log_view, 1)
        self.setCentralWidget(outer)

        # 强制最小尺寸防坍缩
        self.list_widget.setMinimumWidth(280)
        self.setMinimumSize(1280, 720)
        self.resize(1400, 860)

        self.setStatusBar(QStatusBar(self))

        # 信号
        self.btn_refresh.clicked.connect(self.refresh_shortcuts)
        self.btn_add_custom.clicked.connect(self._add_custom_app)
        self.btn_remove_custom.clicked.connect(self._remove_custom_app)
        self.btn_snipping.clicked.connect(self.start_snipping)
        self.btn_load_samples.clicked.connect(self.load_samples_from_files)
        self.btn_capture_coord.clicked.connect(self._capture_coord_for_quick)
        self.btn_run.clicked.connect(self.run_action)
        self.btn_stop.clicked.connect(self.stop_action)
        # btn_onekey_start / btn_onekey_stop 已替换为工作流面板
        self.btn_cleanup.clicked.connect(self.cleanup_residuals)
        # MCP server 控制已转移到【工具】标签页

        # 启动时自动扫描
        self.refresh_shortcuts()

    # ---- 7.1 日志桥接 ----
    def _append_log(self, msg: str) -> None:
        self.log_view.append(msg)
        # 自动滚到底
        sb = self.log_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _capture_coord_for_quick(self):
        """快速启动面板的坐标捕捉: Win+D 显示桌面 -> 3秒倒计时 -> 捕捉"""
        import pyautogui as pa
        from PySide6.QtCore import QTimer
        self.btn_capture_coord.setEnabled(False)
        self.coord_status.setText("按 Win+D 显示桌面...")
        # 先 Win+D
        pa.hotkey('win', 'd')
        # 隐藏主窗口
        self.hide()
        # 800ms 后开始倒计时 (等动画完成)
        QTimer.singleShot(800, lambda: self._quick_capture_countdown(3))

    def _quick_capture_countdown(self, n):
        from PySide6.QtCore import QTimer
        if n <= 0:
            import pyautogui as pa
            x, y = pa.position()
            self.coord_x.setValue(x)
            self.coord_y.setValue(y)
            self.coord_status.setText(f"✅ 已捕捉: ({x}, {y})")
            self.btn_capture_coord.setEnabled(True)
            # 恢复窗口并强制转到前台
            self.show()
            self.showNormal()  # 确保不被最小化
            self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
            self.raise_()
            self.activateWindow()
            # 闪动状态栏: 设置高亮样式 1.5 秒后还原
            self.coord_status.setStyleSheet("color:#16a34a; font-weight:bold; font-size:12px; background:#dcfce7; padding:2px 6px;")
            QTimer.singleShot(2000, lambda: self.coord_status.setStyleSheet("color:#666; font-size:11px;"))
            return
        self.coord_status.setText(f"⏱ {n} 秒后捕捉...")
        QTimer.singleShot(1000, lambda: self._quick_capture_countdown(n - 1))

    def _on_worker_log(self, msg: str) -> None:
        self._append_log(msg)

    def _on_worker_done(self, ok: bool, msg: str) -> None:
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self._append_log(("✅ " if ok else "❌ ") + msg)

    # ---- 7.2 列表操作 ----
    # 状态文件:记录「一键启动」开启的 PID,关闭时只关这些
    STATE_FILE = RUNTIME_DIR / "launch_state.json"

    def _load_state(self) -> dict:
        if self.STATE_FILE.exists():
            try:
                return json.loads(self.STATE_FILE.read_text("utf-8"))
            except Exception:
                pass
        return {"pids": [], "names": [], "ts": 0}

    def _save_state(self) -> None:
        try:
            self.STATE_FILE.write_text(
                json.dumps(self.state, ensure_ascii=False, indent=2), "utf-8"
            )
        except Exception as e:
            self._append_log(f"⚠️ 状态保存失败: {e}")

    def refresh_shortcuts(self) -> None:
        self.list_widget.clear()
        self.shortcuts = scan_desktop_shortcuts()
        for sc in self.shortcuts:
            item = QListWidgetItem(f"{sc.name}   →   {sc.target}")
            self.list_widget.addItem(item)
        self._append_log(f"🔍 扫描到 {len(self.shortcuts)} 个快捷方式")
        if self.shortcuts:
            self.list_widget.setCurrentRow(0)
        # 同步到工作流面板
        if hasattr(self, 'workflow_editor'):
            self.workflow_editor.refresh_shortcuts()

    def _current(self) -> Optional[ShortcutInfo]:
        row = self.list_widget.currentRow()
        if 0 <= row < len(self.shortcuts):
            return self.shortcuts[row]
        return None

    def _add_custom_app(self) -> None:
        """弹出对话框添加自定义应用"""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择要添加的应用",
            "C:\\Program Files",
            "可执行文件 (*.exe *.bat *.cmd);;所有文件 (*.*)"
        )
        if not path:
            return
        default_name = Path(path).stem
        name, ok = QInputDialog.getText(self, "应用名称", "应用名称 (留空用文件名):", text=default_name)
        if not ok:
            return
        name = (name or "").strip() or default_name
        try:
            app = add_custom_app(name, path)
            self._append_log(f"✅ 已添加自定义应用: {app['name']} → {app['target']}")
            self.refresh_shortcuts()
        except FileNotFoundError as e:
            QMessageBox.warning(self, "路径不存在", str(e))
        except Exception as e:
            QMessageBox.warning(self, "添加失败", str(e))

    def _remove_custom_app(self) -> None:
        """删除当前选中的自定义应用 (只能删 lnk_path 为空的)"""
        sc = self._current()
        if not sc:
            QMessageBox.information(self, "提示", "请先选中一个应用")
            return
        if sc.lnk_path:  # 是 .lnk 快捷方式,不是自定义
            QMessageBox.information(self, "提示", "只能删除自定义添加的应用 (桌面快捷方式请直接删除 .lnk 文件)")
            return
        if QMessageBox.question(self, "确认删除", f"删除自定义应用「{sc.name}」?") != QMessageBox.Yes:
            return
        if remove_custom_app(sc.target):
            self._append_log(f"🗑 已删除: {sc.name}")
            self.refresh_shortcuts()
        else:
            QMessageBox.warning(self, "删除失败", "未找到该应用")

    def _on_select(self) -> None:
        sc = self._current()
        if not sc:
            return
        self.info_label.setText(
            f"<b>{sc.name}</b><br>"
            f"目标: {sc.target}<br>"
            f"工作目录: {sc.work_dir or '(默认)'}<br>"
            f"快捷方式: {sc.lnk_path}"
        )
        # 加载该条目之前保存过的模板(从文件 meta.json 简化版,这里每次只读文件名约定)
        sample_dir = Path("samples")
        if sample_dir.exists():
            sc.icon_samples = [str(p) for p in sample_dir.glob(f"{sc.name}_*.png")]
        self._refresh_samples_label()

    def _refresh_samples_label(self) -> None:
        sc = self._current()
        if not sc or not sc.icon_samples:
            self.samples_label.setText("当前模板: 无")
        else:
            names = "\n".join(Path(s).name for s in sc.icon_samples)
            self.samples_label.setText(f"当前模板 ({len(sc.icon_samples)}):\n{names}")

    # ---- 7.3 模板管理 ----
    def start_snipping(self) -> None:
        sc = self._current()
        if not sc:
            QMessageBox.warning(self, "提示", "请先在左侧选一个快捷方式")
            return
        # 隐藏主窗口,避免被截进图
        self.hide()
        time.sleep(0.3)
        self.snipping = SnippingWindow()
        self.snipping.captured.connect(lambda r: self._on_snipped(sc, r))
        self.snipping.show()
        self.snipping.raise_()
        self.snipping.activateWindow()

    def _on_snipped(self, sc: ShortcutInfo, rect: QRect) -> None:
        self.show()
        if rect.width() < 4 or rect.height() < 4:
            self._append_log("⚠️ 选区太小,已取消")
            return
        sample_dir = Path("samples")
        sample_dir.mkdir(exist_ok=True)
        # 多模板命名: name_idx_timestamp.png
        idx = len(sc.icon_samples)
        out = sample_dir / f"{sc.name}_{idx}_{int(time.time())}.png"
        # 从全屏 pixmap 截一块
        cropped: QImage = self.snipping._full_pixmap.copy(rect).toImage()
        cropped.save(str(out), "PNG")
        sc.icon_samples.append(str(out))
        self._append_log(f"📸 模板已保存: {out}")
        self._refresh_samples_label()

    def load_samples_from_files(self) -> None:
        sc = self._current()
        if not sc:
            return
        # 确保 samples 目录存在,避免 Win32 对话框在空目录上挂起
        sample_dir = Path("samples").resolve()
        sample_dir.mkdir(parents=True, exist_ok=True)
        initial = str(sample_dir)
        self._append_log(f"📂 打开文件对话框: {initial}")
        # 走 Qt 内置对话框 (DontUseNativeDialog) 避免 Windows 资源管理器在中文/特殊路径下卡死
        from PySide6.QtWidgets import QFileDialog as QD
        files, _ = QD.getOpenFileNames(
            self, "选择模板图片", initial, "PNG 图片 (*.png)",
            options=QD.DontUseNativeDialog,
        )
        if files:
            sc.icon_samples.extend(files)
            self._append_log(f"📂 已加载 {len(files)} 个模板")
        else:
            self._append_log("📂 未选择任何文件")
        self._refresh_samples_label()

    # ---- 7.4 执行 / 停止 ----
    def run_action(self) -> None:
        sc = self._current()
        if not sc:
            QMessageBox.warning(self, "提示", "请先选择一个快捷方式")
            return
        if self.worker and self.worker.isRunning():
            return

        mode = (
            "desktop" if self.radio_desktop.isChecked()
            else "direct" if self.radio_direct.isChecked()
            else "shell" if self.radio_shellexec.isChecked()
            else "image"
        )
        if mode == "image" and not sc.icon_samples:
            QMessageBox.warning(self, "提示", "图像识别模式需要先有模板,请用「截图框选」")
            return

        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.worker = LaunchWorker(
            sc, mode,
            do_notepad=self.chk_notepad.isChecked(),
            extra_args=self.args_edit.text(),
            coord={
                "x": self.coord_x.value(),
                "y": self.coord_y.value(),
                "click_type": self.coord_click_type.currentData()
            },
        )
        # (self.scope_all 已被工作流面板取代)
        self.worker.log_signal.connect(self._on_worker_log)
        self.worker.finished_signal.connect(self._on_worker_done)
        self.worker.start()
        self._append_log(f"▶ 启动任务: {sc.name}  (mode={mode})")

    def stop_action(self) -> None:
        # 先终止 worker 线程
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.quit()
            self.worker.wait(2000)
            self._append_log("⏹ 已请求停止 worker")
        
        # 再杀掉已启动的目标进程
        sc = self._current()
        if sc:
            try:
                # 解析快捷方式找目标进程名
                target_exe = None
                if sc.lnk_path and str(sc.lnk_path).lower().endswith('.lnk'):
                    import win32com.client
                    shell = win32com.client.Dispatch('WScript.Shell')
                    shortcut = shell.CreateShortCut(str(sc.lnk_path))
                    if shortcut.TargetPath:
                        target_exe = Path(shortcut.TargetPath).name.lower()
                elif sc.target:
                    target_exe = Path(sc.target).name.lower()
                else:
                    target_exe = sc.name.lower() + ".exe"
                
                import psutil
                killed = []
                for p in psutil.process_iter(['pid', 'name']):
                    if (p.info['name'] or '').lower() == target_exe:
                        try:
                            p.kill()
                            killed.append(p.info['pid'])
                        except Exception:
                            pass
                if killed:
                    self._append_log(f"⏹ 已终止进程: {target_exe}, PID={killed}")
                else:
                    self._append_log(f"⏹ 未找到运行中的进程: {target_exe}")
            except Exception as e:
                self._append_log(f"⚠️ 终止进程失败: {e}")
        
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)

    # ---- 7.5a 清理历史残留进程 ----
    def cleanup_residuals(self) -> None:
        """按进程名关键词 (可多个,空格分隔) 强制 taskkill"""
        kw_text = self.cleanup_kw.text().strip()
        if not kw_text:
            QMessageBox.warning(self, "提示", "请输入至少一个关键词 (例如 aipy  lobe)")
            return
        keywords = [k.strip().lower() for k in kw_text.split() if k.strip()]

        import psutil
        targets: list[tuple[int, str, str]] = []  # (pid, name, exe)
        for p in psutil.process_iter(['name', 'pid', 'exe']):
            try:
                name = (p.info['name'] or '').lower()
                exe = (p.info['exe'] or '').lower()
                for kw in keywords:
                    if kw in name or kw in exe:
                        targets.append((p.info['pid'], p.info['name'] or '', p.info['exe'] or ''))
                        break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if not targets:
            self._append_log(f"🧹 未发现含 {keywords} 的进程")
            return

        detail = "\n".join(
            "  • PID={}  name={}  exe={}".format(pid, n, e)
            for pid, n, e in targets
        )
        confirm = QMessageBox.question(
            self, "确认清理",
            f"将 taskkill /F 强制结束 {len(targets)} 个进程:\n{detail}\n\n是否继续?",
        )
        if confirm != QMessageBox.Yes:
            return

        self.btn_cleanup.setEnabled(False)
        killed = 0
        for pid, name, exe in targets:
            try:
                r = subprocess.run(
                    ['taskkill', '/F', '/T', '/PID', str(pid)],
                    capture_output=True, text=True, timeout=10,
                )
                if r.returncode == 0:
                    killed += 1
                    self._append_log(f"  ✅ 清理 PID={pid} ({name})")
                else:
                    self._append_log(f"  ⚠️ PID={pid} 失败: {r.stderr.strip() or r.stdout.strip()}")
            except Exception as e:
                self._append_log(f"  ❌ PID={pid}: {e}")

        self._append_log(f"🧹 清理完成: {killed}/{len(targets)} 个")
        self.btn_cleanup.setEnabled(True)

    # ---- 7.5 一键启停 ----
    def _targets_to_handle(self) -> list[ShortcutInfo]:
        """根据 scope_all 决定作用于全部还是当前选中"""
        if self.scope_all.isChecked():
            return list(self.shortcuts)
        sc = self._current()
        if sc is None:
            QMessageBox.warning(self, "提示", "请先勾选「作用于全部」或在左侧选中一个快捷方式")
        return [sc] if sc else []

    def onekey_start(self) -> None:
        targets = self._targets_to_handle()
        if not targets:
            return

        # 跳过无效 target
        valid = [sc for sc in targets if sc.target and Path(sc.target).exists()]
        skipped = len(targets) - len(valid)
        if not valid:
            QMessageBox.warning(self, "提示", "所选项目没有有效的 target 路径")
            return

        confirm = QMessageBox.question(
            self, "确认启动",
            f"即将启动 {len(valid)} 个程序"
            + (f" (跳过 {skipped} 个无效)" if skipped else "")
            + "\n是否继续?",
        )
        if confirm != QMessageBox.Yes:
            return

        self.btn_onekey_start.setEnabled(False)
        self._append_log(f"🚀 一键启动 {len(valid)} 个程序")

        pids: list[int] = []
        names: list[str] = []
        use_shell = self.radio_shellexec.isChecked()
        for sc in valid:
            try:
                cwd = sc.work_dir if sc.work_dir and Path(sc.work_dir).is_dir() else str(Path(sc.target).parent)
                if use_shell:
                    cmd_str = 'cd /d "{}" && start "" "{}"'.format(cwd, sc.target)
                    proc = subprocess.Popen(
                        ["cmd", "/c", cmd_str],
                        creationflags=0x08000000,
                    )
                else:
                    proc = subprocess.Popen(
                        [sc.target],
                        cwd=cwd,
                        creationflags=0x08000000,
                    )
                pids.append(proc.pid)
                names.append(sc.name)
                self._append_log("  ✅ {}  (PID={}, mode={})".format(sc.name, proc.pid, "shell" if use_shell else "direct"))
            except Exception as e:
                self._append_log("  ❌ {}: {}".format(sc.name, e))

        # 记忆,供一键关闭用
        self.state = {"pids": pids, "names": names, "ts": int(time.time())}
        self._save_state()
        self._append_log(f"📝 已记录本次启动 {len(pids)} 个 PID")
        self.btn_onekey_start.setEnabled(True)

    def onekey_stop(self) -> None:
        pids: list[int] = self.state.get("pids", [])
        names: list[str] = self.state.get("names", [])

        # 额外补刀:有些进程会派生子进程,这里同时按可执行文件名扫一遍
        all_pids = self._expand_running_pids(pids)

        if not all_pids:
            QMessageBox.information(self, "提示", "没有可关闭的进程 (state 为空或进程已退出)")
            return

        detail = "\n".join(f"  • {n} (PID={p})" for n, p in zip(names, pids))
        confirm = QMessageBox.question(
            self, "确认关闭",
            f"将关闭以下 {len(all_pids)} 个进程:\n{detail}\n\n是否继续?",
        )
        if confirm != QMessageBox.Yes:
            return

        self.btn_onekey_stop.setEnabled(False)
        killed = 0
        for pid in all_pids:
            try:
                # /F 强制 /T 连带子进程
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    check=False, capture_output=True, text=True, timeout=10,
                )
                killed += 1
            except Exception as e:
                self._append_log(f"  ⚠️ PID {pid}: {e}")

        self._append_log(f"🛑 已尝试关闭 {killed}/{len(all_pids)} 个进程")
        # 清理状态
        self.state = {"pids": [], "names": [], "ts": 0}
        self._save_state()
        self.btn_onekey_stop.setEnabled(True)

    def _expand_running_pids(self, root_pids: list[int]) -> list[int]:
        """按 PID 列表 + 当前选中项的 target,合并出实际还活着的 PID 集合"""
        import psutil  # 局部导入,允许缺失时报错
        alive: set[int] = set()
        # 1) 记录中的 PID 仍然存活 -> 加入
        for pid in root_pids:
            try:
                if psutil.pid_exists(pid):
                    alive.add(pid)
            except Exception:
                pass
        # 2) 对当前所有 target,按可执行文件名匹配同进程
        for sc in self.shortcuts:
            if not sc.target:
                continue
            exe_name = Path(sc.target).name.lower()
            for p in psutil.process_iter(["pid", "name"]):
                try:
                    if (p.info["name"] or "").lower() == exe_name:
                        alive.add(p.info["pid"])
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        return sorted(alive)


# ---------------------------------------------------------------------------
# 8. 入口
# ---------------------------------------------------------------------------
def main() -> int:
    # MCP 模式: 不显示 GUI,作为 stdio server 运行
    if "--mcp" in sys.argv:
        return _run_mcp_only()

    # 单实例检查: 如果已有实例在运行, 通过 IPC 转发任务后退出
    if not _try_acquire_single_instance():
        print("[单实例] 已有实例在运行, 通过 IPC 转发任务...")
        _forward_to_running_instance(sys.argv)
        print("[单实例] 任务已转发, 当前进程退出")
        sys.exit(0)
    
    app = QApplication(sys.argv)
    app.setApplicationName("桌面自动化助手")
    # 设置应用图标
    icon_path = Path(__file__).parent / "app_icon.ico"
    if icon_path.exists():
        from PySide6.QtGui import QIcon
        app.setWindowIcon(QIcon(str(icon_path)))

    # 统一 QSS 风格(浅色)
    app.setStyleSheet("""
        QPushButton { padding: 4px 10px; min-height: 18px; }
        QGroupBox { font-weight: bold; margin-top: 14px; }
        QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 6px; }
        QCheckBox, QRadioButton { padding: 2px 0; }
        QLineEdit { padding: 4px; }
        QLabel { padding: 2px 0; }
    """)

    win = MainWindow()
    win.show()
    return app.exec()


def _run_mcp_only() -> int:
    """只运行 MCP server,不显示 GUI (用于 AI 客户端调用)"""
    import asyncio
    import json

    # MCP 模式才应用兼容补丁/导入 MCP 依赖,避免普通 GUI 启动被 MCP 依赖拖崩。
    try:
        from mcp_patch import patch_jsonschema_specifications
        patch_jsonschema_specifications()
    except Exception as e:
        print(f"[WARN] MCP 兼容补丁失败: {e}", file=sys.stderr)

    from mcp_embedded import scan_desktop_shortcuts, load_workflows, run_workflow_sync, launch_shortcut_sync
    from search_panel import search_everything
    
    try:
        from mcp.server import Server
        from mcp.server.stdio import stdio_server
        from mcp.types import Tool, TextContent
    except ImportError as e:
        print(f"[ERR] MCP 依赖缺失: {e}", file=sys.stderr)
        print("[ERR] 需要安装: pip install mcp", file=sys.stderr)
        return 1

    async def serve():
        server = Server("desktop-auto")
        @server.list_tools()
        async def list_tools():
            return [
                Tool(name="list_workflows", description="列出所有工作流", inputSchema={"type": "object", "properties": {"name": {"type": "string"}}}),
                Tool(name="list_shortcuts", description="列出桌面快捷方式", inputSchema={"type": "object", "properties": {}}),
                Tool(name="run_workflow", description="执行工作流", inputSchema={"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}),
                Tool(name="launch_shortcut", description="启动快捷方式", inputSchema={"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}),
                Tool(name="search_local_files", description="Everything 全盘搜索 (支持通配符 *.py / 文件名 4月明细 / 大小 size:>10MB / 日期 dm:today)", inputSchema={"type": "object", "properties": {
                    "query": {"type": "string", "description": "搜索词,如: 4月明细"},
                    "limit": {"type": "number", "description": "返回结果数,默认50"},
                    "path": {"type": "string", "description": "限定目录,如 C:\\Users\\Public"},
                    "sort": {"type": "string", "description": "排序: name/date/size,默认 date"},
                }, "required": ["query"]}),
            ]
        @server.call_tool()
        async def call_tool(name, arguments):
            try:
                if name == "list_workflows":
                    wfs = load_workflows()
                    target = arguments.get("name", "")
                    if target:
                        wf = wfs.get(target)
                        if not wf: return [TextContent(type="text", text=json.dumps({"ok": False, "error": f"不存在: {target}"}, ensure_ascii=False))]
                        return [TextContent(type="text", text=json.dumps({"ok": True, "workflow": wf}, ensure_ascii=False, indent=2))]
                    summary = {n: {"description": wf.get("description", ""), "step_count": len(wf.get("steps", []))} for n, wf in wfs.items()}
                    return [TextContent(type="text", text=json.dumps({"ok": True, "workflows": summary}, ensure_ascii=False, indent=2))]
                elif name == "list_shortcuts":
                    scs = scan_desktop_shortcuts()
                    return [TextContent(type="text", text=json.dumps({"ok": True, "count": len(scs), "shortcuts": scs}, ensure_ascii=False, indent=2))]
                elif name == "run_workflow":
                    n = arguments.get("name", "")
                    logs = []
                    result = run_workflow_sync(n, logs.append)
                    result["logs"] = logs
                    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]
                elif name == "launch_shortcut":
                    n = arguments.get("name", "")
                    return [TextContent(type="text", text=json.dumps(launch_shortcut_sync(n), ensure_ascii=False))]
                elif name == "search_local_files":
                    q = arguments.get("query", "")
                    limit = int(arguments.get("limit", 50))
                    path = arguments.get("path", "")
                    sort = arguments.get("sort", "date")
                    result = search_everything(q, path=path, limit=limit, sort=sort)
                    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]
                return [TextContent(type="text", text=json.dumps({"ok": False, "error": f"未知: {name}"}, ensure_ascii=False))]
            except Exception as e:
                return [TextContent(type="text", text=json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))]

        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    asyncio.run(serve())
    return 0




if __name__ == "__main__":
    sys.exit(main())
