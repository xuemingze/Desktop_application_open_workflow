"""
全局日志总线
============

任意模块都可以 `from log_bus import log_bus; log_bus.emit("...")` 发日志,
主窗口订阅后会写到统一的【操作日志】区。

设计:
- 进程内单例 (模块级全局对象)
- Qt Signal 跨线程安全 (auto-queued)
- 多订阅者支持 (主窗口 + 可选文件记录)
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal

# Windows GBK 兼容
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


class LogBus(QObject):
    """全局日志总线 - 单例"""

    log_signal = Signal(str)         # 转发给主窗口
    log_file_path: Optional[str] = None  # 若设置,所有日志会同时写入此文件

    def emit(self, msg: str) -> None:
        """发送一条日志"""
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        line = f"[{ts}] {msg}"
        # 文件 (可选)
        if self.log_file_path:
            try:
                Path(self.log_file_path).parent.mkdir(parents=True, exist_ok=True)
                with open(self.log_file_path, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except Exception:
                pass
        # 信号
        self.log_signal.emit(line)

    def set_log_file(self, path: str) -> None:
        self.log_file_path = path


# 进程内单例
log_bus = LogBus()
