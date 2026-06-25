# app_bridges.py
# 功能: 集中管理 MainWindow 的后台服务与桥接状态
# 目的: 把 MainWindow 从"7 个独立状态属性持有者"降级为"一个 bridges 容器的持有者"
# 兼容性: 属性名与 MainWindow 原属性一致,允许 context_tab.py 通过 MainWindow 的 @property 转发继续工作

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QObject


class AppBridges(QObject):
    """后台服务与桥接对象的集中容器。

    设计原则:
    - 属性名与 MainWindow 原属性保持一致 (特别是 memory_engine_mgr 必须保持原名,
      因为 context_tab.py 通过 self.window().memory_engine_mgr 跨窗口访问)
    - 公开属性 (无下划线前缀) 是历史原因导致需要被外部访问;下划线前缀为内部使用
    - 不在这里执行 init, init 流程由 MainWindow 显式调用 5 个 _init_* 方法
    - parent 指向 MainWindow, Qt 父子关系保证 MainWindow 销毁时自动释放
    """

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)

        # ---- 公开属性 (历史原因, 外部代码依赖) ----
        # context_tab.py 通过 self.window().memory_engine_mgr 访问
        self.memory_engine_mgr: Optional["memory_engine.MemoryEngineManager"] = None
        # assistant_core 当前没有跨模块访问, 但保持原命名风格
        self.assistant_core: Optional["assistant_core.AssistantCore"] = None

        # ---- 内部属性 (仅 MainWindow 内部使用) ----
        self._companion_bridge: Optional["companion_bridge.CompanionBridgeThread"] = None
        self._vtuber_bridge: Optional["vtuber_bridge.VTuberBridge"] = None
        self._assistant_bridge: Optional["assistant_bridge_server.AssistantBridgeServer"] = None
        self._reminder_timer: Optional["PySide6.QtCore.QTimer"] = None
        self._diary_scheduler: Optional["daily_diary.DiaryScheduler"] = None

    def __repr__(self) -> str:
        return (
            f"<AppBridges("
            f"mem={self.memory_engine_mgr is not None}, "
            f"core={self.assistant_core is not None}, "
            f"companion={self._companion_bridge is not None}, "
            f"vtuber={self._vtuber_bridge is not None}, "
            f"assistant={self._assistant_bridge is not None}, "
            f"reminder={self._reminder_timer is not None}, "
            f"diary={self._diary_scheduler is not None}"
            f")>"
        )
