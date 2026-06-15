"""
工作流面板 - GUI 嵌入组件
与主窗口的快捷方式列表打通,支持截图框选
"""
from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Optional
from PySide6.QtCore import Qt, QThread, Signal, QRect, QPoint
from PySide6.QtGui import QPainter, QPen, QColor, QGuiApplication
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget, QListWidgetItem,
    QLabel, QLineEdit, QComboBox, QSpinBox, QFileDialog, QTextEdit, QGroupBox,
    QMessageBox, QCheckBox, QSplitter, QInputDialog, QDialog, QSizePolicy
)


# ============================================================
# 截图框选对话框 (全屏透明)
# ============================================================
class SnipDialog(QDialog):
    """全屏透明框选工具,支持选择区域"""
    captured = Signal(QRect)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)
        self._start = None
        self._end = None

        # 覆盖整个虚拟桌面(支持多屏)
        virtual = QGuiApplication.primaryScreen().virtualGeometry()
        self.setGeometry(virtual)

    def paintEvent(self, ev):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))  # 半透明黑遮罩
        if self._start and self._end:
            rect = QRect(self._start, self._end).normalized()
            pen = QPen(QColor(0, 200, 0), 2)
            painter.setPen(pen)
            painter.drawRect(rect)

    def mousePressEvent(self, ev):
        self._start = ev.position().toPoint()
        self._end = self._start
        self.update()

    def mouseMoveEvent(self, ev):
        self._end = ev.position().toPoint()
        self.update()

    def mouseReleaseEvent(self, ev):
        self._end = ev.position().toPoint()
        rect = QRect(self._start, self._end).normalized()
        self.captured.emit(rect)
        self.accept()

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Escape:
            self.reject()


