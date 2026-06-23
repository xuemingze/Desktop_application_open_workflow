"""
companion_bridge.py
桌宠桥接层：为 MetaPact 等外部桌宠/陪伴 AI 提供本地 API。

设计原则：
- 运行在标准库 Thread 中，不阻塞 PySide6 主界面
- 只暴露必要的、安全的端点
- 所有调用走现有模块（mcp_embedded, user_profile, ActivityLogDB）
- 强制 token 校验（可选）
- run_workflow 必须白名单（可选）
- 日志统一走 log_bus
"""
from __future__ import annotations

import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse


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
    from context_agent import OpenAICompatibleBackend, parse_intent_response
except ImportError:
    USER_DATA_DIR = None
    get_active_profile_summary = None
    run_workflow_sync = None
    log_bus = None
    ActivityLogDB = None
    OpenAICompatibleBackend = None
    parse_intent_response = None


# =======================
# 工具函数
# =======================

def _log(message: str) -> None:
    """统一日志输出（兼容 log_bus 缺失场景）"""
    msg = f"[CompanionBridge] {message}"
    if log_bus:
        try:
            log_bus.emit(msg)
        except Exception:
            print(msg)
    else:
        print(msg)


def _get_data_dir():
    """获取用户数据目录"""
    return USER_DATA_DIR


