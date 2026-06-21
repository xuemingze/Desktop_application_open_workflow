"""上下文感知 - 呼吸态悬浮气泡（Toast Bubble）

设计要点：
- 无焦点抢占（Qt.WA_ShowWithoutActivating）
- 毛玻璃半透明
- 队列堆叠（最多 3 条）
- hover 暂停倒计时
- 5 秒自动淡出，点击触发工具调用
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import re
import time

from PySide6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, QRect, QPoint, QSize, Signal, QObject, QThread, Slot,
)
from PySide6.QtGui import QColor, QPainter, QFont, QFontMetrics
from PySide6.QtWidgets import (
    QWidget, QLabel, QHBoxLayout, QVBoxLayout, QProgressBar, QPushButton,
    QGraphicsOpacityEffect,
)


@dataclass
class ToastIntent:
    """AI 推断返回的可执行意图"""
    intent: str               # "Nginx 端口冲突报错"
    message: str              # "发现 80 端口被占用，要帮你查 nginx.conf 吗？"
    suggested_action: str     # "search_local_files"
    action_param: str         # "nginx.conf"


class ToastBubble(QWidget):
    """单条气泡 Widget"""

    clicked = Signal(ToastIntent)
    closed = Signal(object)  # emit self

    TOAST_WIDTH = 240
    TOAST_HEIGHT = 56
    MARGIN_RIGHT = 10
    MARGIN_BOTTOM = 10
    SPACING = 6
    AUTO_DISMISS_MS = 5000

    def __init__(self, intent: ToastIntent, parent=None):
        super().__init__(parent)
        self.intent = intent
        self._hovered = False

        # 关键：避免抢占焦点 + 无边框 + 顶层 + Tool（不在任务栏）
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
        )
        # 这一行至关重要：WA_ShowWithoutActivating 防止弹出瞬间抢走焦点
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self.setFixedSize(self.TOAST_WIDTH, self.TOAST_HEIGHT)
        self._build_ui()
        self._build_animation()

        # 自动关闭计时器
        self._dismiss_timer = QTimer(self)
        self._dismiss_timer.setSingleShot(True)
        self._dismiss_timer.timeout.connect(self.fade_out)
        self._dismiss_timer.start(self.AUTO_DISMISS_MS)

    def _build_ui(self):
        # 主体布局
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 6, 10, 6)
        root.setSpacing(3)

        # 第一行：图标 + message + 关闭按钮
        top = QHBoxLayout()
        top.setSpacing(5)

        self.icon_label = QLabel("💡")
        self.icon_label.setStyleSheet("font-size: 15px; background: transparent;")
        top.addWidget(self.icon_label)

        self.message_label = QLabel(self.intent.message)
        self.message_label.setWordWrap(True)
        self.message_label.setStyleSheet(
            "color: white; font-size: 11px; background: transparent;"
        )
        top.addWidget(self.message_label, stretch=1)

        self.close_btn = QPushButton("×")
        self.close_btn.setFixedSize(16, 16)
        self.close_btn.setStyleSheet(
            "QPushButton { color: rgba(255,255,255,180); background: transparent;"
            " border: none; font-size: 12px; font-weight: bold; }"
            "QPushButton:hover { color: white; background: rgba(255,255,255,30);"
            " border-radius: 8px; }"
        )
        self.close_btn.clicked.connect(self.fade_out)
        self.close_btn.setVisible(False)  # hover 时才显示
        top.addWidget(self.close_btn)

        root.addLayout(top)

        # 第二行：进度条
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(100)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(2)
        self.progress.setStyleSheet(
            "QProgressBar { background: rgba(255,255,255,40); border: none; }"
            "QProgressBar::chunk { background: rgba(255,255,255,180); }"
        )
        root.addWidget(self.progress)

        # 进度条刷新计时器（每秒减一次）
        self._progress_timer = QTimer(self)
        self._progress_timer.timeout.connect(self._tick_progress)
        self._progress_timer.start(50)  # 50ms tick，5s 完成
        self._progress_value = 100

    def _build_animation(self):
        # 透明度动画（淡出用）
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_effect)

        self._fade_in = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_in.setDuration(220)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)
        self._fade_in.setEasingCurve(QEasingCurve.OutCubic)

        self._fade_out = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_out.setDuration(300)
        self._fade_out.setStartValue(1.0)
        self._fade_out.setEndValue(0.0)
        self._fade_out.setEasingCurve(QEasingCurve.InCubic)
        self._fade_out.finished.connect(self._on_fade_out_done)

    # ---- 公开 API ----
    def fade_in(self, target_pos: QPoint):
        """滑入到目标位置"""
        self.move(target_pos)
        self.show()
        self._fade_in.start()

    def fade_out(self):
        """淡出并关闭"""
        if self._dismiss_timer.isActive():
            self._dismiss_timer.stop()
        if self._progress_timer.isActive():
            self._progress_timer.stop()
        self._fade_out.start()

    def pause_dismiss(self):
        """hover 进入时暂停倒计时"""
        self._hovered = True
        self._dismiss_timer.stop()
        self._progress_timer.stop()
        self.close_btn.setVisible(True)

    def resume_dismiss(self):
        """hover 离开时恢复倒计时"""
        self._hovered = False
        self.close_btn.setVisible(False)
        remaining_ms = int(self._progress_value / 100 * self.AUTO_DISMISS_MS)
        self._dismiss_timer.start(remaining_ms)
        self._progress_timer.start(50)

    # ---- 内部 ----
    def _tick_progress(self):
        if self._hovered:
            return
        decrement = 50 / self.AUTO_DISMISS_MS * 100
        self._progress_value = max(0, self._progress_value - decrement)
        self.progress.setValue(int(self._progress_value))

    def _on_fade_out_done(self):
        self.closed.emit(self)
        self.deleteLater()

    # ---- 鼠标事件 ----
    def enterEvent(self, event):
        self.pause_dismiss()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.resume_dismiss()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.intent)
            self.fade_out()
        super().mousePressEvent(event)

    # ---- 绘制 ----
    def paintEvent(self, event):
        """自绘半透明圆角背景"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRect(0, 0, self.width(), self.height())
        # 深色半透明背景
        painter.setBrush(QColor(28, 28, 32, 220))
        painter.setPen(QColor(255, 255, 255, 30))
        painter.drawRoundedRect(rect, 8, 8)
        painter.end()
        super().paintEvent(event)


