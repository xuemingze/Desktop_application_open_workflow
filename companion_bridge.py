"""
companion_bridge.py
桌宠桥接层：为 MetaPact 等外部桌宠/陪伴 AI 提供本地 API 接口。

设计原则：
- 运行在 QThread 中，不阻塞 PySide6 主界面
- 只暴露必要的、安全的端点
- 所有调用走现有模块（mcp_embedded, user_profile, ActivityLogDB）
- 强制 token 校验（可选）
- run_workflow 必须白名单（可选）
- 日志统一走 log_bus
"""
from __future__ import annotations

import json
import sqlite3
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

from PySide6.QtCore import QThread, Signal


# =======================
# 配置与常量
# =======================
DEFAULT_PORT = 16260


# =======================
# 核心模块导入
# =======================
try:
    from data_paths import USER_DATA_DIR
    from user_profile import get_active_profile_summary
    from mcp_embedded import run_workflow_sync
    from log_bus import log_bus
    from activity_log import ActivityLogDB
except ImportError:
    USER_DATA_DIR = None
    get_active_profile_summary = None
    run_workflow_sync = None
    log_bus = None
    ActivityLogDB = None


# =======================
# 工具函数
# =======================

def _log(message: str) -> None:
    """统一日志输出（兼容 log_bus 缺失场景）"""
    if log_bus:
        log_bus.emit(f"[CompanionBridge] {message}")
    else:
        print(f"[CompanionBridge] {message}")


def _get_data_dir():
    """获取用户数据目录：优先 data_paths，fallback 回退到旧路径"""
    if USER_DATA_DIR is not None:
        return USER_DATA_DIR
    return None


# =======================
# HTTP Handler
# =======================
class CompanionAPIHandler(BaseHTTPRequestHandler):
    """处理来自 MetaPact 的 HTTP 请求"""

    server = None  # type: Optional[CompanionBridgeServer]

    # 可选配置（由 desktop_auto 注入）
    config = {
        "enabled": True,
        "token": "",
        "whitelist_workflows": [],
    }

    def _send_json(self, status_code: int, data: dict) -> None:
        """发送 JSON 响应"""
        self.send_response(status_code)
        self.send_header("Content-type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _check_token(self) -> bool:
        """检查请求头中的 token 是否匹配配置"""
        if not self.config["token"]:
            return True  # 未配置 token = 不校验
        auth_header = self.headers.get("Authorization", "")
        return auth_header == f"Bearer {self.config['token']}"

    def log_message(self, format: str, *args) -> None:
        """禁用默认日志"""
        pass

    def do_GET(self):
        """GET 请求：/api/status"""
        parsed = = urlparse(self.path)
        if parsed.path == "/api/status":
            self._handle_status()
        else:
            self._send_json(404, {"ok": False, "error": "Not Found"})

    def do_POST(self):
        """POST 请求：/api/action/run_workflow"""
        parsed = urlparse(self.path)
        if parsed.path == "/api/action/run_workflow":
            if not self._check_token():
                self._send_json(401, {"ok": False, "error": "Unauthorized: invalid token"})
                return
            self._handle_run_workflow()
        else:
            self._send_json(404, {"ok": False, "error": "Not Found"})

    def do_OPTIONS(self):
        """CORS 预检"""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def _handle_status(self) -> None:
        """返回当前用户画像 + 最近活动"""
        profile = "暂无画像"
        if get_active_profile_summary is not None:
            try:
                profile = get_active_profile_summary()
            except Exception:
                profile = "暂无画像"

        current_activity = "未知"
        data_dir = _get_data_dir()
        if data_dir is not None and ActivityLogDB is not None:
            try:
                db = ActivityLogDB(data_dir)
                # 使用 query_latest 而不直接拼表名
                latest = db.query_latest(limit=1)
                if latest:
                    row = latest[0]
                    cat = row.get("category") or "未知"
                    win = row.get("window_title") or "未知窗口"
                    current_activity = f"正在 {cat}，窗口：{win}"
            except Exception as e:
                _log(f"查询最近活动失败: {e}")

        self._send_json(200, {
            "ok": True,
            "profile": profile,
            "current_activity": current_activity,
        })

    def _handle_run_workflow(self) -> None:
        """执行指定工作流（带白名单校验）"""
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        try:
            body = json.loads(post_data)
        except json.JSONDecodeError:
            self._send_json(400, {"ok": False, "error": "Invalid JSON"})
            return

        wf_name = body.get("name")
        if not wf_name:
            self._send_json(400, {"ok": False, "error": "缺少 name 参数"})
            return

        # 白名单校验
        whitelist = self.config.get("whitelist_workflows", [])
        if whitelist and wf_name not in whitelist:
            _log(f"[桥接] 工作流 {wf_name} 不在白名单中，拒绝执行")
            self._send_json(403, {"ok": False, "error": f"工作流 '{wf_name}' 不在白名单中"})
            return

        # 通知主线程（通过回调）
        if self.server and hasattr(self.server, "log_cb") and self.server.log_cb:
            self.server.log_cb(f"[桥接] MetaPact 请求执行工作流: {wf_name}")

        # 实际执行
        if run_workflow_sync is not None:
            res = run_workflow_sync(wf_name)
            self._send_json(200, res)
        else:
            self._send_json(500, {"ok": False, "error": "mcp_embedded 模块未加载"})


# =======================
# 桥接线程（QThread）
# =======================
class CompanionBridgeThread(QThread):
    """后台运行 HTTP Server 的 QThread"""

    log_signal = Signal(str)  # 日志输出
    status_signal = Signal(bool, str)  # (running, message)

    def __init__(self, port: int = DEFAULT_PORT, parent=None):
        super().__init__(parent)
        self.port = port
        self.httpd = None
        self._is_running = False
        self.handler = CompanionAPIHandler()
        self.handler.server = self  # 循环引用，供回调

    def update_config(self, config: dict) -> None:
        """更新运行时配置（enabled, token, whitelist_workflows）"""
        self.handler.config.update(config)

    def run(self) -> None:
        """启动 HTTP server"""
        if not self.handler.config["enabled"]:
            self.log_signal.emit("[桥接] 已禁用，不启动")
            self.status_signal.emit(False, "已禁用")
            return

        try:
            self.httpd = HTTPServer(("127.0.0.1", self.port), self.handler)
            self.httpd.log_cb = self.log_signal.emit
            self._is_running = True
            self.status_signal.emit(True, f"已启动，端口: {self.port}")
            self.log_signal.emit(f"🔗 桌宠桥接 API 已启动 (端口: {self.port})")
            self.httpd.serve_forever()
        except OSError as e:
            self.log_signal.emit(f"❌ 桌宠桥接 API 启动失败: {e}")
            self.status_signal.emit(False, str(e))

    def stop(self) -> None:
        """停止 HTTP server"""
        self._is_running = False
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.log_signal.emit("⏹ 桌宠桥接 API 已停止")
