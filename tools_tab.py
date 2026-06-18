"""
工具标签页 - 集中管理 MCP server 等系统工具
=============================================

包含:
- MCP Server 控制 (启动/停止)
- MCP Server 工具简介
- 系统设置 (开机启动 / 默认后台运行)
- 启动器信息 (桌面快捷方式)
"""
from __future__ import annotations

# Windows GBK 兼容: 强制 UTF-8 输出
import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import os
import json
import subprocess
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGroupBox, QTextEdit, QFrame, QScrollArea, QCheckBox, QMessageBox, QComboBox
)
from i18n import t

# 复用父项目的运行时目录解析
try:
    from desktop_auto import RUNTIME_DIR
except Exception:
    RUNTIME_DIR = Path(__file__).parent

# 开机启动管理
try:
    from autostart import (
        is_autostart_enabled, enable_autostart, disable_autostart,
        get_autostart_command,
    )
    _AUTOSTART_OK = True
except Exception:
    _AUTOSTART_OK = False


CONFIG_FILE = RUNTIME_DIR / "config.json"


# 5 个 MCP 工具的简介
MCP_TOOLS_DOCS = [
    {
        "name": "list_workflows",
        "title": "列出工作流",
        "params": "无",
        "description": "返回所有已配置的工作流及其步骤数。",
        "example": '{"method": "tools/call", "params": {"name": "list_workflows"}}',
    },
    {
        "name": "list_shortcuts",
        "title": "列出桌面快捷方式",
        "params": "无",
        "description": "扫描桌面 .lnk 文件,返回名称、目标路径、是否存在等信息。",
        "example": '{"method": "tools/call", "params": {"name": "list_shortcuts"}}',
    },
    {
        "name": "run_workflow",
        "title": "执行工作流",
        "params": '{"name": "工作流名称"}',
        "description": "按顺序执行工作流的每个步骤 (启动应用、点击、等待、按键等)。",
        "example": '{"method": "tools/call", "params": {"name": "run_workflow", "arguments": {"name": "zzz日常"}}}',
    },
    {
        "name": "launch_shortcut",
        "title": "启动快捷方式",
        "params": '{"name": "应用名称"}',
        "description": "按名称启动桌面快捷方式 (必须存在 .lnk 文件)。",
        "example": '{"method": "tools/call", "params": {"name": "launch_shortcut", "arguments": {"name": "Chrome"}}}',
    },
    {
        "name": "search_local_files",
        "title": "Everything 全盘搜索",
        "params": '{"query": "搜索词", "limit": 50, "path": "可选限定目录"}',
        "description": "通过 Everything HTTP 搜索本地文件。支持通配符 (如 '4月 png|jpg')。\n"
                       "⚠️ 需要本机安装并运行 Everything,且 HTTP server 关闭鉴权。",
        "example": '{"method": "tools/call", "params": {"name": "search_local_files", "arguments": {"query": "4月货款 png|jpg", "limit": 20}}}',
    },
]