# =======================
# HTTP Handler（无状态，每请求独立处理）
# =======================
class CompanionAPIHandler(BaseHTTPRequestHandler):
    """处理来自 MetaPact 的 HTTP 请求，并新增 OpenAI 兼容 LLM 端点供 VTuber 调用"""

    # 类级别配置（运行时由 desktop_auto 注入）
    config = {
        "enabled": True,
        "token": "",
        "whitelist_workflows": [],
    }

    # 共享的 LLM 后端实例（由 desktop_auto 设置）
    _backend = None
    _backend_model = "desktop-auto-v1"  # 实际模型名，由 desktop_auto 注入

    def _send_json(self, status_code: int, data: dict) -> None:
        self.send_response(status_code)
        self.send_header("Content-type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _send_chat_stream(self, raw: str, model: str = "desktop-auto-v1") -> None:
        """发送 OpenAI 兼容 SSE 流式响应（VTuber 固定 stream=True）。
        使用 raw socket 直接发送避免 BufferedWriter 缓冲问题。"""
        import time
        chat_id = f"chatcmpl-{int(time.time() * 1000)}"
        created = int(time.time())
        sock = self.request
        self.close_connection = True
        # 手动构建 HTTP 响应（绕过 BaseHTTPRequestHandler 的 wfile 缓冲）
        resp_headers = (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: text/event-stream; charset=utf-8\r\n"
            "Cache-Control: no-cache\r\n"
            "Connection: close\r\n"
            "Access-Control-Allow-Origin: *\r\n"
            "\r\n"
        )
        try:
            sock.sendall(resp_headers.encode("utf-8"))
        except Exception:
            return

        def send_event(payload: dict) -> None:
            line = "data: " + json.dumps(payload, ensure_ascii=False) + "\n\n"
            try:
                sock.sendall(line.encode("utf-8"))
            except Exception:
                pass

        send_event({
            "id": chat_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
        })
        send_event({
            "id": chat_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": {"content": raw}, "finish_reason": None}],
        })
        send_event({
            "id": chat_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        })
        try:
            sock.sendall(b"data: [DONE]\n\n")
        except Exception:
            pass

    def _check_token(self) -> bool:
        if not self.config.get("token"):
            return True
        auth = self.headers.get("Authorization", "")
        return auth == f"Bearer {self.config['token']}"

    def log_message(self, format: str, *args) -> None:
        """禁用默认 apache 风格日志"""
        pass

    def do_GET(self):
        if self.path == "/api/status":
            self._handle_status()
        elif self.path == "/v1/models":
            self._handle_models()
        else:
            self._send_json(404, {"ok": False, "error": "Not Found"})

    def do_POST(self):
        if self.path == "/api/action/run_workflow":
            if not self._check_token():
                self._send_json(401, {"ok": False, "error": "Unauthorized"})
                return
            self._handle_run_workflow()
        elif self.path == "/v1/chat/completions":
            self._handle_chat_completions()
        else:
            self._send_json(404, {"ok": False, "error": "Not Found"})

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def _handle_status(self) -> None:
        profile = "暂无画像"
        if get_active_profile_summary is not None:
            try:
                profile = get_active_profile_summary()
            except Exception:
                pass

        current_activity = "未知"
        data_dir = _get_data_dir()
        if data_dir and ActivityLogDB:
            try:
                db = ActivityLogDB(data_dir)
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
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        try:
            body = json.loads(post_data)
        except json.JSONDecodeError:
            self._send_json(400, {"ok": False, "error": "Invalid ISON"})
            return

        wf_name = body.get("name")
        if not wf_name:
            self._send_json(400, {"ok": False, "error": "缺少 name 参数"})
            return

        whitelist = self.config.get("whitelist_workflows", [])
        if whitelist and wf_name not in whitelist:
            _log(f"[桥接] 工作流 {wf_name} 不在白名单，拒绝")
            self._send_json(403, {"ok": False, "error": f"工作流 '{wf_name}' 不在白名单"})
            return
        if run_workflow_sync is not None:
            res = run_workflow_sync(wf_name)
            self._send_json(200, res)
        else:
            self._send_json(500, {"ok": False, "error": "mcp_embedded 模块未加载"})

    def _handle_models(self) -> None:
        """返回 OpenAI 兼容的模型列表（用于 VTuber），自动同步真实后端模型名"""
        self._sync_backend_from_config()
        model_id = CompanionAPIHandler._backend_model or "desktop-auto-v1"
        self._send_json(200, {
            "object": "list",
            "data": [
                {
                    "id": model_id,
                    "object": "model",
                    "created": 1718880000,
                    "owned_by": "desktop-auto",
                }
            ],
        })

    @classmethod
    def _sync_backend_from_config(cls) -> bool:
        """从 context_aware_config.json 重新加载后端配置（桌面助手重启后也可同步）"""
        try:
            cfg_path = None
            if _get_data_dir():
                cfg_path = _get_data_dir() / "context_aware_config.json"
            if not cfg_path or not cfg_path.exists():
                return False
            import json
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            bc = cfg.get("backend", {}) if isinstance(cfg, dict) else {}
            if int(bc.get("type", 0) or 0) != 1:
                return False
            from context_agent import OpenAICompatibleBackend
            base_url = str(bc.get("base_url") or "").strip()
            api_key = str(bc.get("api_key") or "EMPTY").strip() or "EMPTY"
            model = str(bc.get("model") or "").strip()
            if not base_url or not model:
                return False
            if cls._backend is not None and cls._backend_model == model:
                return True
            cls._backend = OpenAICompatibleBackend(
                base_url=base_url,
                api_key=api_key,
                model=model,
            )
            cls._backend_model = model
            _log(f"后端配置已同步: {base_url}, model={model}")
            return True
        except Exception as e:
            _log(f"后端配置同步失败: {e}")
            return False

    def _handle_reload_backend(self) -> None:
        """手动触发后端配置重新加载"""
        ok = self._sync_backend_from_config()
        model = CompanionAPIHandler._backend_model or "none"
        if ok:
            self._send_json(200, {"ok": True, "model": model, "message": f"后端已重载: {model}"})
        else:
            self._send_json(200, {"ok": False, "model": model, "message": "配置未变化或读取失败"})

    def _handle_chat_completions(self) -> None:
        """处理 OpenAI 兼容的 /v1/chat/completions 请求"""
        self._sync_backend_from_config()
        if CompanionAPIHandler._backend is None:
            self._send_json(500, {"ok": False, "error": "LLM backend 未初始化"})
            return


        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        try:
            body = json.loads(post_data)
        except json.JSONDecodeError as e:
            _log(f"[桥接] JSON 解析失败: {e}")
            self._send_json(400, {"ok": False, "error": "Invalid ISON"})
            return


        messages = body.get("messages", [])
        if not messages:
            self._send_json(400, {"ok": False, "error": "Missing messages"})
            return


        def _content_to_text(content) -> str:
            """兼容 OpenAI 文本 content 与多模态 content list。"""
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, dict):
                        if item.get("type") == "text":
                            parts.append(str(item.get("text") or ""))
                        elif "text" in item:
                            parts.append(str(item.get("text") or ""))
                    elif isinstance(item, str):
                        parts.append(item)
                return "\n".join([p for p in parts if p.strip()])
            if content is None:
                return ""
            return str(content)

        # 拆出 system 和最后一条 user 消息（OpenAICompatibleBackend 只接受 system + user）
        system_prompt = ""
        user_text = ""
        for msg in messages:
            role = msg.get("role", "")
            content_text = _content_to_text(msg.get("content", ""))
            if role == "system":
                system_prompt = content_text
            elif role == "user":
                user_text = content_text

        if not user_text:
            self._send_json(400, {"ok": False, "error": "Missing user message"})
            return

        # 调用后端推理
        try:
            raw = CompanionAPIHandler._backend.infer(system_prompt, user_text, timeout=30.0)
        except Exception as e:
            _log(f"[桥接] LLM 推理异常: {type(e).__name__}: {e}")
            raw = None
        if not raw:
            _log(f"[桥接] LLM 推理失败: backend={type(CompanionAPIHandler._backend).__name__}, user={user_text[:80]!r}")
            self._send_json(500, {"ok": False, "error": "LLM inference failed"})
            return


        # 过滤掉 <think>...</think> 推理块，只保留最终回复发给 VTuber
        import re as _re
        raw = _re.sub(r'<think>[\s\S]*?</think>', '', raw).strip()

        model = body.get("model") or "desktop-auto-v1"
        if bool(body.get("stream", False)):
            self._send_chat_stream(raw, model=model)
            return

        # 包成 OpenAI 兼容响应格式
        self._send_json(200, {
            "id": "chatcmpl-001",
            "object": "chat.completion",
            "created": int(__import__("time").time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": raw,
                    },
                    "finish_reason": "stop",
                }
            ],
        })