class ToastManager(QObject):
    """Toast 队列管理器——单例"""

    toast_clicked = Signal(ToastIntent)
    _show_requested = Signal(ToastIntent)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._queue: deque[ToastBubble] = deque(maxlen=3)
        self._move_animations: list[QPropertyAnimation] = []
        self._recent_keys: dict[str, float] = {}
        self._dedupe_seconds = 12.0
        self._show_requested.connect(self._show_toast_now, Qt.QueuedConnection)

    def _intent_key(self, intent: ToastIntent) -> str:
        """短时间去重 key。

        同一个 IP/URL/动作在 LLM 推荐 + 规则兜底 + 剪贴板重复事件中可能产生多条不同文案，
        这里按实体去重，而不是按完整 message 去重。
        """
        text = f"{intent.intent} {intent.message} {intent.suggested_action} {intent.action_param}"
        ip = re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", text)
        if ip:
            return f"ip:{ip.group(0)}"
        url = re.search(r"https?://[^\s]+", text)
        if url:
            return f"url:{url.group(0).rstrip('/')}"
        return f"{intent.suggested_action}:{intent.action_param or intent.message[:30]}".lower()

    def show_toast(self, intent: ToastIntent):
        """线程安全地显示一个新气泡。

        QWidget 必须在 ToastManager 所在线程创建；工作流/AI 工具线程调用时，
        只投递信号回 GUI 线程，避免 Windows/PyInstaller 下直接闪退。
        """
        if QThread.currentThread() is not self.thread():
            self._show_requested.emit(intent)
            return
        self._show_toast_now(intent)

    @Slot(ToastIntent)
    def _show_toast_now(self, intent: ToastIntent):
        """显示一个新气泡（仅在 GUI 线程执行）。"""
        key = self._intent_key(intent)
        now = time.time()
        # 清理旧 key
        for k, ts in list(self._recent_keys.items()):
            if now - ts > self._dedupe_seconds:
                self._recent_keys.pop(k, None)
        if key in self._recent_keys and now - self._recent_keys[key] <= self._dedupe_seconds:
            try:
                from log_bus import log_bus
                log_bus.emit(f"[Toast] 去重跳过: {key}")
            except Exception:
                pass
            return
        self._recent_keys[key] = now

        try:
            from log_bus import log_bus
            log_bus.emit(f"[Toast] show_toast: {intent.message} -> {intent.suggested_action}({intent.action_param})")
        except Exception:
            pass
        try:
            # 队列已满（maxlen=3 自动弹出最早），先让旧的淡出
            if len(self._queue) >= 3:
                oldest = self._queue[0]
                oldest.fade_out()
                # 注意：maxlen=3 会在 append 时自动丢弃最左侧元素

            toast = ToastBubble(intent)
            toast.closed.connect(self._on_toast_closed)
            toast.clicked.connect(self.toast_clicked.emit)
            self._queue.append(toast)
            self._relayout(animate=True)
        except Exception as e:
            try:
                from log_bus import log_bus
                log_bus.emit(f"[Toast] 显示失败: {type(e).__name__}: {e}")
            except Exception:
                pass

    def stop_all(self):
        for t in list(self._queue):
            t.fade_out()
        self._queue.clear()
        self._recent_keys.clear()

    def _on_toast_closed(self, toast: ToastBubble):
        try:
            self._queue.remove(toast)
        except ValueError:
            pass
        self._relayout(animate=True)

    def _relayout(self, animate: bool = True):
        """重排所有气泡位置，从下往上堆叠"""
        # ToastManager 是 QObject, 没有 self.screen(); 必须通过 QApplication 获取屏幕
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        screen_obj = None
        if app is not None:
            # 优先用当前激活窗口所在屏幕；RDP/多屏场景下 primaryScreen 可能不是用户正在看的屏幕
            win = QApplication.activeWindow()
            if win is not None and win.screen() is not None:
                screen_obj = win.screen()
            if screen_obj is None:
                from PySide6.QtGui import QCursor
                screen_obj = QApplication.screenAt(QCursor.pos())
            if screen_obj is None:
                screen_obj = QApplication.primaryScreen()
        if screen_obj is None:
            try:
                from log_bus import log_bus
                log_bus.emit("[Toast] 显示失败: 找不到可用屏幕")
            except Exception:
                pass
            return
        screen = screen_obj.availableGeometry()

        for i, toast in enumerate(self._queue):
            # i=0 是最底部，i 越大越靠上
            target_y = screen.bottom() - ToastBubble.MARGIN_BOTTOM - (i + 1) * ToastBubble.TOAST_HEIGHT - i * ToastBubble.SPACING
            target_x = screen.right() - ToastBubble.TOAST_WIDTH - ToastBubble.MARGIN_RIGHT
            target = QPoint(target_x, target_y)

            if not toast.isVisible():
                toast.fade_in(target)
            elif animate:
                # 平滑移动
                anim = QPropertyAnimation(toast, b"pos")
                anim.setDuration(220)
                anim.setStartValue(toast.pos())
                anim.setEndValue(target)
                anim.setEasingCurve(QEasingCurve.OutCubic)
                anim.start()
                self._move_animations.append(anim)  # 防止被 GC
