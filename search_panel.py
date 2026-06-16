"""
文件搜索标签页 - 集成 Everything HTTP
====================================

依赖:
    - everything_http.py (HTTP 后端)
    - secure_store.py (DPAPI 凭据存储)

集成方式:
    from search_panel import SearchPanel
    tab_widget.addTab(SearchPanel(), "🔍 文件搜索")
"""
from __future__ import annotations

import os
import sys
import json
import urllib.request
import urllib.error
import urllib.parse
import base64
import subprocess
import time
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from PySide6.QtCore import Qt, QThread, Signal, QSize, QTimer
from PySide6.QtGui import QIcon, QFont, QDesktopServices, QKeySequence, QShortcut, QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit,
    QComboBox, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QGroupBox, QRadioButton, QButtonGroup, QFileDialog,
    QDialog, QDialogButtonBox, QFormLayout, QCheckBox, QSpinBox,
    QProgressDialog, QPlainTextEdit, QFrame, QSizePolicy, QToolButton,
    QApplication
)

# ---------------------------------------------------------------------------
# 0. DPAPI 安全存储 (内联实现,避免依赖 secure_store.py 文件位置)
# ---------------------------------------------------------------------------
class SecureStore:
    """Windows DPAPI 加密存储"""

    def __init__(self, app_name: str = "desktop_auto"):
        self.store_path = Path(os.environ.get("APPDATA", str(Path.home()))) \
            / app_name / "secure_store.bin"
        self.store_path.parent.mkdir(parents=True, exist_ok=True)

    def _dpapi_protect(self, plain: bytes) -> bytes:
        import ctypes
        from ctypes import wintypes
        crypt32 = ctypes.WinDLL("crypt32")

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [
                ("cbData", wintypes.DWORD),
                ("pbData", ctypes.POINTER(ctypes.c_byte)),
            ]
        in_blob = DATA_BLOB(len(plain), ctypes.cast(
            ctypes.c_char_p(plain), ctypes.POINTER(ctypes.c_byte)))
        out_blob = DATA_BLOB()
        ok = crypt32.CryptProtectData(
            ctypes.byref(in_blob), None, None, None, None, 0,
            ctypes.byref(out_blob)
        )
        if not ok:
            raise RuntimeError("CryptProtectData failed")
        encrypted = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)
        return encrypted

    def _dpapi_unprotect(self, encrypted: bytes) -> bytes:
        import ctypes
        from ctypes import wintypes
        crypt32 = ctypes.WinDLL("crypt32")

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [
                ("cbData", wintypes.DWORD),
                ("pbData", ctypes.POINTER(ctypes.c_byte)),
            ]
        in_blob = DATA_BLOB(len(encrypted), ctypes.cast(
            ctypes.c_char_p(encrypted), ctypes.POINTER(ctypes.c_byte)))
        out_blob = DATA_BLOB()
        ok = crypt32.CryptUnprotectData(
            ctypes.byref(in_blob), None, None, None, None, 0,
            ctypes.byref(out_blob)
        )
        if not ok:
            raise RuntimeError("CryptUnprotectData failed (数据可能已损坏或被其他账户加密)")
        plain = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)
        return plain

    def save(self, key: str, value: str) -> None:
        data = self._read()
        data[key] = value
        plain = json.dumps(data, ensure_ascii=False).encode("utf-8")
        encrypted = self._dpapi_protect(plain)
        self.store_path.write_bytes(encrypted)

    def load(self, key: str) -> Optional[str]:
        return self._read().get(key)

    def delete(self, key: str) -> None:
        data = self._read()
        if key in data:
            del data[key]
            plain = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.store_path.write_bytes(self._dpapi_protect(plain))

    def clear(self) -> None:
        if self.store_path.exists():
            self.store_path.unlink()

    def _read(self) -> dict:
        if not self.store_path.exists():
            return {}
        try:
            encrypted = self.store_path.read_bytes()
            plain = self._dpapi_unprotect(encrypted)
            return json.loads(plain.decode("utf-8"))
        except Exception:
            return {}


# ---------------------------------------------------------------------------
# 1. Everything HTTP 后端 (内联)
# ---------------------------------------------------------------------------
@dataclass
class FileResult:
    name: str
    path: str
    type: str = "file"
    size: int = 0
    date_modified: str = ""
    extension: str = ""

    @property
    def full_path(self) -> str:
        return os.path.join(self.path, self.name)


@dataclass
class EverythingConfig:
    host: str = "127.0.0.1"
    port: int = 16259
    username: str = ""
    password: str = ""