class ToolsTab(QWidget):
    """
    工具标签页 - MCP server 控制 + 工具简介
    """

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.parent_window = parent
        self.mcp_proc: Optional[subprocess.Popen] = None

        self._build_ui()
        # 启动时立即同步检查状态 (不走 QTimer 延迟, 避免“检测中”闪现)
        self._refresh_mcp_status()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # 滚动区域 (放所有内容)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        scroll.setWidget(inner)
        iv = QVBoxLayout(inner)
        iv.setContentsMargins(4, 4, 4, 4)
        iv.setSpacing(10)

        # ===== 系统设置 (开机启动 / 后台运行) =====
        iv.addWidget(self._build_system_box())

        # ===== 语言设置 =====
        iv.addWidget(self._build_language_box())

        # ===== MCP Server 控制 =====
        iv.addWidget(self._build_mcp_box())

        # ===== MCP 工具简介 =====
        iv.addWidget(self._build_mcp_docs_box())

        # ===== 启动器信息 =====
        iv.addWidget(self._build_launcher_box())

        iv.addStretch()
        layout.addWidget(scroll)

    def _build_system_box(self) -> QGroupBox:
        """系统设置:开机启动 + 默认后台运行"""
        from i18n import t
        gb = QGroupBox(t("tools_system_settings"))
        v = QVBoxLayout(gb)
        v.setContentsMargins(10, 6, 10, 10)
        v.setSpacing(8)

        # 开机启动
        self.chk_autostart = QCheckBox(t("tools_chk_autostart"))
        self.chk_autostart.setStyleSheet("font-weight: bold; font-size: 12px; padding: 4px;")
        self.chk_autostart.toggled.connect(self._on_autostart_toggle)
        v.addWidget(self.chk_autostart)

        self.lbl_autostart_status = QLabel(t("tools_status_not_started"))
        self.lbl_autostart_status.setStyleSheet("color: #666; font-size: 11px; padding: 0 8px 4px 24px;")
        self.lbl_autostart_status.setWordWrap(True)
        v.addWidget(self.lbl_autostart_status)

        # 分割线
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("color: #e5e7eb;")
        v.addWidget(line)

        # 默认后台运行
        self.chk_start_bg = QCheckBox(t("tools_chk_start_bg"))
        self.chk_start_bg.setStyleSheet("font-weight: bold; font-size: 12px; padding: 4px;")
        self.chk_start_bg.toggled.connect(self._on_start_bg_toggle)
        v.addWidget(self.chk_start_bg)

        self.lbl_start_bg_status = QLabel(t("tools_status_not_enabled"))
        self.lbl_start_bg_status.setStyleSheet("color: #666; font-size: 11px; padding: 0 8px 4px 24px;")
        self.lbl_start_bg_status.setWordWrap(True)
        v.addWidget(self.lbl_start_bg_status)

        # 分割线
        line2 = QFrame()
        line2.setFrameShape(QFrame.HLine)
        line2.setFrameShadow(QFrame.Sunken)
        line2.setStyleSheet("color: #e5e7eb;")
        v.addWidget(line2)

        # 显示操作日志
        self.chk_show_log = QCheckBox(t("tools_chk_show_log"))
        self.chk_show_log.setStyleSheet("font-weight: bold; font-size: 12px; padding: 4px;")
        self.chk_show_log.setChecked(True)
        self.chk_show_log.toggled.connect(self._on_show_log_toggle)
        v.addWidget(self.chk_show_log)

        # 测试/立即隐藏按钮
        btn_row = QHBoxLayout()
        self.btn_hide_to_tray = QPushButton(t("tools_btn_hide_to_tray"))
        self.btn_hide_to_tray.setStyleSheet(
            "QPushButton { padding: 6px 10px; }"
            "QPushButton:hover { background:#e0e7ff; }"
        )
        self.btn_hide_to_tray.clicked.connect(self._hide_main_to_tray)
        btn_row.addWidget(self.btn_hide_to_tray)

        self.btn_refresh_sys = QPushButton(t("tools_btn_refresh"))
        self.btn_refresh_sys.setStyleSheet("padding: 6px 10px;")
        self.btn_refresh_sys.clicked.connect(self._refresh_system_status)
        btn_row.addWidget(self.btn_refresh_sys)

        btn_row.addStretch()
        v.addLayout(btn_row)

        # 提示
        hint = QLabel(t("tools_hint"))
        hint.setStyleSheet("color: #888; font-size: 11px; padding: 4px 0 0 0;")
        hint.setWordWrap(True)
        v.addWidget(hint)


        # ----- 危险操作 -----
        line3 = QFrame()
        line3.setFrameShape(QFrame.HLine)
        line3.setFrameShadow(QFrame.Sunken)
        line3.setStyleSheet("color: #fca5a5;")
        v.addWidget(line3)

        danger_box = QGroupBox(t("tools_danger_box"))
        danger_box.setStyleSheet(
            "QGroupBox { font-weight: bold; color: #dc2626; "
            "border: 1px solid #fca5a5; border-radius: 4px; margin-top: 6px; padding: 2px; }"
        )
        dv = QVBoxLayout(danger_box)
        dv.setContentsMargins(8, 4, 8, 6)

        warn_label = QLabel(t("tools_danger_warn"))
        warn_label.setStyleSheet(
            "color: #991b1b; font-size: 11px; padding: 4px; "
            "background: #fef2f2; border-radius: 4px; line-height: 1.6;"
        )
        warn_label.setWordWrap(True)
        dv.addWidget(warn_label)

        self.btn_uninstall = QPushButton(t("tools_btn_uninstall"))
        self.btn_uninstall.setStyleSheet(
            "QPushButton { background: #dc2626; color: white; font-weight: bold; "
            "padding: 7px 14px; border-radius: 4px; }"
            "QPushButton:hover { background: #b91c1c; }"
        )
        self.btn_uninstall.clicked.connect(self._do_uninstall)
        dv.addWidget(self.btn_uninstall)

        v.addWidget(danger_box)

        # 启动时同步加载状态 (不走延迟)
        self._refresh_system_status()
        return gb

    def _build_language_box(self) -> QGroupBox:
        """语言切换区"""
        from i18n import t, get_lang
        gb = QGroupBox(t("tools_language"))
        v = QVBoxLayout(gb)
        v.setContentsMargins(10, 6, 10, 10)
        v.setSpacing(8)

        row = QHBoxLayout()
        row.addWidget(QLabel(t("tools_lang_label")))
        self.lang_combo = QComboBox()
        self.lang_combo.addItem(t("tools_lang_zh"), "zh")
        self.lang_combo.addItem(t("tools_lang_en"), "en")
        cur = get_lang()
        idx = self.lang_combo.findData(cur)
        if idx >= 0:
            self.lang_combo.setCurrentIndex(idx)
        self.lang_combo.currentIndexChanged.connect(self._on_lang_change)
        row.addWidget(self.lang_combo)
        row.addStretch()
        v.addLayout(row)

        hint = QLabel(t("tools_lang_apply_hint"))
        hint.setStyleSheet("color: #666; font-size: 11px;")
        v.addWidget(hint)
        return gb

    def _on_lang_change(self, idx):
        """语言切换回调 - 保存后提示重启"""
        from i18n import t, set_lang
        new_lang = self.lang_combo.itemData(idx)
        if not new_lang:
            return
        try:
            set_lang(new_lang)
            lang_name = self.lang_combo.itemText(idx)
            # 同时推送气泡通知（同步到 AI 对话 tab）
            main_win = self.parent()
            if main_win and hasattr(main_win, "context_tab") and main_win.context_tab:
                from context_toast import ToastIntent
                intent = ToastIntent(
                    intent="\U0001f310 " + lang_name,
                    message=t("msg_lang_changed_body", lang=lang_name),
                    suggested_action="",
                    action_param="",
                )
                main_win.context_tab._toast_manager.show_toast(intent)
                main_win.context_tab.toast_broadcast.emit(intent)
            QMessageBox.information(
                self,
                t("msg_lang_changed_title"),
                t("msg_lang_changed_body", lang=lang_name),
            )
        except Exception as e:
            QMessageBox.warning(self, t("msg_error"), str(e))

    def _build_mcp_box(self) -> QGroupBox:
        """MCP Server 控制区"""
        from i18n import t

        mcp_box = QGroupBox(t("tools_mcp_server"))
        mv = QVBoxLayout(mcp_box)

        # 状态显示 (初始为"未启动", 创建后会同步刷新)
        self.lbl_mcp_status = QLabel(t("tools_status_not_started"))
        self.lbl_mcp_status.setStyleSheet("color: #666; font-size: 12px; padding: 4px;")
        mv.addWidget(self.lbl_mcp_status)

        # 按钮
        mcp_btn_row = QHBoxLayout()
        self.btn_start_mcp = QPushButton(t("tools_btn_start_mcp"))
        self.btn_start_mcp.setStyleSheet(
            "QPushButton { background:#10b981; color:white; font-weight:bold; padding:8px; }"
            "QPushButton:hover { background:#059669; }"
            "QPushButton:disabled { background:#9ca3af; }"
        )
        self.btn_start_mcp.clicked.connect(self._start_mcp_server)
        mcp_btn_row.addWidget(self.btn_start_mcp)

        self.btn_stop_mcp = QPushButton(t("tools_btn_stop_mcp"))
        self.btn_stop_mcp.setStyleSheet(
            "QPushButton { background:#dc2626; color:white; font-weight:bold; padding:8px; }"
            "QPushButton:hover { background:#b91c1c; }"
            "QPushButton:disabled { background:#9ca3af; }"
        )
        self.btn_stop_mcp.setEnabled(False)
        self.btn_stop_mcp.clicked.connect(self._stop_mcp_server)
        mcp_btn_row.addWidget(self.btn_stop_mcp)
        mv.addLayout(mcp_btn_row)

        # 配置示例
        cfg_label = QLabel(t("tools_mcp_cfg_label"))
        cfg_label.setStyleSheet("color: #555; font-weight: bold; padding: 4px 0 2px 0;")
        mv.addWidget(cfg_label)
        cfg_text = QTextEdit()
        cfg_text.setReadOnly(True)
        cfg_text.setMaximumHeight(120)
        cfg_text.setStyleSheet("font-family: Consolas, monospace; font-size: 11px; background:#f9fafb;")
        # 自动填当前 EXE 路径
        exe_path = self._get_exe_path()
        cfg_text.setPlainText(
            '{\n'
            '  "mcpServers": {\n'
            '    "desktop-auto": {\n'
            f'      "command": "{exe_path}",\n'
            '      "args": ["--mcp"]\n'
            '    }\n'
            '  }\n'
            '}'
        )
        mv.addWidget(cfg_text)

        return mcp_box

    def _build_mcp_docs_box(self) -> QGroupBox:
        """MCP 工具简介区 (可展开/折叠)"""
        from i18n import t

        self.mcp_docs_expanded = True
        docs_box = QGroupBox()
        dv = QVBoxLayout(docs_box)
        dv.setContentsMargins(8, 4, 8, 8)

        # 标题 + 折叠按钮
        header_row = QHBoxLayout()
        title = QLabel(t("tools_mcp_docs_title", n=len(MCP_TOOLS_DOCS)))
        title.setStyleSheet("font-weight: bold; font-size: 13px; color: #1e40af;")
        header_row.addWidget(title)
        header_row.addStretch()
        self.btn_toggle_docs = QPushButton(t("tools_btn_collapse"))
        self.btn_toggle_docs.setFixedWidth(80)
        self.btn_toggle_docs.setStyleSheet(
            "QPushButton { padding: 4px 8px; font-size: 11px; }"
            "QPushButton:hover { background:#e0e7ff; }"
        )
        self.btn_toggle_docs.clicked.connect(self._toggle_mcp_docs)
        header_row.addWidget(self.btn_toggle_docs)
        dv.addLayout(header_row)

        # 简介容器 (可隐藏)
        self.mcp_docs_container = QWidget()
        container_layout = QVBoxLayout(self.mcp_docs_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(6)

        for tool in MCP_TOOLS_DOCS:
            tool_frame = QFrame()
            tool_frame.setFrameShape(QFrame.StyledPanel)
            tool_frame.setStyleSheet(
                "QFrame { background:#f9fafb; border:1px solid #e5e7eb; border-radius:4px; padding:6px; }"
            )
            tf = QVBoxLayout(tool_frame)
            tf.setContentsMargins(8, 6, 8, 6)

            # 标题
            title_lbl = QLabel(f"<b>{tool['name']}</b> - {tool['title']}")
            title_lbl.setStyleSheet("color: #2563eb; font-size: 12px;")
            tf.addWidget(title_lbl)

            # 参数
            param = QLabel(t("tools_mcp_param_label") + f" <code>{tool['params']}</code>")
            param.setStyleSheet("color: #666; font-size: 11px; padding: 2px 0;")
            param.setTextFormat(Qt.RichText)
            tf.addWidget(param)

            # 描述
            desc = QLabel(tool['description'])
            desc.setStyleSheet("color: #333; font-size: 11px; padding: 2px 0;")
            desc.setWordWrap(True)
            tf.addWidget(desc)

            # 示例
            ex_label = QLabel(t("tools_mcp_example_label"))
            ex_label.setStyleSheet("color: #888; font-size: 10px; padding: 2px 0 0 0;")
            tf.addWidget(ex_label)
            ex = QLabel(f"<code>{tool['example']}</code>")
            ex.setStyleSheet("color: #059669; font-size: 10px; font-family:Consolas,monospace;")
            ex.setTextFormat(Qt.RichText)
            ex.setWordWrap(True)
            tf.addWidget(ex)

            container_layout.addWidget(tool_frame)

        dv.addWidget(self.mcp_docs_container)
        return docs_box

    def _toggle_mcp_docs(self) -> None:
        """展开/折叠 MCP 简介"""
        from i18n import t
        if self.mcp_docs_expanded:
            self.mcp_docs_container.setVisible(False)
            self.btn_toggle_docs.setText(t("tools_btn_expand"))
            self.mcp_docs_expanded = False
        else:
            self.mcp_docs_container.setVisible(True)
            self.btn_toggle_docs.setText(t("tools_btn_collapse"))
            self.mcp_docs_expanded = True

    def _build_launcher_box(self) -> QGroupBox:
        """启动器信息"""
        from i18n import t

        lb = QGroupBox(t("tools_launcher_title"))
        lv = QVBoxLayout(lb)

        info = QLabel(t("tools_launcher_info"))
        info.setStyleSheet("color: #333; font-size: 12px; padding: 4px;")
        info.setWordWrap(True)
        lv.addWidget(info)

        btn_row = QHBoxLayout()
        btn_install = QPushButton(t("tools_btn_install_shortcut"))
        btn_install.setStyleSheet("padding: 6px;")
        btn_install.clicked.connect(self._install_launcher_shortcut)
        btn_row.addWidget(btn_install)

        btn_uninstall = QPushButton(t("tools_btn_uninstall_shortcut"))
        btn_uninstall.setStyleSheet("padding: 6px;")
        btn_uninstall.clicked.connect(self._uninstall_launcher_shortcut)
        btn_row.addWidget(btn_uninstall)
        lv.addLayout(btn_row)

        return lb

    # ------------------------------------------------------------------
    # 系统设置:开机启动 / 默认后台运行
    # ------------------------------------------------------------------
    def _load_global_config(self) -> dict:
        """加载全局 config.json"""
        if not CONFIG_FILE.exists():
            return {}
        try:
            return json.loads(CONFIG_FILE.read_text("utf-8"))
        except Exception:
            return {}

    def _save_global_config(self, data: dict) -> None:
        """保存全局 config.json"""
        try:
            CONFIG_FILE.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                "utf-8",
            )
        except Exception as e:
            QMessageBox.warning(self, "提示", f"保存配置失败:\n{e}")

    def _refresh_system_status(self) -> None:
        """刷新开机启动 / 后台运行 状态显示"""
        from i18n import t
        # 开机启动
        if _AUTOSTART_OK:
            enabled = is_autostart_enabled()
            self.chk_autostart.blockSignals(True)
            self.chk_autostart.setChecked(enabled)
            self.chk_autostart.blockSignals(False)
            if enabled:
                cmd = get_autostart_command() or ""
                self.lbl_autostart_status.setText(t("tools_status_autostart_enabled", cmd=cmd))
                self.lbl_autostart_status.setStyleSheet("color: #16a34a; font-size: 11px; padding: 0 8px 4px 24px;")
            else:
                self.lbl_autostart_status.setText(t("tools_status_autostart_disabled"))
                self.lbl_autostart_status.setStyleSheet("color: #666; font-size: 11px; padding: 0 8px 4px 24px;")
        else:
            self.chk_autostart.setEnabled(False)
            self.lbl_autostart_status.setText(t("tools_status_autostart_unavailable"))
            self.lbl_autostart_status.setStyleSheet("color: #d97706; font-size: 11px; padding: 0 8px 4px 24px;")

        # 默认后台运行
        cfg = self._load_global_config()
        bg = bool(cfg.get("start_in_background", False))
        self.chk_start_bg.blockSignals(True)
        self.chk_start_bg.setChecked(bg)
        self.chk_start_bg.blockSignals(False)
        if bg:
            self.lbl_start_bg_status.setText(t("tools_status_startbg_enabled"))
            self.lbl_start_bg_status.setStyleSheet("color: #16a34a; font-size: 11px; padding: 0 8px 4px 24px;")
        else:
            self.lbl_start_bg_status.setText(t("tools_status_startbg_disabled"))
            self.lbl_start_bg_status.setStyleSheet("color: #666; font-size: 11px; padding: 0 8px 4px 24px;")

    def _do_uninstall(self):
        from i18n import t
        reply = QMessageBox.warning(
            self,
            t("tools_uninstall_confirm_title"),
            t("tools_uninstall_confirm_body"),
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Ok:
            return
        import sys as _sys
        exe_path = _sys.executable
        data_dir = str(Path.home() / "\u684c\u9762\u81ea\u52a8\u5316\u52a9\u624b")
        tmp_dir = os.environ.get("TEMP", "C:\\Windows\\Temp")
        batch_path = Path(tmp_dir) / ("uninstall_desktop_auto_" + str(os.getpid()) + ".bat")
        exe_name = Path(exe_path).name

        _t = {
            "exe_name": exe_name,
            "exe_path": exe_path,
            "data_dir": data_dir,
        }
        _batch = (
            "@echo off\n"
            "chcp 65001 >nul\n"
            "echo \u6b63\u5728\u7b49\u5f85\u7a0b\u5e8f\u9000\u51fa...\n"
            ":wait_loop\n"
            'tasklist /FI "IMAGENAME eq %(exe_name)s" 2>nul | find /I "%(exe_name)s" >nul\n'
            "if %%errorlevel%%==0 (\n"
            "    timeout /t 2 /nobreak >nul\n"
            "    goto wait_loop\n"
            ")\n"
            "echo \u6b63\u5728\u5220\u9664 exe...\n"
            'del /f /q "%(exe_path)s" 2>nul\n'
            "echo \u6b63\u5728\u5220\u9664\u7528\u6237\u6570\u636e\u76ee\u5f55...\n"
            'rmdir /s /q "%(data_dir)s" 2>nul\n'
            "echo \u5378\u8f7d\u5b8c\u6210.\n"
            'del "%%~f0"\n'
        ) % _t

        try:
            batch_path.write_text(_batch, encoding="utf-8")
        except Exception as e:
            QMessageBox.critical(self, "\u5378\u8f7d\u5931\u8d25", "\u65e0\u6cd5\u521b\u5efa\u5378\u8f7d\u811a\u672c\uff1a" + str(e))
            return
        try:
            subprocess.Popen(["cmd.exe", "/c", str(batch_path)], creationflags=0x08000000)
        except Exception:
            pass
        from PySide6.QtWidgets import QApplication
        QApplication.quit()

    def _on_autostart_toggle(self, checked: bool) -> None:
        """开关 开机启动"""
        if not _AUTOSTART_OK:
            QMessageBox.warning(self, "提示", "autostart 模块不可用")
            return
        if checked:
            ok, msg = enable_autostart()
        else:
            ok, msg = disable_autostart()
        # 同步推到全局日志
        try:
            from log_bus import log_bus
            log_bus.emit(f"[工具] 开机启动 {'启用' if checked else '停用'}: {msg.splitlines()[0] if msg else ''}")
        except Exception:
            pass
        # 显示结果到状态标签
        if ok:
            self.lbl_autostart_status.setText(f"状态: {msg}")
            self.lbl_autostart_status.setStyleSheet("color: #16a34a; font-size: 11px; padding: 0 8px 4px 24px;")
        else:
            self.lbl_autostart_status.setText(f"状态: {msg}")
            self.lbl_autostart_status.setStyleSheet("color: #dc2626; font-size: 11px; padding: 0 8px 4px 24px;")
            # 失败时恢复勾选状态
            self.chk_autostart.blockSignals(True)
            self.chk_autostart.setChecked(not checked)
            self.chk_autostart.blockSignals(False)
            QMessageBox.warning(self, "提示", msg)
        # 刷新状态
        QTimer.singleShot(100, self._refresh_system_status)

    def _on_start_bg_toggle(self, checked: bool) -> None:
        """开关 默认后台运行"""
        cfg = self._load_global_config()
        cfg["start_in_background"] = bool(checked)
        self._save_global_config(cfg)
        try:
            from log_bus import log_bus
            log_bus.emit(f"[工具] 默认后台运行 {'启用' if checked else '停用'}")
        except Exception:
            pass
        QTimer.singleShot(100, self._refresh_system_status)

    def _on_show_log_toggle(self, checked: bool) -> None:
        """开关 显示/隐藏底部操作日志"""
        main_win = self.window()
        if main_win is None or not isinstance(main_win, QWidget):
            return
        main_win.log_view.setVisible(checked)

    def _hide_main_to_tray(self) -> None:
        """点击 "立即隐藏到托盘" 按钮"""
        main_win = self.window()
        if main_win is None or not isinstance(main_win, QWidget):
            QMessageBox.information(self, "提示", "找不到主窗口")
            return
        # 触发 closeEvent (会隐藏到托盘)
        main_win.close()

    # ------------------------------------------------------------------
    # MCP Server 控制
    # ------------------------------------------------------------------
    def _find_latest_exe(self) -> Path | None:
        """开发模式下查找 dist 中最新的 EXE。"""
        dist = Path(__file__).parent / "dist"
        exes = sorted(dist.glob("*.exe"), key=lambda p: p.stat().st_mtime, reverse=True)
        return exes[0] if exes else None

    def _get_exe_path_raw(self) -> str:
        """获取 EXE 路径 (原始路径,用于创建快捷方式/启动进程)。"""
        if getattr(sys, 'frozen', False):
            return sys.executable
        exe = self._find_latest_exe()
        return str(exe) if exe else ""

    def _get_exe_path(self) -> str:
        """获取 EXE 路径 (显示用)。"""
        exe = self._get_exe_path_raw()
        return exe.replace("/", "\\\\") if exe else "<需要打包 EXE>"

    def _start_mcp_server(self) -> None:
        """启动 MCP server (子进程方式)"""
        if self.mcp_proc and self.mcp_proc.poll() is None:
            self.lbl_mcp_status.setText(f"状态: 已在运行 (PID={self.mcp_proc.pid})")
            return

        exe = self._get_exe_path_raw()
        if not exe:
            self.lbl_mcp_status.setText("状态: ❌ 没找到 EXE, 请先打包")
            return

        try:
            self.mcp_proc = subprocess.Popen(
                [exe, "--mcp"],
                cwd=str(Path(exe).parent),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            )
            self.lbl_mcp_status.setText(
                f"状态: ✅ 启动成功 (PID={self.mcp_proc.pid})\n"
                f"📍 AI 客户端可通过 stdio 连接此进程"
            )
            self.lbl_mcp_status.setStyleSheet("color: #16a34a; font-size: 12px; padding: 4px;")
            self.btn_start_mcp.setEnabled(False)
            self.btn_stop_mcp.setEnabled(True)
            try:
                from log_bus import log_bus
                log_bus.emit(f"[工具] MCP server 启动成功 PID={self.mcp_proc.pid}")
            except Exception:
                pass
            # 定时检查状态
            QTimer.singleShot(2000, self._refresh_mcp_status)
        except Exception as e:
            self.lbl_mcp_status.setText(f"状态: ❌ 启动失败: {e}")
            self.lbl_mcp_status.setStyleSheet("color: #dc2626; font-size: 12px; padding: 4px;")
            try:
                from log_bus import log_bus
                log_bus.emit(f"[工具] MCP server 启动失败: {e}")
            except Exception:
                pass

    def _stop_mcp_server(self) -> None:
        """停止 MCP server 子进程"""
        if not self.mcp_proc or self.mcp_proc.poll() is not None:
            self.lbl_mcp_status.setText("状态: 未运行")
            self.lbl_mcp_status.setStyleSheet("color: #666; font-size: 12px; padding: 4px;")
            self.btn_start_mcp.setEnabled(True)
            self.btn_stop_mcp.setEnabled(False)
            return

        try:
            self.mcp_proc.terminate()
            try:
                self.mcp_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.mcp_proc.kill()
            self.mcp_proc = None
            self.lbl_mcp_status.setText("状态: ⏹ 已停止")
            self.lbl_mcp_status.setStyleSheet("color: #666; font-size: 12px; padding: 4px;")
            self.btn_start_mcp.setEnabled(True)
            self.btn_stop_mcp.setEnabled(False)
        except Exception as e:
            self.lbl_mcp_status.setText(f"状态: ❌ 停止失败: {e}")
            self.lbl_mcp_status.setStyleSheet("color: #dc2626; font-size: 12px; padding: 4px;")

    def _refresh_mcp_status(self) -> None:
        """检查 MCP 进程是否还在"""
        if self.mcp_proc and self.mcp_proc.poll() is None:
            self.lbl_mcp_status.setText(f"状态: ✅ 运行中 (PID={self.mcp_proc.pid})")
            self.lbl_mcp_status.setStyleSheet("color: #16a34a; font-size: 12px; padding: 4px;")
            self.btn_start_mcp.setEnabled(False)
            self.btn_stop_mcp.setEnabled(True)
        else:
            self.lbl_mcp_status.setText("状态: 未启动")
            self.lbl_mcp_status.setStyleSheet("color: #666; font-size: 12px; padding: 4px;")
            self.btn_start_mcp.setEnabled(True)
            self.btn_stop_mcp.setEnabled(False)

    # ------------------------------------------------------------------
    # 启动器快捷方式
    # ------------------------------------------------------------------
    def _install_launcher_shortcut(self) -> None:
        """创建桌面快捷方式 (直接指向 EXE + --silent-task)。"""
        try:
            import win32com.client
            from PySide6.QtWidgets import QMessageBox

            exe_path = self._get_exe_path_raw()
            if not exe_path:
                self.lbl_mcp_status.setText("状态: ❌ 没找到 EXE, 请先打包")
                QMessageBox.warning(self, "提示", "没找到 EXE,请先打包")
                return

            desktop = Path.home() / "Desktop"
            icon_path = Path(__file__).parent / "app_icon.ico"
            shortcut_path = desktop / "桌面助手.lnk"

            shell = win32com.client.Dispatch("WScript.Shell")
            sc = shell.CreateShortCut(str(shortcut_path))
            sc.TargetPath = exe_path
            sc.Arguments = "--silent-task"
            sc.WorkingDirectory = str(Path(exe_path).parent)
            sc.IconLocation = str(icon_path) if icon_path.exists() else exe_path
            sc.Description = t("app_title")
            sc.WindowStyle = 1
            sc.save()

            self.lbl_mcp_status.setText("状态: ✅ 桌面快捷方式已创建")
            QMessageBox.information(
                self, "成功",
                t("tools_shortcut_created_msg")
            )
        except Exception as e:
            self.lbl_mcp_status.setText(f"状态: ❌ 创建失败: {e}")
            try:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.critical(self, "错误", f"创建快捷方式失败:\n{e}")
            except Exception:
                pass

    def _uninstall_launcher_shortcut(self) -> None:
        """删除桌面快捷方式。"""
        try:
            from PySide6.QtWidgets import QMessageBox
            shortcut_path = Path.home() / "Desktop" / "桌面助手.lnk"
            if shortcut_path.exists():
                shortcut_path.unlink()
                self.lbl_mcp_status.setText("状态: 🗑 桌面快捷方式已删除")
                QMessageBox.information(self, "成功", "桌面快捷方式已删除")
            else:
                self.lbl_mcp_status.setText("状态: i️ 快捷方式不存在")
                QMessageBox.information(self, "提示", "桌面快捷方式不存在")
        except Exception as e:
            self.lbl_mcp_status.setText(f"状态: ❌ 删除失败: {e}")
