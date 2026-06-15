"""
工具标签页 - 集中管理 MCP server 等系统工具
=============================================

包含:
- MCP Server 控制 (启动/停止)
- MCP Server 工具简介
- (后续可扩展: 配置导入/导出、日志查看等)
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
import subprocess
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGroupBox, QTextEdit, QFrame, QScrollArea
)


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
        # 启动时检查 MCP 状态
        QTimer.singleShot(500, self._refresh_mcp_status)

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

        # ===== MCP Server 控制 =====
        iv.addWidget(self._build_mcp_box())

        # ===== MCP 工具简介 =====
        iv.addWidget(self._build_mcp_docs_box())

        # ===== 启动器信息 =====
        iv.addWidget(self._build_launcher_box())

        iv.addStretch()
        layout.addWidget(scroll)

    def _build_mcp_box(self) -> QGroupBox:
        """MCP Server 控制区"""
        mcp_box = QGroupBox("🤖 MCP Server (AI 接入)")
        mv = QVBoxLayout(mcp_box)

        # 状态显示
        self.lbl_mcp_status = QLabel("状态: 检测中...")
        self.lbl_mcp_status.setStyleSheet("color: #666; font-size: 12px; padding: 4px;")
        mv.addWidget(self.lbl_mcp_status)

        # 按钮
        mcp_btn_row = QHBoxLayout()
        self.btn_start_mcp = QPushButton("▶ 启动 MCP Server")
        self.btn_start_mcp.setStyleSheet(
            "QPushButton { background:#10b981; color:white; font-weight:bold; padding:8px; }"
            "QPushButton:hover { background:#059669; }"
            "QPushButton:disabled { background:#9ca3af; }"
        )
        self.btn_start_mcp.clicked.connect(self._start_mcp_server)
        mcp_btn_row.addWidget(self.btn_start_mcp)

        self.btn_stop_mcp = QPushButton("⏹ 停止")
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
        cfg_label = QLabel("📋 MCP 客户端配置示例 (mcp_config.json):")
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
        self.mcp_docs_expanded = True
        docs_box = QGroupBox()
        dv = QVBoxLayout(docs_box)
        dv.setContentsMargins(8, 4, 8, 8)

        # 标题 + 折叠按钮
        header_row = QHBoxLayout()
        title = QLabel(f"📚 MCP 工具简介 (共 {len(MCP_TOOLS_DOCS)} 个)")
        title.setStyleSheet("font-weight: bold; font-size: 13px; color: #1e40af;")
        header_row.addWidget(title)
        header_row.addStretch()
        self.btn_toggle_docs = QPushButton("▲ 折叠")
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
            title_lbl = QLabel(f"<b>{tool['name']}</b> — {tool['title']}")
            title_lbl.setStyleSheet("color: #2563eb; font-size: 12px;")
            tf.addWidget(title_lbl)

            # 参数
            param = QLabel(f"参数: <code>{tool['params']}</code>")
            param.setStyleSheet("color: #666; font-size: 11px; padding: 2px 0;")
            param.setTextFormat(Qt.RichText)
            tf.addWidget(param)

            # 描述
            desc = QLabel(tool['description'])
            desc.setStyleSheet("color: #333; font-size: 11px; padding: 2px 0;")
            desc.setWordWrap(True)
            tf.addWidget(desc)

            # 示例
            ex_label = QLabel("示例:")
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
        if self.mcp_docs_expanded:
            self.mcp_docs_container.setVisible(False)
            self.btn_toggle_docs.setText("▼ 展开")
            self.mcp_docs_expanded = False
        else:
            self.mcp_docs_container.setVisible(True)
            self.btn_toggle_docs.setText("▲ 折叠")
            self.mcp_docs_expanded = True

    def _build_launcher_box(self) -> QGroupBox:
        """启动器信息"""
        lb = QGroupBox("🚀 启动器 (桌面快捷方式)")
        lv = QVBoxLayout(lb)

        info = QLabel(
            "点击桌面上 <b>「桌面助手」</b> 快捷方式,可弹出菜单选择:\n"
            "  🟢 启动 GUI\n"
            "  🟡 启动 GUI + MCP server\n"
            "  🔴 停止所有"
        )
        info.setStyleSheet("color: #333; font-size: 12px; padding: 4px;")
        info.setWordWrap(True)
        lv.addWidget(info)

        btn_row = QHBoxLayout()
        btn_install = QPushButton("📥 创建桌面快捷方式")
        btn_install.setStyleSheet("padding: 6px;")
        btn_install.clicked.connect(self._install_launcher_shortcut)
        btn_row.addWidget(btn_install)

        btn_uninstall = QPushButton("🗑 删除桌面快捷方式")
        btn_uninstall.setStyleSheet("padding: 6px;")
        btn_uninstall.clicked.connect(self._uninstall_launcher_shortcut)
        btn_row.addWidget(btn_uninstall)
        lv.addLayout(btn_row)

        return lb

    # ------------------------------------------------------------------
    # MCP Server 控制
    # ------------------------------------------------------------------
    def _get_exe_path(self) -> str:
        """获取 EXE 路径"""
        # 优先用 EXE 模式下的 sys.executable
        if getattr(sys, 'frozen', False):
            return sys.executable.replace("/", "\\\\")
        # 开发模式: 用 dist 下的 EXE
        dist = Path(__file__).parent / "dist"
        for f in dist.glob("*.exe"):
            return str(f).replace("/", "\\\\")
        return "<需要打包 EXE>"

    def _start_mcp_server(self) -> None:
        """启动 MCP server (子进程方式)"""
        if self.mcp_proc and self.mcp_proc.poll() is None:
            self.lbl_mcp_status.setText(f"状态: 已在运行 (PID={self.mcp_proc.pid})")
            return

        if getattr(sys, 'frozen', False):
            # EXE 模式
            exe = sys.executable
        else:
            # 开发模式: 找 dist 下的 EXE
            dist = Path(__file__).parent / "dist"
            exes = list(dist.glob("*.exe"))
            if not exes:
                self.lbl_mcp_status.setText("状态: ❌ 没找到 EXE, 请先打包")
                return
            exe = str(exes[0])

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
            # 定时检查状态
            QTimer.singleShot(2000, self._refresh_mcp_status)
        except Exception as e:
            self.lbl_mcp_status.setText(f"状态: ❌ 启动失败: {e}")
            self.lbl_mcp_status.setStyleSheet("color: #dc2626; font-size: 12px; padding: 4px;")

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
        """创建桌面快捷方式"""
        try:
            import subprocess as _sp
            launcher = Path(__file__).parent / "launcher.py"
            r = _sp.run(
                [sys.executable, str(launcher), "install"],
                capture_output=True, text=True, encoding="utf-8"
            )
            if r.returncode == 0:
                self.lbl_mcp_status.setText("状态: ✅ 桌面快捷方式已创建")
                # 提示
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.information(self, "成功", "桌面快捷方式已创建!\n双击「桌面助手」即可使用")
            else:
                self.lbl_mcp_status.setText(f"状态: ❌ 创建失败: {r.stderr or r.stdout}")
        except Exception as e:
            self.lbl_mcp_status.setText(f"状态: ❌ 创建失败: {e}")

    def _uninstall_launcher_shortcut(self) -> None:
        """删除桌面快捷方式"""
        try:
            import subprocess as _sp
            launcher = Path(__file__).parent / "launcher.py"
            r = _sp.run(
                [sys.executable, str(launcher), "uninstall"],
                capture_output=True, text=True, encoding="utf-8"
            )
            self.lbl_mcp_status.setText("状态: 🗑 桌面快捷方式已删除")
        except Exception as e:
            self.lbl_mcp_status.setText(f"状态: ❌ 删除失败: {e}")