class EverythingHTTP:
    def __init__(self, config: EverythingConfig):
        self.config = config

    def _request(self, params: dict) -> dict:
        url = f"http://{self.config.host}:{self.config.port}/?" + urllib.parse.urlencode(params)
        headers = {}
        if self.config.username:
            token = base64.b64encode(
                f"{self.config.username}:{self.config.password}".encode()).decode()
            headers["Authorization"] = f"Basic {token}"
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return json.loads(r.read().decode("utf-8", errors="ignore"))
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise PermissionError("需要鉴权")
            raise

    def search(self, query: str, limit: int = 100, offset: int = 0,
               sort: str = "date_modified_desc", path: str = "") -> list[FileResult]:
        # 关键: Everything HTTP 的 path 参数是子串匹配,不是目录限定
        # 正确做法: 用 <目录路径> 语法限定到该目录下
        if path:
            # 去掉路径结尾的 \ 或 /,避免双重反斜杠
            path_clean = path.rstrip("\\/").replace("/", "\\")
            # 目录限定语法: <路径> 包含在 q 里
            query = f"<{path_clean}> {query}" if query else f"<{path_clean}>"
        params = {
            "q": query, "limit": limit, "offset": offset,
            "sort": sort, "json": 1,
            "path_column": 1,  # 返回完整路径
        }
        data = self._request(params)
        return [FileResult(
            name=item.get("name", ""),
            path=item.get("path", ""),
            type=item.get("type", "file"),
            size=item.get("size", 0),
            date_modified=item.get("date_modified", ""),
            extension=item.get("extension", ""),
        ) for item in data.get("results", [])]

    def test_connection(self) -> tuple[bool, str]:
        """测试连接,返回 (成功, 错误信息)"""
        try:
            results = self.search("*", limit=1)
            return True, f"连接成功,索引内有文件"
        except PermissionError:
            return False, "需要鉴权 (401)"
        except urllib.error.URLError as e:
            return False, f"无法连接: {e.reason}"
        except Exception as e:
            return False, str(e)


# ---------------------------------------------------------------------------
# 2. Everything 检测工具
# ---------------------------------------------------------------------------
EVERYTHING_DOWNLOAD_URL = "https://www.voidtools.com/zh-cn/downloads/"
EVERYTHING_COMMON_PATHS = [
    r"D:\Everything\Everything.exe",
    r"C:\Program Files\Everything\Everything.exe",
    r"C:\Program Files (x86)\Everything\Everything.exe",
    r"D:\Tools\Everything\Everything.exe",
    r"C:\Tools\Everything\Everything.exe",
]


def find_everything_exe() -> Optional[Path]:
    """自动扫描 Everything.exe 位置"""
    # 1. 注册表 (HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall)
    try:
        import winreg
        for hive, path in [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]:
            try:
                with winreg.OpenKey(hive, path) as key:
                    i = 0
                    while True:
                        try:
                            sub_name = winreg.EnumKey(key, i)
                            with winreg.OpenKey(key, sub_name) as sub:
                                try:
                                    name, _ = winreg.QueryValueEx(sub, "DisplayName")
                                    if "Everything" in name:
                                        try:
                                            loc, _ = winreg.QueryValueEx(sub, "InstallLocation")
                                            if loc:
                                                exe = Path(loc) / "Everything.exe"
                                                if exe.exists():
                                                    return exe
                                        except FileNotFoundError:
                                            pass
                                except FileNotFoundError:
                                    pass
                        except OSError:
                            break
                        i += 1
            except FileNotFoundError:
                pass
    except Exception:
        pass

    # 2. PATH 环境变量
    for p_dir in os.environ.get("PATH", "").split(";"):
        if p_dir and ("verything" in p_dir.lower()):
            exe = Path(p_dir) / "Everything.exe"
            if exe.exists():
                return exe

    # 3. 常见路径
    for p in EVERYTHING_COMMON_PATHS:
        if Path(p).exists():
            return Path(p)

    # 4. 任务管理器找进程 (ProcessId -> 路径)
    try:
        ps_cmd = ["wmic", "process", "where", "name='Everything.exe'", "get", "ProcessId,ExecutablePath", "/format:csv"]
        out = subprocess.check_output(ps_cmd, text=True, encoding="utf-8", errors="ignore", timeout=3)
        for line in out.splitlines():
            if "Everything.exe" in line and "," in line:
                parts = line.strip().split(",")
                if len(parts) >= 2 and Path(parts[1]).exists():
                    return Path(parts[1])
    except Exception:
        pass

    return None


def is_everything_running() -> bool:
    """检测 Everything 进程是否在跑"""
    try:
        out = subprocess.check_output(
            ["tasklist", "/FI", "IMAGENAME eq Everything.exe"],
            text=True, encoding="utf-8", errors="ignore", timeout=3
        )
        return "Everything.exe" in out
    except Exception:
        return False


