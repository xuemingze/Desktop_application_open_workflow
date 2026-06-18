# memory_engine.py
# 功能: 双线程架构。MainPoll负责定期采样和状态机流转；IdleWatcher负责极低开销监听键鼠唤醒。

import time
import ctypes
import psutil
from datetime import datetime, timedelta
from pathlib import Path
from PySide6.QtCore import QObject, QThread, Signal

from log_bus import log_bus
from activity_log import ActivityLogDB
from app_categorizer import categorize

# Windows API 结构体，用于空闲检测
class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

def get_idle_seconds() -> float:
    """获取系统键鼠空闲时间 (秒)"""
    lii = LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
        millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
        return millis / 1000.0
    return 0.0

def get_foreground_info_safe() -> tuple[str, str]:
    """获取前台窗口信息，权限不足时优雅降级"""
    try:
        # 获取最上层窗口句柄
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not hwnd:
            return "", "unknown_process"

        # 获取窗口标题
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        buff = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
        title = buff.value or ""

        # 获取进程名
        pid = ctypes.c_ulong()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        
        try:
            proc = psutil.Process(pid.value)
            app_name = proc.name()
        except psutil.AccessDenied:
            app_name = "System_Process"
        except psutil.NoSuchProcess:
            app_name = "Transient_Process"
        except Exception:
            app_name = "Unknown_Process"

        return title, app_name
    except Exception as e:
        log_bus.emit(f"[MemoryEngine] 前台窗口采样异常: {e}")
        return "", ""


class IdleWatcherThread(QThread):
    """永远不停的低开销监视器，用于在深度暂停时唤醒主轮询"""
    woke_from_suspend = Signal()

    def __init__(self, main_poll_ref):
        super().__init__()
        self._is_running = True
        self.main_poll = main_poll_ref

    def stop(self):
        self._is_running = False

    def run(self):
        while self._is_running:
            try:
                # 只有当主轮询处于暂停状态（深度休眠）且用户有键鼠动作时，才发唤醒信号
                if self.main_poll.is_suspended:
                    idle = get_idle_seconds()
                    if idle < 1.0:
                        self.woke_from_suspend.emit()
            except Exception as e:
                log_bus.emit(f"[IdleWatcher] Error: {e}")
            
            time.sleep(5)  # 极低开销轮询


class MainPollThread(QThread):
    """主采样线程，包含状态合并压缩与流转机"""
    # 状态：ACTIVE, IDLE
    
    def __init__(self, db: ActivityLogDB, interval=30, idle_threshold=180, suspend_threshold=1800):
        super().__init__()
        self.db = db
        self.interval = interval
        self.idle_threshold = idle_threshold
        self.suspend_threshold = suspend_threshold
        
        self._is_running = True
        self.is_suspended = False
        self._pause_until = 0.0  # 用户手动暂停的时间戳
        
        # 内部状态机变量
        self._state = "ACTIVE"
        self._cur_table = None
        self._cur_id = None
        self._cur_title = ""
        self._cur_app = ""

    def stop(self):
        self._is_running = False
        
    def manual_pause(self, seconds: int):
        self._pause_until = time.time() + seconds
        
    def wake_up(self):
        """由 IdleWatcher 或外部触发唤醒"""
        self.is_suspended = False
        # 强制清除旧状态，让下一次轮询立即打新点
        self._state = "ACTIVE"
        self._cur_title = ""
        self._cur_app = ""

    def run(self):
        while self._is_running:
            try:
                now = time.time()
                
                # 1. 检查是否在用户手动暂停期间
                if now < self._pause_until:
                    self._close_current_if_any(now)
                    time.sleep(self.interval)
                    continue

                idle = get_idle_seconds()
                
                # 2. 深度休眠逻辑 (省电)
                if idle > self.suspend_threshold and self._state != "SUSPENDED":
                    self._close_current_if_any(now)
                    self.is_suspended = True
                    self._state = "SUSPENDED"
                    log_bus.emit(f"[Memory] 深度休眠中 (idle={int(idle)}s)")
                
                if self.is_suspended:
                    time.sleep(self.interval)
                    continue

                # 3. 正常采样
                title, app = get_foreground_info_safe()
                
                # --- 核心状态机 ---
                if idle > self.idle_threshold:
                    if self._state == "ACTIVE":
                        # 活跃 -> 空闲：结算活跃，开 [IDLE] 段
                        self._close_current_if_any(now)
                        self._cur_table, self._cur_id = self.db.open_record(
                            now, title, app, category="[IDLE]", is_idle=1
                        )
                        self._state = "IDLE"
                    elif self._state == "IDLE":
                        # 保持空闲：延长 [IDLE] 段
                        self.db.update_end(self._cur_table, self._cur_id, now)
                        
                else: # 活跃状态 (idle < threshold)
                    if self._state == "IDLE":
                        # 空闲 -> 活跃：结算空闲段，准备开启新活跃段
                        self._close_current_if_any(now)
                        self._state = "ACTIVE"
                        self._cur_title = "" # 强迫开新段
                        
                    if self._state == "ACTIVE":
                        if title == self._cur_title and app == self._cur_app and self._cur_id:
                            # 窗口未变：状态压缩 (合并)
                            self.db.update_end(self._cur_table, self._cur_id, now)
                        else:
                            # 窗口改变：切段
                            self._close_current_if_any(now)
                            category = categorize(app)
                            self._cur_table, self._cur_id = self.db.open_record(
                                now, title, app, category=category, is_idle=0
                            )
                            self._cur_title = title
                            self._cur_app = app
                            
            except Exception as e:
                log_bus.emit(f"[MainPoll] Error: {e}")
                
            time.sleep(self.interval)

    def _close_current_if_any(self, ts):
        if self._cur_table and self._cur_id:
            self.db.close_record(self._cur_table, self._cur_id, ts)
            self._cur_table = None
            self._cur_id = None


class MemoryEngineManager(QObject):
    """对外的控制网关，管理双线程"""
    paused_changed = Signal(bool, str) # 通知托盘图标或 UI

    def __init__(self, db_dir: Path):
        super().__init__()
        self.db = ActivityLogDB(db_dir)
        
        self.main_poll = MainPollThread(self.db, interval=30, idle_threshold=180, suspend_threshold=1800)
        self.idle_watcher = IdleWatcherThread(self.main_poll)
        
        # 绑信号：唤醒主线程
        self.idle_watcher.woke_from_suspend.connect(self.main_poll.wake_up)

    def start(self):
        self.main_poll.start()
        self.idle_watcher.start()

    def stop(self):
        self.idle_watcher.stop()
        self.main_poll.stop()
        self.idle_watcher.wait()
        self.main_poll.wait()

    def pause(self, seconds: int):
        self.main_poll.manual_pause(seconds)
        resume_time = (datetime.now() + timedelta(seconds=seconds)).strftime("%H:%M")
        self.paused_changed.emit(True, f"已暂停至 {resume_time}")

    def pause_until(self, hour: int):
        target = datetime.now().replace(hour=hour, minute=0, second=0, microsecond=0)
        if target < datetime.now():
            target += timedelta(days=1)
        secs = int((target - datetime.now()).total_seconds())
        self.pause(secs)