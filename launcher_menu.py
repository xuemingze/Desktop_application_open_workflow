"""
桌面自动化助手 - 启动菜单对话框
================================
点击桌面快捷方式后弹出,提供 3 个选项:
1. 启动 GUI
2. 启动 GUI + MCP server
3. 停止所有

依赖 PySide6 (项目本身就有)
"""
import sys
import subprocess
from pathlib import Path

# Windows GBK 兼容: 强制 stdout/stderr 用 UTF-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 启动 launcher.py 的同步命令
LAUNCHER = Path(__file__).parent / "launcher.py"
PYTHON_EXE = Path(sys.executable)
EXE_PATH = Path(__file__).parent / "dist" / "桌面自动化助手.exe"
ICON_PATH = Path(__file__).parent / "app_icon.ico"


def run_launcher(*args) -> int:
    """调用 launcher.py 执行命令"""
    cmd = [str(PYTHON_EXE), str(LAUNCHER), *args]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    # 把 launcher 输出回显到弹窗的 label
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return result.returncode


def show_dialog() -> str:
    """弹出选项对话框,返回用户选择的动作"""
    try:
        from PySide6.QtWidgets import (QApplication, QDialog, QVBoxLayout,
                                         QPushButton, QLabel, QHBoxLayout)
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QIcon

        app = QApplication.instance() or QApplication(sys.argv)
        app.setApplicationName("桌面助手启动器")

        dlg = QDialog()
        dlg.setWindowTitle("桌面自动化助手 - 启动器")
        dlg.setFixedSize(360, 280)
        if ICON_PATH.exists():
            dlg.setWindowIcon(QIcon(str(ICON_PATH)))

        layout = QVBoxLayout(dlg)

        # 标题
        title = QLabel("🚀 桌面自动化助手")
        title.setStyleSheet("font-size: 16px; font-weight: bold; padding: 8px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("请选择要执行的操作:")
        subtitle.setStyleSheet("color: #666; padding: 4px;")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)

        # 选项 1: 启动 GUI
        btn1 = QPushButton("🟢  启动 GUI")
        btn1.setStyleSheet("padding: 12px; font-size: 13px; text-align: left;")
        btn1.clicked.connect(lambda: dlg.done(1))
        layout.addWidget(btn1)

        # 选项 2: 启动 GUI + MCP
        btn2 = QPushButton("🟡  启动 GUI + MCP server")
        btn2.setStyleSheet("padding: 12px; font-size: 13px; text-align: left;")
        btn2.clicked.connect(lambda: dlg.done(2))
        layout.addWidget(btn2)

        # 选项 3: 停止所有
        btn3 = QPushButton("🔴  停止所有")
        btn3.setStyleSheet("padding: 12px; font-size: 13px; text-align: left;")
        btn3.clicked.connect(lambda: dlg.done(3))
        layout.addWidget(btn3)

        # 取消按钮
        btn_cancel = QPushButton("❌  取消")
        btn_cancel.setStyleSheet("padding: 8px; font-size: 12px;")
        btn_cancel.clicked.connect(lambda: dlg.done(0))
        layout.addWidget(btn_cancel)

        return dlg.exec()
    except ImportError:
        # PySide6 不可用,降级到命令行选择
        print("=" * 50)
        print("桌面自动化助手 - 启动器")
        print("=" * 50)
        print("1. 启动 GUI")
        print("2. 启动 GUI + MCP server")
        print("3. 停止所有")
        print("0. 取消")
        print("=" * 50)
        try:
            choice = input("请选择 (0-3): ").strip()
            return int(choice)
        except (ValueError, EOFError):
            return 0


def show_result(action: int) -> None:
    """显示执行结果对话框"""
    messages = {
        1: ("✅ GUI 已启动", "#dcfce7", "#16a34a"),
        2: ("✅ GUI + MCP server 已启动", "#dcfce7", "#16a34a"),
        3: ("✅ 已停止所有进程", "#fee2e2", "#dc2626"),
        0: ("已取消", "#f3f4f6", "#6b7280"),
    }
    msg, bg, fg = messages.get(action, ("❓ 未知操作", "#fef3c7", "#d97706"))

    try:
        from PySide6.QtWidgets import (QApplication, QMessageBox)
        from PySide6.QtGui import QIcon

        app = QApplication.instance() or QApplication(sys.argv)
        if ICON_PATH.exists():
            QApplication.setWindowIcon(QIcon(str(ICON_PATH)))
        QMessageBox.information(None, "启动器", msg)
    except ImportError:
        print(f"\n{msg}\n")


def main() -> int:
    action = show_dialog()
    if action == 1:
        run_launcher("start")
    elif action == 2:
        run_launcher("start")
        # 再启动 MCP server (用子进程,独立 stdio)
        mcp_proc = subprocess.Popen(
            [str(EXE_PATH), "--mcp"],
            cwd=str(EXE_PATH.parent),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        print(f"✅ MCP server 启动 (PID: {mcp_proc.pid})")
    elif action == 3:
        run_launcher("stop")
        # 也关闭 MCP 进程
        try:
            subprocess.run(
                ["taskkill", "/F", "/FI", "IMAGENAME eq 桌面自动化助手.exe"],
                capture_output=True, timeout=5
            )
        except Exception:
            pass

    show_result(action)
    return 0


if __name__ == "__main__":
    sys.exit(main())