# ============================================================
# 步骤执行器
# ============================================================
class StepExecutor:
    @staticmethod
    def execute(step: dict, log_func) -> bool:
        step_type = step.get("type", "")
        step_name = step.get("name", step_type)
        params = step.get("params", {})

        if not step.get("enabled", True):
            log_func(f"  跳过: {step_name}")
            return True

        log_func(f"\n--- 步骤: {step_name} ---")
        try:
            if step_type == "launch_app":
                return StepExecutor._launch_app(params, log_func)
            elif step_type == "wait":
                return StepExecutor._wait(params, log_func)
            elif step_type == "click_image":
                return StepExecutor._click_image(params, log_func)
            elif step_type == "key_press":
                return StepExecutor._key_press(params, log_func)
            elif step_type == "click_coords":
                return StepExecutor._click_coords(params, log_func)
            elif step_type == "search_file":
                return StepExecutor._search_file(params, log_func)
            else:
                log_func(f"  未知步骤类型: {step_type}")
                return False
        except Exception as e:
            log_func(f"  步骤异常: {e}")
            return False

    @staticmethod
    def _launch_app(params, log_func) -> bool:
        import subprocess
        path = params.get("path", "")
        if not path or not Path(path).exists():
            log_func(f"  路径不存在: {path}")
            return False
        log_func(f"  启动: {path}")
        subprocess.Popen([path], creationflags=0x08000000)
        log_func(f"  已启动")
        return True

    @staticmethod
    def _wait(params, log_func) -> bool:
        seconds = params.get("seconds", 2)
        log_func(f"  等待 {seconds} 秒")
        for i in range(seconds, 0, -1):
            log_func(f"  {i}...")
            time.sleep(1)
        return True

    @staticmethod
    def _click_image(params, log_func) -> bool:
        import pyautogui
        from image_match import locate_on_screen, get_center
        template = params.get("template", "")
        confidence = params.get("confidence", 0.7)
        show_desktop = params.get("show_desktop", False)
        click_type = params.get("click_type", "double")
        # 路径转换: 相对路径转绝对路径
        if template:
            template = str(Path(template).resolve())
        if not template or not Path(template).exists():
            log_func(f"  模板不存在: {template}")
            return False
        if show_desktop:
            log_func(f"  按 Win+D 显示桌面")
            pyautogui.hotkey('win', 'd')
            time.sleep(0.5)
        else:
            log_func(f"  保持当前窗口状态(不按 Win+D)")
            time.sleep(0.2)
        log_func(f"  匹配 (阈值={confidence}): {template}")
        try:
            # 先截图再调匹配 (避免 opencv 读模板问题)
            screen = pyautogui.screenshot()
            box = locate_on_screen(template, confidence=confidence, screenshot=screen)
        except Exception as e:
            log_func(f"  匹配异常: {e}")
            return False
        if box:
            x, y, w, h = box
            center = (x + w // 2, y + h // 2)
            log_func(f"  找到: 区域=({x},{y},{w}x{h}) 中心={center}")
            if click_type == "double":
                pyautogui.doubleClick(center)
                log_func(f"  已双击")
            else:
                pyautogui.click(center)
                log_func(f"  已单击")
            return True
        else:
            log_func(f"  未匹配到模板")
            debug = Path("samples") / "_debug_workflow.png"
            debug.parent.mkdir(exist_ok=True)
            pyautogui.screenshot(str(debug))
            log_func(f"  调试截图: {debug}")
            return False

    @staticmethod
    def _key_press(params, log_func) -> bool:
        import pyautogui
        keys = params.get("keys", "")
        log_func(f"  按键: {keys}")
        if "+" in keys:
            key_list = [k.strip().lower() for k in keys.split("+")]
            pyautogui.hotkey(*key_list)
        else:
            pyautogui.press(keys)
        return True

    @staticmethod
    def _click_coords(params, log_func) -> bool:
        import pyautogui
        x = params.get("x", 0)
        y = params.get("y", 0)
        # 兼容旧格式 button / 新格式 click_type
        click_type = params.get("click_type")
        if not click_type:
            btn = params.get("button", "left")
            click_type = "left_single" if btn == "left" else ("right_single" if btn == "right" else "left_single")
        log_func(f"  坐标点击: ({x}, {y}) 类型={click_type}")
        if click_type == "left_single":
            pyautogui.click(x, y, button="left")
        elif click_type == "left_double":
            pyautogui.doubleClick(x, y, button="left")
        elif click_type == "right_single":
            pyautogui.click(x, y, button="right")
        else:
            pyautogui.click(x, y, button="left")
        return True

    @staticmethod
    def _search_file(params, log_func) -> bool:
        """使用 Everything HTTP 搜索本地文件"""
        query = params.get("query", "").strip()
        if not query:
            log_func("  搜索词为空,跳过")
            return False
        path = params.get("path", "").strip()
        limit = int(params.get("limit", 10))
        action = params.get("action", "log")  # log / open_first / save_var

        log_func(f"  搜索: {query}" + (f" (限定: {path})" if path else ""))

        try:
            # 懒加载: 避免 PyInstaller 打额外的依赖
            from search_panel import search_everything
            result = search_everything(query, limit=limit, sort="date", path=path)
            if not isinstance(result, dict):
                log_func(f"  搜索返回格式错误: {type(result).__name__}")
                return False
            if not result.get("ok"):
                log_func(f"  搜索失败: {result.get('error', '未知错误')}")
                return False
            results = result.get("results", [])
            log_func(f"  找到 {len(results)} 个结果:")
            for i, r in enumerate(results[:5], 1):
                log_func(f"    {i}. {r.get('name', '?')}  ({r.get('path', '?')})")
            if len(results) > 5:
                log_func(f"    ...还有 {len(results)-5} 个")

            if action == "open_first" and results:
                first = results[0]
                target_path = first.get("path", "")
                # path 可能是目录,需要拼接 name
                if not target_path or not Path(target_path).is_file():
                    target_path = str(Path(target_path) / first.get("name", "")) if target_path else ""
                if target_path and Path(target_path).exists():
                    import os
                    os.startfile(target_path)
                    log_func(f"  已打开: {target_path}")
                else:
                    log_func(f"  无法打开: 文件不存在 ({target_path})")
            elif action == "save_var":
                # TODO: 保存到工作流变量(供后续步骤使用)
                log_func(f"  TODO: 保存 {len(results)} 个结果到工作流变量")

            return True
        except ImportError:
            log_func("  搜索模块未安装 (需要 search_panel.py 和 Everything)")
            return False
        except Exception as e:
            log_func(f"  搜索出错: {e}")
            return False


# ============================================================
# 工作流 Worker
# ============================================================
class WorkflowWorker(QThread):
    log_signal = Signal(str)
    finished_signal = Signal(bool, str)

    def __init__(self, workflow: dict):
        super().__init__()
        self.workflow = workflow
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            name = self.workflow.get("name", "未命名")
            steps = self.workflow.get("steps", [])
            self.log_signal.emit(f"开始执行工作流: {name}")
            self.log_signal.emit(f"步骤数: {len(steps)}")
            success = 0
            total = len([s for s in steps if s.get("enabled", True)])
            for i, step in enumerate(steps):
                if self._cancel:
                    self.log_signal.emit("已取消")
                    self.finished_signal.emit(False, "用户取消")
                    return
                if not step.get("enabled", True):
                    continue
                self.log_signal.emit(f"\n[{i+1}/{total}]")
                if StepExecutor.execute(step, self.log_signal.emit):
                    success += 1
            self.log_signal.emit(f"\n执行完成: {success}/{total} 成功")
            self.finished_signal.emit(success == total, f"{success}/{total} 成功")
        except Exception as e:
            self.log_signal.emit(f"工作流执行异常: {e}")
            self.finished_signal.emit(False, str(e))


# ============================================================
# 工作流编辑面板
# ============================================================
class WorkflowEditor(QWidget):
    STEP_TYPES = [
        ("launch_app", "启动软件"),
        ("wait", "等待"),
        ("click_image", "截图匹配点击"),
        ("key_press", "按键输入"),
        ("click_coords", "坐标点击"),
        ("search_file", "文件搜索"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.workflows: dict[str, dict] = {}
        self.workflow_file = Path("workflows.json")
        self.worker: Optional[WorkflowWorker] = None
        # 当前工作流的步骤列表(临时存储)
        self._current_steps: list[dict] = []
        self._current_workflow: str = ""  # 记住当前选中的工作流名

        # 从主窗口获取快捷方式列表
        self.shortcuts = []
        if parent and hasattr(parent, 'shortcuts'):
            self.shortcuts = parent.shortcuts

        self._load_workflows()
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # ===== 左侧: 工作流列表 =====
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.addWidget(QLabel("工作流列表:"))
        self.wf_list = QListWidget()
        self.wf_list.currentRowChanged.connect(self._on_wf_select)
        lv.addWidget(self.wf_list)
        wf_btn_row = QHBoxLayout()
        self.btn_new_wf = QPushButton("+ 新建")
        self.btn_new_wf.clicked.connect(self._new_workflow)
        self.btn_del_wf = QPushButton("删除")
        self.btn_del_wf.clicked.connect(self._del_workflow)
        wf_btn_row.addWidget(self.btn_new_wf)
        wf_btn_row.addWidget(self.btn_del_wf)
        lv.addLayout(wf_btn_row)
        left.setMaximumWidth(220)
        layout.addWidget(left)

        # ===== 右侧: 步骤编辑 =====
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)

        # 步骤工具栏
        toolbar = QHBoxLayout()
        self.btn_add_step = QPushButton("+ 添加步骤")
        self.btn_add_step.clicked.connect(self._add_step)
        self.btn_del_step = QPushButton("删除")
        self.btn_del_step.clicked.connect(self._del_step)
        self.btn_up_step = QPushButton("↑")
        self.btn_up_step.clicked.connect(self._up_step)
        self.btn_down_step = QPushButton("↓")
        self.btn_down_step.clicked.connect(self._down_step)
        toolbar.addWidget(self.btn_add_step)
        toolbar.addWidget(self.btn_del_step)
        toolbar.addWidget(self.btn_up_step)
        toolbar.addWidget(self.btn_down_step)
        toolbar.addStretch()
        rv.addLayout(toolbar)

        # 步骤列表
        self.step_list = QListWidget()
        self.step_list.currentRowChanged.connect(self._on_step_select)
        self.step_list.setMaximumHeight(180)
        rv.addWidget(self.step_list)

        # 步骤详情编辑
        detail = QGroupBox("步骤详情")
        dv = QVBoxLayout(detail)

        # 步骤类型和名称
        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("类型:"))
        self.step_type_combo = QComboBox()
        for key, name in self.STEP_TYPES:
            self.step_type_combo.addItem(name, key)
        self.step_type_combo.currentIndexChanged.connect(self._on_type_change)
        type_row.addWidget(self.step_type_combo)
        type_row.addWidget(QLabel("名称:"))
        self.step_name_edit = QLineEdit()
        self.step_name_edit.setPlaceholderText("步骤名称")
        type_row.addWidget(self.step_name_edit)
        self.step_enabled = QCheckBox("启用")
        self.step_enabled.setChecked(True)
        type_row.addWidget(self.step_enabled)
        dv.addLayout(type_row)

        # ============ 启动软件 专用控件 ============
        self.launch_widget = QWidget()
        lw = QVBoxLayout(self.launch_widget)
        lw.setContentsMargins(0, 0, 0, 0)
        lw.addWidget(QLabel("从桌面快捷方式列表选择(可执行/停止):"))
        self.launch_combo = QComboBox()
        self.launch_combo.addItem("-- 选择软件 --", "")
        for sc in self.shortcuts:
            self.launch_combo.addItem(f"{sc.name}  →  {sc.target}", sc.target)
        lw.addWidget(self.launch_combo)
        self.launch_path_label = QLabel("路径: ")
        self.launch_path_label.setStyleSheet("color: #555; font-size: 11px;")
        lw.addWidget(self.launch_path_label)
        self.launch_combo.currentIndexChanged.connect(self._on_launch_select)
        dv.addWidget(self.launch_widget)

        # ============ 等待 专用控件 ============
        self.wait_widget = QWidget()
        ww = QHBoxLayout(self.wait_widget)
        ww.setContentsMargins(0, 0, 0, 0)
        ww.addWidget(QLabel("等待秒数:"))
        self.wait_spin = QSpinBox()
        self.wait_spin.setRange(1, 3600)
        self.wait_spin.setValue(2)
        ww.addWidget(self.wait_spin)
        ww.addStretch()
        dv.addWidget(self.wait_widget)

        # ============ 截图匹配点击 专用控件 ============
        self.image_widget = QWidget()
        # 固定 widget 高度,避免被外面布局拉伸
        self.image_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        iw = QVBoxLayout(self.image_widget)
        iw.setContentsMargins(0, 0, 0, 0)
        iw.setSpacing(4)
        iw.addWidget(QLabel("模板图片:"))
        img_row = QHBoxLayout()
        self.image_path_edit = QLineEdit()
        self.image_path_edit.setPlaceholderText("samples/xxx.png")
        self.btn_snip = QPushButton("✂️ 截图框选")
        self.btn_snip.clicked.connect(self._screenshot_template)
        self.btn_browse_img = QPushButton("📂 浏览")
        self.btn_browse_img.clicked.connect(self._browse_template)
        img_row.addWidget(self.image_path_edit, 1)
        img_row.addWidget(self.btn_snip)
        img_row.addWidget(self.btn_browse_img)
        iw.addLayout(img_row)
        conf_row = QHBoxLayout()
        conf_row.addWidget(QLabel("匹配阈值:"))
        self.conf_spin = QSpinBox()
        self.conf_spin.setRange(5, 100)
        self.conf_spin.setValue(30)
        self.conf_spin.setSuffix("%")
        conf_row.addWidget(self.conf_spin)
        self.show_desktop_chk = QCheckBox("先按 Win+D 显示桌面")
        self.show_desktop_chk.setChecked(False)  # 默认不按
        conf_row.addWidget(self.show_desktop_chk)
        conf_row.addStretch()
        iw.addLayout(conf_row)
        # 预览区
        self.image_preview = QLabel("(无预览)")
        self.image_preview.setMinimumHeight(120)
        self.image_preview.setMaximumHeight(160)
        self.image_preview.setAlignment(Qt.AlignCenter)
        self.image_preview.setStyleSheet("background:#f5f5f5; border:1px dashed #999; padding:4px;")
        self.image_preview.setText("(无预览)")
        iw.addWidget(self.image_preview)
        # 点击类型
        click_row = QHBoxLayout()
        click_row.addWidget(QLabel("点击类型:"))
        self.click_type_combo = QComboBox()
        self.click_type_combo.addItem("双击 (默认)", "double")
        self.click_type_combo.addItem("单击", "single")
        click_row.addWidget(self.click_type_combo)
        click_row.addStretch()
        iw.addLayout(click_row)
        dv.addWidget(self.image_widget)

        # ============ 按键 专用控件 ============
        self.key_widget = QWidget()
        kw = QVBoxLayout(self.key_widget)
        kw.setContentsMargins(0, 0, 0, 0)
        kw.addWidget(QLabel("按键 (支持组合键,如 ctrl+c / alt+tab / win+d):"))
        self.key_edit = QLineEdit()
        kw.addWidget(self.key_edit)
        dv.addWidget(self.key_widget)

        # ============ 坐标点击 专用控件 ============
        self.coord_widget = QWidget()
        cw = QVBoxLayout(self.coord_widget)
        cw.setContentsMargins(0, 0, 0, 0)
        coord_row = QHBoxLayout()
        coord_row.addWidget(QLabel("X:"))
        self.x_spin = QSpinBox()
        self.x_spin.setRange(0, 9999)
        coord_row.addWidget(self.x_spin)
        coord_row.addWidget(QLabel("Y:"))
        self.y_spin = QSpinBox()
        self.y_spin.setRange(0, 9999)
        coord_row.addWidget(self.y_spin)
        coord_row.addWidget(QLabel("点击:"))
        self.click_combo = QComboBox()
        self.click_combo.addItem("左键单击", "left_single")
        self.click_combo.addItem("左键双击", "left_double")
        self.click_combo.addItem("右键单击", "right_single")
        coord_row.addWidget(self.click_combo)
        coord_row.addStretch()
        cw.addLayout(coord_row)
        # 捕捉坐标按钮行
        capture_row = QHBoxLayout()
        self.btn_capture = QPushButton("🎯 捕捉当前鼠标坐标 (3秒倒计时)")
        self.btn_capture.setStyleSheet(
            "QPushButton { background:#0891b2; color:white; padding:6px; font-weight:bold; }"
            "QPushButton:hover { background:#0e7490; }"
            "QPushButton:disabled { background:#9ca3af; }"
        )
        self.btn_capture.clicked.connect(self._capture_mouse_position)
        capture_row.addWidget(self.btn_capture)
        self.capture_status = QLabel("")
        self.capture_status.setStyleSheet("color:#666; font-size:11px;")
        capture_row.addWidget(self.capture_status)
        capture_row.addStretch()
        cw.addLayout(capture_row)
        dv.addWidget(self.coord_widget)

        # ============ 文件搜索 专用控件 ============
        self.search_widget = QWidget()
        self.search_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        sw = QVBoxLayout(self.search_widget)
        sw.setContentsMargins(0, 0, 0, 0)
        sw.setSpacing(4)
        # 查询词
        qrow = QHBoxLayout()
        qrow.addWidget(QLabel("搜索词:"))
        self.search_query_edit = QLineEdit()
        self.search_query_edit.setPlaceholderText("如: 4月明细, 报告*.pdf, ext:docx")
        qrow.addWidget(self.search_query_edit, 1)
        sw.addLayout(qrow)
        # 可选限定目录
        prow = QHBoxLayout()
        prow.addWidget(QLabel("限定目录:"))
        self.search_path_edit = QLineEdit()
        self.search_path_edit.setPlaceholderText("可选, 例: C:\\Users\\Public")
        prow.addWidget(self.search_path_edit, 1)
        sw.addLayout(prow)
        # 限制结果数
        lrow = QHBoxLayout()
        lrow.addWidget(QLabel("最大结果:"))
        self.search_limit_spin = QSpinBox()
        self.search_limit_spin.setRange(1, 1000)
        self.search_limit_spin.setValue(10)
        lrow.addWidget(self.search_limit_spin)
        lrow.addWidget(QLabel("  发现后动作:"))
        self.search_action_combo = QComboBox()
        self.search_action_combo.addItem("仅输出到日志", "log")
        self.search_action_combo.addItem("打开第一个结果", "open_first")
        self.search_action_combo.addItem("保存到变量 (供后续步骤用)", "save_var")
        lrow.addWidget(self.search_action_combo)
        lrow.addStretch()
        sw.addLayout(lrow)
        # 帮助
        self.search_help = QLabel("💡 使用 Everything 搜索本地文件。需要本机安装 Everything 并关闭 HTTP 鉴权。")
        self.search_help.setStyleSheet("color: #888; font-size: 10px; padding: 2px 0;")
        self.search_help.setWordWrap(True)
        sw.addWidget(self.search_help)
        dv.addWidget(self.search_widget)

        # 加个 stretch 让可见控件贴顶
        dv.addStretch(1)

        rv.addWidget(detail)

        # 保存/重置按钮
        btn_row = QHBoxLayout()
        self.btn_save_step = QPushButton("💾 保存步骤修改")
        self.btn_save_step.clicked.connect(self._save_step)
        btn_row.addWidget(self.btn_save_step)
        self.btn_save_all = QPushButton("💾 保存到文件")
        self.btn_save_all.clicked.connect(self._save_workflow_file)
        btn_row.addWidget(self.btn_save_all)
        rv.addLayout(btn_row)

        # 执行控制
        exec_row = QHBoxLayout()
        self.btn_run_wf = QPushButton("▶ 执行")
        self.btn_run_wf.setStyleSheet(
            "QPushButton { background:#16a34a; color:white; font-weight:bold; padding:8px; }"
            "QPushButton:hover { background:#15803d; }"
            "QPushButton:disabled { background:#9ca3af; }"
        )
        self.btn_run_wf.clicked.connect(self._run_workflow)
        self.btn_stop_wf = QPushButton("⏹ 停止")
        self.btn_stop_wf.setStyleSheet(
            "QPushButton { background:#dc2626; color:white; font-weight:bold; padding:8px; }"
            "QPushButton:hover { background:#b91c1c; }"
            "QPushButton:disabled { background:#9ca3af; }"
        )
        self.btn_stop_wf.clicked.connect(self._stop_workflow)
        self.btn_stop_wf.setEnabled(False)
        exec_row.addWidget(self.btn_run_wf)
        exec_row.addWidget(self.btn_stop_wf)
        rv.addLayout(exec_row)

        layout.addWidget(right)
        self._refresh_wf_list()

    def refresh_shortcuts(self):
        """主窗口刷新快捷方式时调用"""
        if self.parent_window and hasattr(self.parent_window, 'shortcuts'):
            self.shortcuts = self.parent_window.shortcuts
            # 重新填充 launch_combo
            current = self.launch_combo.currentData()
            self.launch_combo.clear()
            self.launch_combo.addItem("-- 选择软件 --", "")
            for sc in self.shortcuts:
                self.launch_combo.addItem(f"{sc.name}  →  {sc.target}", sc.target)
            if current:
                idx = self.launch_combo.findData(current)
                if idx >= 0:
                    self.launch_combo.setCurrentIndex(idx)

    def _load_workflows(self):
        if self.workflow_file.exists():
            try:
                self.workflows = json.loads(self.workflow_file.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"加载工作流失败: {e}")
                self.workflows = {}
        else:
            self.workflows = {
                "zzz日常": {
                    "name": "zzz日常",
                    "description": "启动 MiniMax 测试",
                    "steps": [
                        {
                            "type": "launch_app",
                            "name": "启动 MiniMax",
                            "params": {"path": r"C:\Users\Administrator\AppData\Local\Programs\MiniMax Code\MiniMax Code.exe"},
                            "enabled": True
                        },
                        {
                            "type": "wait",
                            "name": "等待启动",
                            "params": {"seconds": 5},
                            "enabled": True
                        }
                    ]
                }
            }
            self._save_to_file()

    def _save_to_file(self):
        self.workflow_file.write_text(
            json.dumps(self.workflows, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def _refresh_wf_list(self):
        self.wf_list.clear()
        for name in self.workflows:
            self.wf_list.addItem(name)

    def _on_wf_select(self, row):
        if row < 0:
            return
        name = self.wf_list.item(row).text()
        self._current_workflow = name
        self._current_steps = list(self.workflows.get(name, {}).get("steps", []))
        self._refresh_step_list()

    def _refresh_step_list(self):
        self.step_list.clear()
        for step in self._current_steps:
            step_name = step.get("name", step.get("type", ""))
            enabled = "✓" if step.get("enabled", True) else "✗"
            self.step_list.addItem(f"[{enabled}] {step_name}")

    def _on_step_select(self, row):
        if row < 0 or row >= len(self._current_steps):
            return
        step = self._current_steps[row]
        # 类型
        step_type = step.get("type", "")
        for i, (k, _) in enumerate(self.STEP_TYPES):
            if k == step_type:
                self.step_type_combo.setCurrentIndex(i)
                break
        # 名称和启用
        self.step_name_edit.setText(step.get("name", ""))
        self.step_enabled.setChecked(step.get("enabled", True))
        # 参数
        params = step.get("params", {})
        if step_type == "launch_app":
            path = params.get("path", "")
            idx = self.launch_combo.findData(path)
            if idx >= 0:
                self.launch_combo.setCurrentIndex(idx)
            else:
                self.launch_path_label.setText(f"路径: {path} (不在快捷方式列表中)")
        elif step_type == "wait":
            self.wait_spin.setValue(params.get("seconds", 2))
        elif step_type == "click_image":
            self.image_path_edit.setText(params.get("template", ""))
            self.conf_spin.setValue(int(params.get("confidence", 0.7) * 100))
            self.show_desktop_chk.setChecked(params.get("show_desktop", False))
            click_type = params.get("click_type", "double")
            idx = self.click_type_combo.findData(click_type)
            if idx >= 0:
                self.click_type_combo.setCurrentIndex(idx)
            self._update_image_preview()
        elif step_type == "key_press":
            self.key_edit.setText(params.get("keys", ""))
        elif step_type == "click_coords":
            self.x_spin.setValue(params.get("x", 0))
            self.y_spin.setValue(params.get("y", 0))
            click_type = params.get("click_type", "left_single")
            idx = self.click_combo.findData(click_type)
            if idx >= 0:
                self.click_combo.setCurrentIndex(idx)
        elif step_type == "search_file":
            self.search_query_edit.setText(params.get("query", ""))
            self.search_path_edit.setText(params.get("path", ""))
            self.search_limit_spin.setValue(params.get("limit", 10))
            action = params.get("action", "log")
            idx = self.search_action_combo.findData(action)
            if idx >= 0:
                self.search_action_combo.setCurrentIndex(idx)

    def _on_type_change(self, idx):
        """切换步骤类型,显示对应控件"""
        step_type = self.step_type_combo.itemData(idx)
        self.launch_widget.setVisible(step_type == "launch_app")
        self.wait_widget.setVisible(step_type == "wait")
        self.image_widget.setVisible(step_type == "click_image")
        self.key_widget.setVisible(step_type == "key_press")
        self.coord_widget.setVisible(step_type == "click_coords")
        self.search_widget.setVisible(step_type == "search_file")

    def _on_launch_select(self, idx):
        path = self.launch_combo.itemData(idx) or ""
        if path:
            self.launch_path_label.setText(f"路径: {path}")
        else:
            self.launch_path_label.setText("路径: ")

    def _screenshot_template(self):
        """截图框选生成模板: 隐藏 GUI 本身,全屏透明选区"""
        # 隐藏本主窗口,只露出干净全屏
        main_win = self.window()  # 拿到顶层窗口
        main_win.hide()
        time.sleep(0.3)  # 等待动画完成
        try:
            snip = SnipDialog(self)
            snip.captured.connect(lambda rect: self._on_screenshot_captured(rect))
            snip.exec()
        finally:
            # 恢复显示
            main_win.show()
            main_win.raise_()

    def _capture_mouse_position(self):
        """倒计时 3 秒后,自动捕捉当前鼠标坐标填入 X/Y (隐藏主窗口)"""
        import pyautogui
        self.btn_capture.setEnabled(False)
        main_win = self.window()
        # 隐藏主窗口,让用户看清目标位置
        main_win.hide()
        self.capture_status.setText("3 秒后捕捉坐标,请将鼠标移到目标位置...")
        from PySide6.QtCore import QTimer
        QTimer.singleShot(300, lambda: self._capture_countdown(3))

    def _capture_countdown(self, n):
        if n <= 0:
            import pyautogui
            x, y = pyautogui.position()
            self.x_spin.setValue(x)
            self.y_spin.setValue(y)
            self.capture_status.setText(f"已捕捉: ({x}, {y})")
            self.btn_capture.setEnabled(True)
            # 恢复主窗口
            main_win = self.window()
            main_win.show()
            main_win.raise_()
            self._append_log(f"捕捉到坐标: ({x}, {y})")
            return
        self.capture_status.setText(f"{n} 秒后捕捉...")
        from PySide6.QtCore import QTimer
        QTimer.singleShot(1000, lambda: self._capture_countdown(n - 1))

    def _on_screenshot_captured(self, rect):
        """截图回调"""
        if rect.width() < 5 or rect.height() < 5:
            return
        from PIL import ImageGrab
        # 转换物理坐标
        dpr = self.devicePixelRatio()
        phys_rect = (
            int(rect.left() * dpr),
            int(rect.top() * dpr),
            int(rect.right() * dpr),
            int(rect.bottom() * dpr),
        )
        img = ImageGrab.grab(bbox=phys_rect)
        # 不用中文文件名 (OpenCV 不认中文路径,会导致后续 pyautogui 报错)
        name = f"wf_{int(time.time())}.png"
        out = Path("samples") / name
        out.parent.mkdir(exist_ok=True)
        img.save(str(out))
        self.image_path_edit.setText(str(out))
        self._update_image_preview()
        self._append_log(f"截图已保存: {out}")

    def _browse_template(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择模板图片", "samples", "PNG (*.png)")
        if path:
            self.image_path_edit.setText(path)
            self._update_image_preview()

    def _update_image_preview(self):
        path = self.image_path_edit.text().strip()
        # 相对路径转绝对
        if path and not Path(path).is_absolute():
            path = str((Path(".") / path).resolve())
        if path and Path(path).exists():
            from PySide6.QtGui import QPixmap
            pix = QPixmap(path)
            if pix.isNull():
                self.image_preview.setText("(图片加载失败)")
                return
            # 按比例缩放适应预览区域 (高度 120, 宽度按比例)
            target_h = 120
            if pix.height() > target_h:
                pix = pix.scaledToHeight(target_h, Qt.SmoothTransformation)
            self.image_preview.setPixmap(pix)
            self.image_preview.setText("")
        else:
            self.image_preview.setPixmap(QPixmap())  # 清除
            self.image_preview.setText("(无预览)")

    def _new_workflow(self):
        name, ok = QInputDialog.getText(self, "新建工作流", "工作流名称:")
        if ok and name.strip():
            name = name.strip()
            if name in self.workflows:
                QMessageBox.warning(self, "提示", "工作流名称已存在")
                return
            self.workflows[name] = {"name": name, "description": "", "steps": []}
            self._save_to_file()
            self._refresh_wf_list()

    def _del_workflow(self):
        row = self.wf_list.currentRow()
        if row < 0:
            return
        name = self.wf_list.item(row).text()
        if QMessageBox.question(self, "确认", f"删除工作流 {name}?") == QMessageBox.Yes:
            del self.workflows[name]
            self._save_to_file()
            self._refresh_wf_list()

    def _save_workflow_file(self):
        self._save_to_file()
        self._append_log("工作流已保存到 workflows.json")

    def _add_step(self):
        if not self._current_workflow:
            QMessageBox.warning(self, "提示", "请先选择工作流")
            return
        new_step = {
            "type": "wait",
            "name": "新步骤",
            "params": {"seconds": 2},
            "enabled": True
        }
        self._current_steps.append(new_step)
        self.workflows[self._current_workflow]["steps"] = list(self._current_steps)
        self._save_to_file()
        self._refresh_step_list()

    def _del_step(self):
        row = self.step_list.currentRow()
        if row < 0 or row >= len(self._current_steps):
            return
        self._current_steps.pop(row)
        if self._current_workflow and self._current_workflow in self.workflows:
            self.workflows[self._current_workflow]["steps"] = list(self._current_steps)
            self._save_to_file()
        self._refresh_step_list()

    def _up_step(self):
        row = self.step_list.currentRow()
        if row <= 0 or row >= len(self._current_steps):
            return
        self._current_steps[row-1], self._current_steps[row] = self._current_steps[row], self._current_steps[row-1]
        if self._current_workflow in self.workflows:
            self.workflows[self._current_workflow]["steps"] = list(self._current_steps)
            self._save_to_file()
        self._refresh_step_list()
        self.step_list.setCurrentRow(row-1)

    def _down_step(self):
        row = self.step_list.currentRow()
        if row < 0 or row >= len(self._current_steps) - 1:
            return
        self._current_steps[row+1], self._current_steps[row] = self._current_steps[row], self._current_steps[row+1]
        if self._current_workflow in self.workflows:
            self.workflows[self._current_workflow]["steps"] = list(self._current_steps)
            self._save_to_file()
        self._refresh_step_list()
        self.step_list.setCurrentRow(row+1)

    def _save_step(self):
        row = self.step_list.currentRow()
        if row < 0 or row >= len(self._current_steps):
            return
        step = self._current_steps[row]
        step["type"] = self.step_type_combo.currentData()
        step["name"] = self.step_name_edit.text() or step["type"]
        step["enabled"] = self.step_enabled.isChecked()
        # 根据类型保存参数
        if step["type"] == "launch_app":
            step["params"] = {"path": self.launch_combo.currentData() or ""}
        elif step["type"] == "wait":
            step["params"] = {"seconds": self.wait_spin.value()}
        elif step["type"] == "click_image":
            step["params"] = {
                "template": self.image_path_edit.text(),
                "confidence": self.conf_spin.value() / 100.0,
                "show_desktop": self.show_desktop_chk.isChecked(),
                "click_type": self.click_type_combo.currentData()
            }
        elif step["type"] == "key_press":
            step["params"] = {"keys": self.key_edit.text()}
        elif step["type"] == "click_coords":
            step["params"] = {
                "x": self.x_spin.value(),
                "y": self.y_spin.value(),
                "click_type": self.click_combo.currentData()
            }
        elif step["type"] == "search_file":
            step["params"] = {
                "query": self.search_query_edit.text(),
                "path": self.search_path_edit.text(),
                "limit": self.search_limit_spin.value(),
                "action": self.search_action_combo.currentData(),
            }
        wf_name = self._current_workflow
        if wf_name in self.workflows:
            self.workflows[wf_name]["steps"] = list(self._current_steps)
            self._save_to_file()
        self._refresh_step_list()
        self._append_log(f"步骤已保存: {step['name']}")

    def _run_workflow(self):
        row = self.wf_list.currentRow()
        if row < 0:
            QMessageBox.warning(self, "提示", "请先选择工作流")
            return
        name = self.wf_list.item(row).text()
        wf = self.workflows.get(name, {})
        if not wf.get("steps"):
            QMessageBox.warning(self, "提示", "工作流没有步骤")
            return
        self.btn_run_wf.setEnabled(False)
        self.btn_stop_wf.setEnabled(True)
        self.worker = WorkflowWorker(wf)
        self.worker.log_signal.connect(self._on_worker_log)
        self.worker.finished_signal.connect(self._on_worker_done)
        self.worker.start()

    def _stop_workflow(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(2000)
            self._on_worker_log("已请求停止")
        self.btn_run_wf.setEnabled(True)
        self.btn_stop_wf.setEnabled(False)

    def _on_worker_log(self, msg):
        if self.parent_window and hasattr(self.parent_window, '_append_log'):
            self.parent_window._append_log(msg)

    def _on_worker_done(self, ok, msg):
        self.btn_run_wf.setEnabled(True)
        self.btn_stop_wf.setEnabled(False)
        if self.parent_window and hasattr(self.parent_window, '_append_log'):
            prefix = "OK" if ok else "FAIL"
            self.parent_window._append_log(f"[{prefix}] {msg}")

    def _append_log(self, msg):
        if self.parent_window and hasattr(self.parent_window, '_append_log'):
            self.parent_window._append_log(msg)