# =======================
# 桥接线程（标准库 threading，更稳）
# =======================
class CompanionBridgeThread:
    """后台运行 HTTP Server 的标准库线程"""

    def __init__(self, port: int = DEFAULT_PORT):
        self.port = port
        self._thread: threading.Thread | None = None
        self._httpd: HTTPServer | None = None
        self._running = False
        # Qt Signal 风格回调（由 desktop_auto 注入，设为可调用对象）
        self.log_signal = None
        self.status_signal = None

    def update_config(self, config: dict) -> None:
        """更新运行时配置"""
        CompanionAPIHandler.config.update(config)

    def _emit_log(self, msg: str) -> None:
        if self.log_signal:
            try:
                self.log_signal.emit(msg)
            except Exception:
                pass
        _log(msg)

    def _emit_status(self, running: bool, msg: str) -> None:
        if self.status_signal:
            try:
                self.status_signal.emit(running, msg)
            except Exception:
                pass

    def start(self) -> None:
        cfg = CompanionAPIHandler.config
        if not cfg.get("enabled", False):
            self._emit_log("[桥接] 已禁用，不启动")
            self._emit_status(False, "已禁用")
            return

        try:
            self._httpd = HTTPServer(("127.0.0.1", self.port), CompanionAPIHandler)
            self._running = True
            self._emit_status(True, f"已启动，端口: {self.port}")
            self._emit_log(f"🔗 桌宠桥接 API 已启动 (端口: {self.port})")
            self._thread = threading.Thread(target=self._serve, daemon=True, name="CompanionBridge")
            self._thread.start()
        except OSError as e:
            self._emit_log(f"❌ 桌宠桥接 API 启动失败: {e}")
            self._emit_status(False, str(e))

    def _serve(self) -> None:
        """在独立线程中运行 HTTP 服务器（阻塞直到 stop）"""
        if self._httpd:
            self._httpd.serve_forever()

    def stop(self) -> None:
        self._running = False
        if self._httpd:
            try:
                self._httpd.shutdown()
                self._httpd.server_close()
                self._emit_log("⏹ 桌宠桥接 API 已停止")
            except Exception as e:
                self._emit_log(f"停止桥接时出错: {e}")
        self._emit_status(False, "已停止")