def start_everything(exe_path: Path) -> bool:
    """启动 Everything (以服务模式)"""
    try:
        # /instance 服务模式启动 (无 GUI 弹窗)
        subprocess.Popen(
            [str(exe_path), "-instance"],
            creationflags=0x08000008  # CREATE_NO_WINDOW | DETACHED_PROCESS
        )
        time.sleep(2)
        return is_everything_running()
    except Exception:
        return False


def is_http_port_open(host: str = "127.0.0.1", port: int = 16259) -> bool:
    """检测端口是否监听"""
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/", timeout=2) as r:
            return True
    except urllib.error.HTTPError:
        return True  # 端口开,只是要密码
    except Exception:
        return False


# ---------------------------------------------------------------------------
# 3. 引导向导对话框 (4 步)
# ---------------------------------------------------------------------------
class SetupWizard(QDialog):
    """首次使用引导向导"""

    def __init__(self, parent=None, start_page: int = 0):
        super().__init__(parent)
        self.setWindowTitle("🔧 文件搜索 - 设置向导")
        self.setMinimumSize(700, 500)
        self.exe_path: Optional[Path] = None
        self.use_auth = False
        self.username = ""
        self.password = ""
        self.config = EverythingConfig()
        self._start_page = start_page

        # 步骤切换用 stackedWidget
        from PySide6.QtWidgets import QStackedWidget
        self.stack = QStackedWidget()
        self.page1 = self._build_page1()
        self.page2 = self._build_page2()
        self.page3 = self._build_page3()
        self.page4 = self._build_page4()
        self.stack.addWidget(self.page1)
        self.stack.addWidget(self.page2)
        self.stack.addWidget(self.page3)
        self.stack.addWidget(self.page4)

        # 底部按钮
        self.btn_prev = QPushButton("← 上一步")
        self.btn_next = QPushButton("下一步 →")
        self.btn_cancel = QPushButton("取消")
        self.lbl_step = QLabel("第 1/4 步")
        self.btn_test = QPushButton("🔌 测试连接")
        self.btn_test.setVisible(False)

        nav = QHBoxLayout()
        nav.addWidget(self.lbl_step)
        nav.addStretch()
        nav.addWidget(self.btn_test)
        nav.addWidget(self.btn_prev)
        nav.addWidget(self.btn_next)
        nav.addWidget(self.btn_cancel)

        layout = QVBoxLayout(self)
        layout.addWidget(self.stack)
        layout.addLayout(nav)

        self.btn_prev.clicked.connect(self._on_prev)
        self.btn_next.clicked.connect(self._on_next)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_test.clicked.connect(self._on_test)
        self._update_nav()
        QTimer.singleShot(100, self._detect_everything_auto)
        if self._start_page > 0:
            self.stack.setCurrentIndex(self._start_page)
            self._update_nav()

    # ---- Page 1: Everything 路径 ----
    def _build_page1(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        title = QLabel("第 1 步: 找到 Everything")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        desc = QLabel(
            "Everything 是 Windows 上最快的文件搜索工具 (基于 NTFS MFT)。\n"
            "本程序需要 Everything 提供搜索能力。"
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        layout.addSpacing(20)

        # 检测结果区
        self.lbl_detect_status = QLabel("🔍 正在自动扫描常见位置...")
        self.lbl_detect_status.setStyleSheet("font-size: 14px;")
        layout.addWidget(self.lbl_detect_status)

        layout.addSpacing(10)

        # 路径选择
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("Everything.exe 路径:"))
        self.edt_exe_path = QLineEdit()
        self.edt_exe_path.setPlaceholderText("例如: D:\\Everything\\Everything.exe")
        path_layout.addWidget(self.edt_exe_path)
        btn_browse = QPushButton("📂 浏览...")
        btn_browse.clicked.connect(self._on_browse_exe)
        path_layout.addWidget(btn_browse)
        layout.addLayout(path_layout)

        btn_rescan = QPushButton("🔄 重新扫描")
        btn_rescan.clicked.connect(self._detect_everything_auto)
        layout.addWidget(btn_rescan)

        layout.addSpacing(20)

        # 下载区
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep)

        layout.addWidget(QLabel("❓ 没找到 Everything?"))

        btn_download = QPushButton("📥 下载 Everything 1.5+ (官方地址)")
        btn_download.setStyleSheet("padding: 8px; font-size: 13px;")
        btn_download.clicked.connect(self._on_download)
        layout.addWidget(btn_download)

        btn_open_voidtools = QPushButton("🌐 打开 voidtools 官网")
        btn_open_voidtools.clicked.connect(lambda: QDesktopServices.openUrl(
            __import__("PySide6").QtCore.QUrl("https://www.voidtools.com/zh-cn/downloads/")))
        layout.addWidget(btn_open_voidtools)

        note = QLabel(
            "💡 提示: 安装 Everything 时,建议勾选 \"安装为服务\" 以便后台常驻"
        )
        note.setStyleSheet("color: gray; font-size: 11px;")
        note.setWordWrap(True)
        layout.addWidget(note)

        layout.addStretch()
        return w

    def _detect_everything_auto(self):
        self.lbl_detect_status.setText("🔍 正在扫描...")
        QApplication.processEvents()
        exe = find_everything_exe()
        if exe:
            self.exe_path = exe
            self.edt_exe_path.setText(str(exe))
            self.lbl_detect_status.setText(f"✅ 已找到: {exe}")
            self.lbl_detect_status.setStyleSheet("color: green; font-size: 14px; font-weight: bold;")
        else:
            self.lbl_detect_status.setText("❌ 未找到 Everything")
            self.lbl_detect_status.setStyleSheet("color: red; font-size: 14px;")

    def _on_browse_exe(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 Everything.exe", "C:\\", "Executable (*.exe)")
        if path:
            self.exe_path = Path(path)
            self.edt_exe_path.setText(path)
            self.lbl_detect_status.setText(f"✅ 已选择: {path}")
            self.lbl_detect_status.setStyleSheet("color: green; font-size: 14px;")

    def _on_download(self):
        QDesktopServices.openUrl(__import__("PySide6").QtCore.QUrl(EVERYTHING_DOWNLOAD_URL))

    # ---- Page 2: 启动 Everything + HTTP ----
    def _build_page2(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        title = QLabel("第 2 步: 启动 Everything 并启用 HTTP 服务")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        layout.addSpacing(10)

        # 进程状态
        self.lbl_proc = QLabel("进程状态: 检测中...")
        self.lbl_proc.setStyleSheet("font-size: 14px;")
        layout.addWidget(self.lbl_proc)

        btn_start = QPushButton("▶️ 启动 Everything (服务模式)")
        btn_start.clicked.connect(self._on_start_everything)
        layout.addWidget(btn_start)

        layout.addSpacing(20)

        # HTTP 端口
        self.lbl_port = QLabel("HTTP 端口 16259: 检测中...")
        self.lbl_port.setStyleSheet("font-size: 14px;")
        layout.addWidget(self.lbl_port)

        layout.addSpacing(10)

        # 操作指引
        guide = QGroupBox("📋 手动启用 HTTP Server (如果上面按钮无效)")
        guide_layout = QVBoxLayout(guide)
        steps = QLabel(
            "1. 双击 Everything.exe 打开主窗口\n"
            "2. 菜单 → 工具 → 选项 → 切到 [HTTP Server] 标签\n"
            "3. ✅ 勾选 \"启用 HTTP server\"\n"
            "4. 端口保持默认 16259\n"
            "5. 点 [确定] 保存\n"
            "6. 回到这里点 [下一步]"
        )
        steps.setStyleSheet("font-family: Consolas, monospace; font-size: 12px; padding: 10px;")
        guide_layout.addWidget(steps)
        layout.addWidget(guide)

        btn_reecheck = QPushButton("🔄 重新检测")
        btn_reecheck.clicked.connect(self._check_page2_status)
        layout.addWidget(btn_reecheck)

        layout.addStretch()
        return w

    def _on_start_everything(self):
        if not self.exe_path:
            QMessageBox.warning(self, "未选择", "请先在第 1 步选择 Everything.exe")
            return
        QApplication.processEvents()
        if start_everything(self.exe_path):
            QMessageBox.information(self, "成功", "Everything 已启动")
        else:
            QMessageBox.warning(self, "失败", "启动失败,请手动双击 Everything.exe")
        self._check_page2_status()

    def _check_page2_status(self):
        if is_everything_running():
            self.lbl_proc.setText("✅ Everything 进程运行中")
            self.lbl_proc.setStyleSheet("color: green; font-size: 14px;")
        else:
            self.lbl_proc.setText("❌ Everything 未运行")
            self.lbl_proc.setStyleSheet("color: red; font-size: 14px;")

        if is_http_port_open():
            self.lbl_port.setText("✅ HTTP 端口 16259 已监听")
            self.lbl_port.setStyleSheet("color: green; font-size: 14px;")
        else:
            self.lbl_port.setText("❌ HTTP 端口未监听 (需启用 HTTP Server)")
            self.lbl_port.setStyleSheet("color: red; font-size: 14px;")

    # ---- Page 3: 鉴权模式 ----
    def _build_page3(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        title = QLabel("第 3 步: 选择鉴权模式")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        layout.addSpacing(10)

        # 选项
        self.radio_no_auth = QRadioButton("无密码 (本地单机推荐)")
        self.radio_no_auth.setChecked(True)
        self.radio_with_auth = QRadioButton("有密码 (多人共用电脑推荐)")
        layout.addWidget(self.radio_no_auth)
        layout.addWidget(self.radio_with_auth)

        layout.addSpacing(20)

        # 密码输入区 (默认隐藏)
        self.auth_group = QGroupBox("🔐 HTTP 账号密码")
        auth_layout = QFormLayout(self.auth_group)

        self.edt_user = QLineEdit()
        self.edt_user.setPlaceholderText("例如: admin")
        auth_layout.addRow("用户名:", self.edt_user)

        self.edt_pass = QLineEdit()
        self.edt_pass.setEchoMode(QLineEdit.Password)
        auth_layout.addRow("密码:", self.edt_pass)

        layout.addWidget(self.auth_group)
        self.auth_group.setVisible(False)

        self.radio_with_auth.toggled.connect(lambda c: self.auth_group.setVisible(c))

        # 测试连接结果
        self.lbl_test = QLabel("")
        self.lbl_test.setStyleSheet("font-size: 13px; padding: 5px;")
        layout.addWidget(self.lbl_test)

        layout.addSpacing(10)
        layout.addWidget(QLabel("💡 凭据会用 Windows DPAPI 加密保存,只有你的账户能解开"))

        layout.addStretch()
        return w

    def _on_test(self):
        cfg = EverythingConfig(
            port=16259,
            username=self.edt_user.text().strip() if self.radio_with_auth.isChecked() else "",
            password=self.edt_pass.text() if self.radio_with_auth.isChecked() else "",
        )
        backend = EverythingHTTP(cfg)
        ok, msg = backend.test_connection()
        if ok:
            self.lbl_test.setText(f"✅ {msg}")
            self.lbl_test.setStyleSheet("color: green; font-size: 13px;")
        else:
            self.lbl_test.setText(f"❌ {msg}")
            self.lbl_test.setStyleSheet("color: red; font-size: 13px;")

    # ---- Page 4: 完成 ----
    def _build_page4(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        title = QLabel("第 4 步: 完成 ✓")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: green;")
        layout.addWidget(title)

        layout.addSpacing(20)

        summary = QLabel("设置完成!以下是你的配置:\n\n"
                        f"  Everything 路径: {self.exe_path or '(未设置)'}\n"
                        f"  HTTP 端口: 16259\n"
                        f"  鉴权模式: {'有密码' if self.radio_with_auth.isChecked() else '无密码'}")
        summary.setStyleSheet("font-family: Consolas, monospace; font-size: 12px; padding: 10px;")
        summary.setWordWrap(True)
        layout.addWidget(summary)

        layout.addSpacing(20)

        # 最终测试
        btn_final_test = QPushButton("🔌 最终连接测试")
        btn_final_test.clicked.connect(self._on_test)
        layout.addWidget(btn_final_test)

        self.lbl_test = QLabel("")
        self.lbl_test.setStyleSheet("font-size: 13px;")
        layout.addWidget(self.lbl_test)

        layout.addStretch()

        note = QLabel("点击 [完成] 保存设置,凭据会自动加密存储")
        note.setStyleSheet("color: gray;")
        layout.addWidget(note)
        return w

    # ---- 导航 ----
    def _update_nav(self):
        idx = self.stack.currentIndex()
        self.lbl_step.setText(f"第 {idx+1}/4 步")
        self.btn_prev.setEnabled(idx > 0)
        self.btn_next.setText("完成 ✓" if idx == 3 else "下一步 →")
        self.btn_test.setVisible(idx in (2, 3))

    def _on_prev(self):
        if self.stack.currentIndex() > 0:
            self.stack.setCurrentIndex(self.stack.currentIndex() - 1)
            self._update_nav()

    def _on_next(self):
        idx = self.stack.currentIndex()
        if idx == 0:
            # Page 1 -> 2: 必须有 exe_path
            path_text = self.edt_exe_path.text().strip()
            if path_text:
                p = Path(path_text)
                if p.exists():
                    self.exe_path = p
                else:
                    QMessageBox.warning(self, "路径无效", f"文件不存在: {p}")
                    return
            if not self.exe_path:
                QMessageBox.warning(self, "未选择", "请先选择 Everything.exe 路径")
                return
            self._check_page2_status()
        elif idx == 1:
            # Page 2 -> 3: 检查 HTTP 端口
            if not is_http_port_open():
                reply = QMessageBox.question(
                    self, "HTTP 未启用",
                    "HTTP 端口 16259 未监听。\n是否仍然继续?",
                    QMessageBox.Yes | QMessageBox.No)
                if reply != QMessageBox.Yes:
                    return
        elif idx == 2:
            # Page 3 -> 4: 保存凭据
            self.use_auth = self.radio_with_auth.isChecked()
            if self.use_auth:
                self.username = self.edt_user.text().strip()
                self.password = self.edt_pass.text()
                if not self.username:
                    QMessageBox.warning(self, "缺用户名", "请输入 HTTP 账号")
                    return
            # DPAPI 保存
            try:
                store = SecureStore("desktop_auto")
                if self.use_auth:
                    store.save("everything_http_user", self.username)
                    store.save("everything_http_pass", self.password)
                else:
                    store.delete("everything_http_user")
                    store.delete("everything_http_pass")
            except Exception as e:
                QMessageBox.warning(self, "保存失败", f"DPAPI 保存失败: {e}")
                return
        elif idx == 3:
            # 完成
            self.config = EverythingConfig(
                port=16259,
                username=self.username if self.use_auth else "",
                password=self.password if self.use_auth else "",
            )
            self.accept()
            return

        self.stack.setCurrentIndex(idx + 1)
        self._update_nav()

    def get_config(self) -> EverythingConfig:
        return self.config


# ---------------------------------------------------------------------------
# 4. 文件搜索主面板
# ---------------------------------------------------------------------------
class SearchWorker(QThread):
    finished = Signal(list)        # list[FileResult]
    error = Signal(str)

    def __init__(self, backend: EverythingHTTP, query: str, limit: int,
                 sort: str, path: str):
        super().__init__()
        self.backend = backend
        self.query = query
        self.limit = limit
        self.sort = sort
        self.path = path

    def run(self):
        try:
            results = self.backend.search(
                self.query, limit=self.limit, sort=self.sort, path=self.path)
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class SearchPanel(QWidget):
    """文件搜索主面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.backend: Optional[EverythingHTTP] = None
        self.worker: Optional[SearchWorker] = None
        self.results: list[FileResult] = []
        self._build_ui()
        QTimer.singleShot(100, self._auto_load_or_prompt_setup)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # 顶部状态条
        status_bar = QHBoxLayout()
        self.lbl_status = QLabel("⚪ 状态未知")
        self.lbl_status.setStyleSheet("font-size: 13px; padding: 5px;")
        status_bar.addWidget(self.lbl_status)
        status_bar.addStretch()

        btn_setup = QPushButton("🔧 设置")
        btn_setup.clicked.connect(self._open_setup)
        status_bar.addWidget(btn_setup)

        btn_test = QPushButton("🔄 测试")
        btn_test.clicked.connect(self._refresh_status)
        status_bar.addWidget(btn_test)

        layout.addLayout(status_bar)

        # 分隔
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep)

        # 搜索输入区
        search_group = QGroupBox("🔍 搜索")
        sg_layout = QVBoxLayout(search_group)

        # 主搜索框 + 按钮
        row1 = QHBoxLayout()
        self.edt_query = QLineEdit()
        self.edt_query.setPlaceholderText("Everything 语法: *.py / ext:md RAG / size:>10MB / \"完整名\"")
        self.edt_query.setStyleSheet("padding: 6px; font-size: 14px;")
        self.edt_query.returnPressed.connect(self._on_search)
        self.btn_search = QPushButton("🔍 搜索 (Enter)")
        self.btn_search.clicked.connect(self._on_search)
        self.btn_search.setStyleSheet("padding: 6px 15px; font-weight: bold;")
        row1.addWidget(self.edt_query)
        row1.addWidget(self.btn_search)
        sg_layout.addLayout(row1)

        # 过滤行
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("路径:"))
        self.edt_path = QLineEdit()
        self.edt_path.setPlaceholderText("(可选) 限定目录, 例: C:\\Users\\")
        row2.addWidget(self.edt_path)

        row2.addWidget(QLabel("排序:"))
        self.cmb_sort = QComboBox()
        self.cmb_sort.addItems([
            "修改时间 ↓", "修改时间 ↑",
            "名称 ↑", "名称 ↓",
            "大小 ↓", "大小 ↑",
            "路径 ↑", "路径 ↓",
            "扩展名 ↑", "扩展名 ↓",
        ])
        row2.addWidget(self.cmb_sort)

        row2.addWidget(QLabel("数量:"))
        self.spn_limit = QSpinBox()
        self.spn_limit.setRange(10, 10000)
        self.spn_limit.setValue(100)
        self.spn_limit.setSingleStep(50)
        row2.addWidget(self.spn_limit)

        sg_layout.addLayout(row2)

        # 语法帮助
        syntax_help = QLabel(
            "💡 <code>*.py</code> 所有 py 文件 &nbsp; "
            "<code>ext:md RAG</code> md 含 RAG &nbsp; "
            "<code>size:&gt;10MB</code> 大于 10MB &nbsp; "
            "<code>dm:today</code> 今天改的 &nbsp; "
            "<code>\"exact match\"</code> 精确匹配"
        )
        syntax_help.setStyleSheet("color: gray; font-size: 11px;")
        syntax_help.setTextFormat(Qt.RichText)
        sg_layout.addWidget(syntax_help)

        layout.addWidget(search_group)

        # 结果区
        result_group = QGroupBox("📋 结果")
        rg_layout = QVBoxLayout(result_group)

        # 表格
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["名称", "路径", "大小", "修改时间", "类型"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.setColumnWidth(0, 250)
        self.table.doubleClicked.connect(self._on_open_selected)
        rg_layout.addWidget(self.table)

        # 底部信息
        info_row = QHBoxLayout()
        self.lbl_result_count = QLabel("就绪")
        info_row.addWidget(self.lbl_result_count)
        info_row.addStretch()
        btn_clear = QPushButton("🗑 清空")
        btn_clear.clicked.connect(self._clear_results)
        info_row.addWidget(btn_clear)

        # 操作按钮
        btn_open = QPushButton("📂 打开")
        btn_open.clicked.connect(self._on_open_selected)
        btn_reveal = QPushButton("📁 定位")
        btn_reveal.clicked.connect(self._on_reveal_selected)
        btn_copy_path = QPushButton("📋 复制路径")
        btn_copy_path.clicked.connect(self._on_copy_path)
        btn_copy_name = QPushButton("📋 复制文件名")
        btn_copy_name.clicked.connect(self._on_copy_name)

        info_row.addWidget(btn_open)
        info_row.addWidget(btn_reveal)
        info_row.addWidget(btn_copy_path)
        info_row.addWidget(btn_copy_name)

        rg_layout.addLayout(info_row)
        layout.addWidget(result_group)

        # 快捷键
        QShortcut(QKeySequence("Ctrl+F"), self, self.edt_query.setFocus)
        QShortcut(QKeySequence("F5"), self, self._on_search)
        QShortcut(QKeySequence("Ctrl+O"), self, self._on_open_selected)

    # ---- 自动加载 ----
    def _auto_load_or_prompt_setup(self):
        """启动时尝试自动加载凭据,失败则提示设置"""
        try:
            store = SecureStore("desktop_auto")
            user = store.load("everything_http_user") or ""
            pwd = store.load("everything_http_pass") or ""
            cfg = EverythingConfig(port=16259, username=user, password=pwd)
            backend = EverythingHTTP(cfg)
            self.backend = backend
            self._refresh_status()
        except Exception as e:
            self.lbl_status.setText(f"⚠️ 自动加载失败: {e}")
            self.lbl_status.setStyleSheet("color: orange; font-size: 13px;")
            self._open_setup()

    def _refresh_status(self):
        """刷新连接状态"""
        if not self.backend:
            self.lbl_status.setText("⚪ 未配置")
            self.lbl_status.setStyleSheet("color: gray; font-size: 13px;")
            return
        ok, msg = self.backend.test_connection()
        if ok:
            self.lbl_status.setText(f"🟢 {msg}")
            self.lbl_status.setStyleSheet("color: green; font-size: 13px; font-weight: bold;")
        elif "401" in msg or "鉴权" in msg:
            self.lbl_status.setText("🟡 HTTP需要密码，点击[搜索]输入")
            self.lbl_status.setStyleSheet("color: orange; font-size: 13px;")
        else:
            self.lbl_status.setText(f"🔴 {msg}")
            self.lbl_status.setStyleSheet("color: red; font-size: 13px;")

    def _open_setup(self, jump_to_auth: bool = False):
        """打开设置向导，jump_to_auth=True 时直接跳到账号密码页"""
        wizard = SetupWizard(self, start_page=2 if jump_to_auth else 0)
        if wizard.exec() == QDialog.Accepted:
            self.backend = EverythingHTTP(wizard.get_config())
            self._refresh_status()
            QMessageBox.information(self, "设置完成", "可以开始搜索了!")

    def _on_search(self):
        """执行搜索"""
        if not self.backend:
            reply = QMessageBox.question(
                self, "未配置",
                "还没配置 Everything HTTP 服务。\n是否打开设置?",
                QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self._open_setup()
            return

        query = self.edt_query.text().strip()
        if not query:
            query = "*"  # 空查询 = 全部

        path = self.edt_path.text().strip()
        limit = self.spn_limit.value()
        sort_map = [
            "date_modified_desc", "date_modified_asc",
            "name_asc", "name_desc",
            "size_desc", "size_asc",
            "path_asc", "path_desc",
            "extension_asc", "extension_desc",
        ]
        sort = sort_map[self.cmb_sort.currentIndex()]

        self.btn_search.setEnabled(False)
        self.lbl_result_count.setText("搜索中...")

        self.worker = SearchWorker(self.backend, query, limit, sort, path)
        self.worker.finished.connect(self._on_search_done)
        self.worker.error.connect(self._on_search_error)
        self.worker.start()

    def _on_search_done(self, results: list):
        self.results = results
        self._populate_table(results)
        self.btn_search.setEnabled(True)
        self.lbl_result_count.setText(f"✅ 找到 {len(results)} 个文件")
        self.lbl_result_count.setStyleSheet("color: green; font-size: 13px;")

    def _on_search_error(self, err: str):
        self.btn_search.setEnabled(True)
        self.lbl_result_count.setText(f"❌ 错误: {err}")
        self.lbl_result_count.setStyleSheet("color: red; font-size: 13px;")
        if "401" in err or "鉴权" in err:
            # HTTP 需要密码，直接跳到账号密码页
            self._open_setup(jump_to_auth=True)

    def _populate_table(self, results: list):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(results))
        for row, r in enumerate(results):
            self.table.setItem(row, 0, QTableWidgetItem(r.name))
            self.table.setItem(row, 1, QTableWidgetItem(r.path))
            size_item = QTableWidgetItem(self._format_size(r.size))
            size_item.setData(Qt.UserRole, r.size)
            self.table.setItem(row, 2, size_item)
            self.table.setItem(row, 3, QTableWidgetItem(r.date_modified))
            type_item = QTableWidgetItem("📁 文件夹" if r.type == "folder" else "📄 文件")
            type_item.setData(Qt.UserRole, r.full_path)
            self.table.setItem(row, 4, type_item)
        self.table.setSortingEnabled(True)

    def _format_size(self, size: int) -> str:
        s = float(size)
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if s < 1024:
                return f"{int(s)} {unit}" if unit == "B" else f"{s:.1f} {unit}"
            s /= 1024
        return f"{s:.1f} PB"

    def _selected_results(self) -> list:
        rows = set(idx.row() for idx in self.table.selectedIndexes())
        return [self.results[r] for r in sorted(rows) if r < len(self.results)]

    def _clear_results(self):
        """清空搜索结果"""
        self.results = []
        self.table.setRowCount(0)
        self.lbl_result_count.setText("已清空")
        self.lbl_result_count.setStyleSheet("color: gray; font-size: 13px;")


    def _on_open_selected(self):
        selected = self._selected_results()
        if not selected:
            return
        for r in selected[:10]:  # 最多开 10 个
            try:
                os.startfile(r.full_path)
            except Exception as e:
                QMessageBox.warning(self, "打开失败", f"{r.full_path}\n{e}")

    def _on_reveal_selected(self):
        selected = self._selected_results()
        if not selected:
            return
        for r in selected[:10]:
            try:
                subprocess.Popen(["explorer", "/select,", r.full_path])
            except Exception as e:
                QMessageBox.warning(self, "定位失败", f"{r.full_path}\n{e}")

    def _on_copy_path(self):
        selected = self._selected_results()
        if not selected:
            return
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText("\n".join(r.full_path for r in selected))
        self.lbl_result_count.setText(f"📋 已复制 {len(selected)} 个路径到剪贴板")

    def _on_copy_name(self):
        selected = self._selected_results()
        if not selected:
            return
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText("\n".join(r.name for r in selected))
        self.lbl_result_count.setText(f"📋 已复制 {len(selected)} 个文件名")



# ---------------------------------------------------------------------------
# 便利函数 (供 MCP 调用)
# ---------------------------------------------------------------------------
def search_everything(query: str, limit: int = 50, offset: int = 0, sort: str = "date", path: str = ""):
    """
    Everything 全盘搜索 (供 MCP 调用)
    返回 JSON 友好的 dict

    鉴权策略: 优先用 SecureStore 中存储的凭据 (与【文件搜索】标签页一致)。
    凭据不存在时退回无密码模式。
    """
    # 从 SecureStore 加载凭据 (与 SearchPanel._auto_load_or_prompt_setup 一致)
    username, password = "", ""
    try:
        store = SecureStore("desktop_auto")
        username = store.load("everything_http_user") or ""
        password = store.load("everything_http_pass") or ""
    except Exception:
        pass
    config = EverythingConfig(host="127.0.0.1", port=16259, username=username, password=password)
    try:
        eh = EverythingHTTP(config)
        results = eh.search(query, limit=limit, offset=offset, sort=sort, path=path)
        # 转换为 dict 列表
        out = []
        for r in results:
            if hasattr(r, '__dict__'):
                out.append({
                    "name": getattr(r, "name", ""),
                    "path": getattr(r, "path", ""),
                    "type": getattr(r, "type", "file"),
                    "size": getattr(r, "size", 0),
                    "date_modified": getattr(r, "date_modified", ""),
                    "extension": getattr(r, "extension", ""),
                })
            elif isinstance(r, dict):
                out.append(r)
        return {"ok": True, "count": len(out), "results": out}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ---------------------------------------------------------------------------
# 5. CLI 入口 (调试用)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    panel = SearchPanel()
    panel.resize(900, 600)
    panel.show()
    sys.exit(app.exec())