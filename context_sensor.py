"""上下文感知 - 多模态传感器层

负责从桌面环境采集"上下文胶囊"（ContextCapsule），供 Gatekeeper 过滤后使用。

支持的传感器：
1. 剪贴板监听（Qt 信号，零轮询）
2. 前台窗口追踪（Windows API）
3. 文件系统监视（QFileSystemWatcher）
4. 进程启动/退出（psutil 轮询，间隔可配）

所有传感器通过 emit ContextCapsule 信号交给上层。
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Optional

from PySide6.QtCore import QObject, Signal, QTimer, QFileSystemWatcher


@dataclass
class ContextCapsule:
    """上下文胶囊——传感器层产出的统一数据结构"""
    source: str                  # "clipboard" / "window" / "file" / "process"
    clipboard_text: str = ""
    foreground_window: str = ""  # "MobaXterm - root@weecs"
    foreground_app: str = ""     # "mobaxterm.exe"（用于黑名单匹配）
    file_path: str = ""          # 文件系统事件用
    process_name: str = ""       # 进程事件用
    event_type: str = ""         # "created" / "modified" / "deleted" / "started" / "exited"
    timestamp: float = field(default_factory=time.time)


class ClipboardSensor(QObject):
    """剪贴板监听——Qt 信号驱动，零轮询"""

    captured = Signal(object)  # emit ContextCapsule

    def __init__(self, debounce_ms: int = 2000):
        super().__init__()
        self._last_text = ""
        self._last_time = 0.0
        self._debounce_ms = debounce_ms
        self._enabled = False

    def start(self):
        """启动监听（必须在 QApplication 创建后调用）"""
        if self._enabled:
            return
        from PySide6.QtGui import QGuiApplication
        clipboard = QGuiApplication.clipboard()
        clipboard.dataChanged.connect(self._on_clipboard_change)
        self._enabled = True

    def stop(self):
        if not self._enabled:
            return
        from PySide6.QtGui import QGuiApplication
        try:
            QGuiApplication.clipboard().dataChanged.disconnect(self._on_clipboard_change)
        except Exception:
            pass
        self._enabled = False

    def _on_clipboard_change(self):
        from PySide6.QtGui import QGuiApplication
        text = QGuiApplication.clipboard().text() or ""
        norm_text = text.strip()
        now = time.time()

        # 空内容丢弃
        if not norm_text:
            return

        # 去重：忽略前后空白/换行，避免 "\n192.168.0.1\n" 和 "192.168.0.1" 被当成两次
        if norm_text == self._last_text and (now - self._last_time) < (self._debounce_ms / 1000.0):
            return

        self._last_text = norm_text
        self._last_time = now

        cap = ContextCapsule(source="clipboard", clipboard_text=norm_text)
        # 同步获取前台窗口信息
        cap.foreground_window, cap.foreground_app = get_foreground_window_info()
        self.captured.emit(cap)


class WindowSensor(QObject):
    """前台窗口切换监听——Windows API + Qt 定时器

    默认 2 秒轮询一次 (过低会卡主线程, 过高反应慢)。
    """

    captured = Signal(object)

    def __init__(self, poll_interval_ms: int = 2000):
        super().__init__()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._last_window = ""
        self._interval = poll_interval_ms
        self._enabled = False

    def start(self):
        if self._enabled:
            return
        self._timer.start(self._interval)
        self._enabled = True

    def stop(self):
        if not self._enabled:
            return
        self._timer.stop()
        self._enabled = False

    def _poll(self):
        win_title, app_name = get_foreground_window_info()
        if win_title and win_title != self._last_window:
            self._last_window = win_title
            cap = ContextCapsule(
                source="window",
                foreground_window=win_title,
                foreground_app=app_name,
            )
            self.captured.emit(cap)


class FileSystemSensor(QObject):
    """文件系统监视——QFileSystemWatcher

    用户可配置要监视的目录列表（如 Downloads、Desktop、Logs 等）。
    """

    captured = Signal(object)

    def __init__(self, paths: Optional[list[str]] = None):
        super().__init__()
        self._watcher = QFileSystemWatcher(self)
        self._watcher.fileChanged.connect(lambda p: self._emit("modified", p))
        self._watcher.directoryChanged.connect(lambda p: self._emit("modified", p))
        self._enabled = False

    def set_paths(self, paths: list[str]):
        """设置监视路径（自动去重+去不存在）"""
        existing = self._watcher.directories() + self._watcher.files()
        if existing:
            self._watcher.removePaths(existing)

        valid = [p for p in paths if os.path.exists(p)]
        if valid:
            self._watcher.addPaths(valid)

    def add_path(self, path: str):
        if os.path.exists(path) and path not in self._watcher.directories():
            self._watcher.addPath(path)

    def watched_paths(self) -> list[str]:
        return self._watcher.directories() + self._watcher.files()

    def start(self):
        self._enabled = True

    def stop(self):
        self._enabled = False

    def _emit(self, event_type: str, path: str):
        if not self._enabled:
            return
        cap = ContextCapsule(
            source="file",
            file_path=path,
            event_type=event_type,
            foreground_window=get_foreground_window_info()[0],
        )
        cap.foreground_app = get_foreground_window_info()[1]
        self.captured.emit(cap)


class ProcessSensor(QObject):
    """进程启动/退出监听——psutil 轮询

    默认 2 秒轮询一次。可配置。
    """

    captured = Signal(object)

    def __init__(self, poll_interval_ms: int = 2000, whitelist: Optional[list[str]] = None):
        super().__init__()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._interval = poll_interval_ms
        self._enabled = False
        self._whitelist = [w.lower() for w in (whitelist or [])]
        # 已存在进程快照：pid -> name。不能只按进程名，否则同名 helper 还活着时捕捉不到退出。
        self._known = {}
        self._init_snapshot()

    def _init_snapshot(self):
        try:
            import psutil
            self._known = {
                int(p.info["pid"]): p.info["name"].lower()
                for p in psutil.process_iter(["name", "pid"])
                if p.info.get("name") and p.info.get("pid") is not None
            }
        except Exception:
            self._known = {}

    def set_whitelist(self, names: list[str]):
        """设置要监视的进程名白名单（空=全部）"""
        self._whitelist = [n.lower() for n in names]

    def start(self):
        if self._enabled:
            return
        self._init_snapshot()
        self._timer.start(self._interval)
        self._enabled = True

    def stop(self):
        if not self._enabled:
            return
        self._timer.stop()
        self._enabled = False

    def _poll(self):
        try:
            import psutil
        except ImportError:
            return

        current = {}
        for p in psutil.process_iter(["name", "pid"]):
            name = (p.info.get("name") or "").lower()
            pid = p.info.get("pid")
            if not name or pid is None:
                continue
            if self._whitelist and name not in self._whitelist:
                continue
            current[int(pid)] = name

        # 新进程（启动）
        for pid, name in current.items():
            if pid not in self._known:
                self._emit_event("started", name, pid)

        # 已退出
        for pid, name in self._known.items():
            if pid not in current:
                self._emit_event("exited", name, pid)

        self._known = current

    def _emit_event(self, event_type: str, proc_name: str, pid: int):
        cap = ContextCapsule(
            source="process",
            process_name=proc_name,
            event_type=event_type,
        )
        self.captured.emit(cap)


# ---------------------------------------------------------------------------
# Windows API 辅助
# ---------------------------------------------------------------------------
def get_foreground_window_info() -> tuple[str, str]:
    """获取前台窗口标题 + 进程名。

    返回 ("窗口标题", "进程名.exe")。失败时返回 ("", "")。
    """
    if os.name != "nt":
        return ("", "")

    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        psapi = ctypes.windll.psapi

        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return ("", "")

        # 窗口标题
        length = user32.GetWindowTextLengthW(hwnd)
        buff = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buff, length + 1)
        title = buff.value or ""

        # 进程 ID
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

        # 进程名
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        h_process = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h_process:
            return (title, "")

        try:
            exe_name = ctypes.create_unicode_buffer(512)
            size = wintypes.DWORD(512)
            if psapi.GetModuleFileNameExW(h_process, None, exe_name, size):
                full_path = exe_name.value
                app_name = os.path.basename(full_path)
            else:
                app_name = ""
        finally:
            kernel32.CloseHandle(h_process)

        return (title, app_name)
    except Exception:
        return ("", "")


# ---------------------------------------------------------------------------
# 聚合 Manager
# ---------------------------------------------------------------------------
class ContextSensorManager(QObject):
    """统一管理所有传感器，对外只暴露一个 captured 信号"""

    captured = Signal(object)

    def __init__(self):
        super().__init__()
        self.clipboard = ClipboardSensor()
        self.window = WindowSensor()
        self.file = FileSystemSensor()
        self.process = ProcessSensor()

        for sensor in (self.clipboard, self.window, self.file, self.process):
            sensor.captured.connect(self.captured.emit)

    def start(self, modes: dict[str, bool]):
        """根据 modes 字典启用指定传感器

        modes = {"clipboard": True, "window": True, "file": False, "process": True}
        """
        if modes.get("clipboard"):
            self.clipboard.start()
        if modes.get("window"):
            self.window.start()
        if modes.get("file"):
            self.file.start()
        if modes.get("process"):
            self.process.start()

    def stop_all(self):
        self.clipboard.stop()
        self.window.stop()
        self.file.stop()
        self.process.stop()
