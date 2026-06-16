"""
全局日志总线
============

任意模块都可以 `from log_bus import log_bus; log_bus.emit("...")` 发日志,
主窗口订阅后会写到统一的【操作日志】区。

设计:
- 进程内单例 (模块级全局对象)
- Qt Signal 跨线程安全 (auto-queued)
- 多订阅者支持 (主窗口 + 可选文件记录)
- **文件 I/O 异步化**: emit 不会同步打开文件,后台线程 flush (避免高频调用卡主线程)
"""
from __future__ import annotations

import os
import sys
import threading
import queue
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal, QTimer

# Windows GBK 兼容
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


class _FileWriterThread(threading.Thread):
    """后台线程: 独站从队列里取行,批量写入文件

    这样主线程 emit() 不会同步打开/关闭文件,避免被杀毒/索引软件卡住。
    """

    def __init__(self):
        super().__init__(daemon=True, name="LogBusWriter")
        self._q: "queue.Queue[Optional[str]]" = queue.Queue()
        self._path: Optional[str] = None
        self._fp = None
        self._stop = False
        self._batch: list[str] = []
        self._batch_max = 20     # 攒满 20 行刷一次
        self._flush_interval = 1.0  # 最多 1 秒刷一次

    def set_path(self, path: str) -> None:
        """设置日志文件路径。下一轮 flush 生效。"""
        self._path = path
        # 先关旧文件
        if self._fp:
            try:
                self._fp.flush()
                self._fp.close()
            except Exception:
                pass
            self._fp = None

    def submit(self, line: str) -> None:
        """主线程调用,非阻塞"""
        self._q.put(line)

    def stop(self) -> None:
        self._stop = True
        self._q.put(None)  # poison pill

    def run(self) -> None:
        import time
        last_flush = time.time()
        while not self._stop:
            try:
                line = self._q.get(timeout=0.1)
            except queue.Empty:
                # 超时: 检查是否需要 flush
                if self._batch and (time.time() - last_flush) > self._flush_interval:
                    self._flush()
                    last_flush = time.time()
                continue
            if line is None:  # poison
                break
            self._batch.append(line)
            if len(self._batch) >= self._batch_max:
                self._flush()
                last_flush = time.time()
        # 退出前 flush 剩余
        if self._batch:
            self._flush()
        if self._fp:
            try:
                self._fp.close()
            except Exception:
                pass

    def _flush(self) -> None:
        if not self._batch:
            return
        if not self._path:
            self._batch.clear()
            return
        try:
            # 如果文件句柄未开, 打开
            if self._fp is None:
                Path(self._path).parent.mkdir(parents=True, exist_ok=True)
                self._fp = open(self._path, "a", encoding="utf-8", buffering=8192)
            # 一次性写
            self._fp.write("\n".join(self._batch) + "\n")
            self._fp.flush()
        except Exception:
            # 写入失败,丢掉本批
            if self._fp:
                try:
                    self._fp.close()
                except Exception:
                    pass
                self._fp = None
        finally:
            self._batch.clear()


class LogBus(QObject):
    """全局日志总线 - 单例"""

    log_signal = Signal(str)         # 转发给主窗口

    def __init__(self):
        super().__init__()
        self._writer = _FileWriterThread()
        self._writer.start()
        # Qt timer for Qt-thread deferred writes (also routes through writer)

    def emit(self, msg: str) -> None:
        """发送一条日志 (主线程调用, 不会阻塞 I/O)"""
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        line = f"[{ts}] {msg}"
        # 文件 (异步, 不阻塞)
        self._writer.submit(line)
        # 信号 (Qt 跨线程 queued, 主线程接到后写 QTextEdit)
        try:
            self.log_signal.emit(line)
        except RuntimeError:
            # Signal 在 QObject 被 delete 后发会报这个, 忽略
            pass

    def set_log_file(self, path: str) -> None:
        self._writer.set_path(path)

    def shutdown(self) -> None:
        """进程退出前调用, flush 剩余"""
        self._writer.stop()


# 进程内单例
log_bus = LogBus()
