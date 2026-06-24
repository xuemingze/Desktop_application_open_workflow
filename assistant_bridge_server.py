"""
assistant_bridge_server.py — VTuber 桥接服务(无 GUI / 无 PySide6)

伪装成标准 OpenAI /v1/chat/completions 服务器(SSE 流式)。
让 VTuber 通过普通 OpenAI 客户端协议调用,实际由 AssistantCore 路由到 AI 助手 + MCP 工具。

启动方式:
  from assistant_bridge_server import AssistantBridgeServer
  server = AssistantBridgeServer(core=core_instance)
  server.start()
  # ... 长期持有 server 引用,防 GC ...
  server.stop()

或者直接命令行启动(单进程模式):
  python assistant_bridge_server.py
"""

import json
import logging
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from typing import Optional

from assistant_core import AssistantCore

logger = logging.getLogger(__name__)


class OpenAIBridgeHandler(BaseHTTPRequestHandler):
    """伪装成 OpenAI /v1/chat/completions 的 HTTP handler"""

    # HTTP/1.1 必开启 chunked transfer encoding (SSE 必需)
    protocol_version = "HTTP/1.1"
    # 关掉 Nagle,小包立即发送 (降低 SSE 首字节延迟)
    disable_nagle_algorithm = True

    core: Optional[AssistantCore] = None  # 由外部 AssistantBridgeServer.start() 注入

    def do_POST(self):  # noqa: N802 (BaseHTTPRequestHandler 约定)
        if self.path == "/v1/chat/completions":
            self._handle_chat_completions()
        elif self.path == "/v1/models":
            self._handle_models()
        elif self.path == "/health":
            self._handle_health()
        else:
            self.send_error(404, f"Unknown path: {self.path}")

    def do_GET(self):  # noqa: N802
        # /health 和 /v1/models 同时接受 GET (curl 探活)
        if self.path == "/health":
            self._handle_health()
        elif self.path == "/v1/models":
            self._handle_models()
        else:
            self.send_error(404, f"Unknown path: {self.path}")

    # ---------- /health ----------
    def _handle_health(self):
        payload = json.dumps({
            "status": "ok",
            "core_loaded": self.core is not None,
        }).encode("utf-8")
        self._send_json(200, payload)

    # ---------- /v1/models ----------
    def _handle_models(self):
        """伪装 models 列表,让 OpenAI 客户端探活成功"""
        if not self.core:
            self.send_error(503, "AssistantCore not loaded")
            return
        payload = json.dumps({
            "object": "list",
            "data": [
                {"id": self.core.model, "object": "model", "owned_by": "local"}
            ],
        }).encode("utf-8")
        self._send_json(200, payload)

    # ---------- /v1/chat/completions ----------
    def _handle_chat_completions(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception as e:
            self.send_error(400, f"Bad request: {e}")
            return

        if not self.core:
            self.send_error(503, "AssistantCore not loaded")
            return

        messages = body.get("messages", [])
        stream = body.get("stream", False)

        # 从 OpenAI 格式提取最后一条 user 消息 + 历史
        user_text = ""
        chat_history: list = []
        system_prompt: Optional[str] = None
        for m in messages:
            role = m.get("role", "")
            content = m.get("content", "")
            if role == "system":
                # 只取最后一个 system 作为 system_prompt (OpenAI 习惯)
                system_prompt = content
            elif role == "user":
                # 最后一个 user 才是当前问题,之前的 user 进 history
                if user_text:
                    chat_history.append({"role": "user", "content": content})
                else:
                    user_text = content
            elif role in ("assistant", "tool"):
                chat_history.append({"role": role, "content": content})

        context = {"chat_history": chat_history}

        if stream:
            self._stream_chat(user_text, context, system_prompt)
        else:
            self._non_stream_chat(user_text, context, system_prompt)

    # ---------- SSE 流式 ----------
    def _stream_chat(self, user_text: str, context: dict, system_prompt: Optional[str] = None):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")  # 关掉 nginx 缓冲
        self.end_headers()

        try:
            for event in self.core.process_chat_request(
                user_text, context=context, system_prompt=system_prompt
            ):
                et = event["type"]
                chunk_content = ""

                if et == "text":
                    # 已过滤表情的纯文本
                    chunk_content = event["content"]
                elif et == "expression":
                    # 主动把表情标签重新注入文本流,让 VTuber 解析触发 Live2D
                    chunk_content = f"{event['hint']} "
                elif et == "tool_start":
                    # 工具开始 (写到日志/UI 可选),不输出到 VTuber(避免污染 TTS)
                    logger.info("[bridge] tool start: %s", event.get("tool_name"))
                    continue
                elif et == "tool_finish":
                    logger.info("[bridge] tool finish: %s", event.get("tool_name"))
                    continue
                elif et == "error":
                    chunk_content = f"\n[错误: {event['content']}]"
                elif et == "done":
                    break

                if chunk_content:
                    response_chunk = {
                        "id": f"chatcmpl-{context.get('request_id', 'bridge')}",
                        "object": "chat.completion.chunk",
                        "choices": [{"index": 0, "delta": {"content": chunk_content}}],
                    }
                    self.wfile.write(
                        f"data: {json.dumps(response_chunk, ensure_ascii=False)}\n\n".encode("utf-8")
                    )
                    self.wfile.flush()

            # 结束
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            # 客户端断开,正常情况
            logger.info("[bridge] client disconnected")
        except Exception as e:
            logger.exception("[bridge] stream error")
            try:
                err_chunk = {"choices": [{"delta": {"content": f"\n[bridge 错误: {e}]"}}]}
                self.wfile.write(
                    f"data: {json.dumps(err_chunk, ensure_ascii=False)}\n\n".encode("utf-8")
                )
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
            except Exception:
                pass

    # ---------- 非流式 ----------
    def _non_stream_chat(self, user_text: str, context: dict, system_prompt: Optional[str] = None):
        text_parts: list = []
        last_error: Optional[str] = None
        for event in self.core.process_chat_request(
            user_text, context=context, system_prompt=system_prompt
        ):
            et = event["type"]
            if et == "text":
                text_parts.append(event["content"])
            elif et == "expression":
                # 非流式:表情不入文本(GUI 调用方一般能拿到独立信号)
                continue
            elif et == "error":
                last_error = event["content"]
            elif et in ("tool_start", "tool_finish", "done"):
                continue

        full_text = "".join(text_parts)
        if last_error:
            full_text = f"{full_text}\n[错误: {last_error}]" if full_text else f"[错误: {last_error}]"

        payload = json.dumps({
            "id": "chatcmpl-bridge",
            "object": "chat.completion",
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": full_text},
                "finish_reason": "stop",
            }],
        }, ensure_ascii=False).encode("utf-8")
        self._send_json(200, payload)

    # ---------- 工具 ----------
    def _send_json(self, code: int, payload: bytes):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):  # noqa: A002
        # 静默默认 stderr 输出,改走 logger
        logger.debug(format, *args)


class AssistantBridgeServer:
    """
    桥接服务管理器。
    必须持有实例引用,防止 GC 后端口被释放。
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 16299,
        core: Optional[AssistantCore] = None,
    ):
        self.host = host
        self.port = port
        self.core = core or AssistantCore()
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[Thread] = None

    def start(self) -> None:
        if self._server is not None:
            logger.warning("Bridge already running")
            return

        OpenAIBridgeHandler.core = self.core
        self._server = HTTPServer((self.host, self.port), OpenAIBridgeHandler)
        self._thread = Thread(target=self._server.serve_forever, daemon=True, name="assistant-bridge")
        self._thread.start()
        logger.info(
            "VTuber Bridge 启动成功: http://%s:%d/v1/chat/completions (model=%s)",
            self.host, self.port, self.core.model,
        )

    def stop(self) -> None:
        if self._server is None:
            return
        logger.info("VTuber Bridge 停止中...")
        self._server.shutdown()
        self._server.server_close()
        if self._thread:
            self._thread.join(timeout=3)
        self._server = None
        self._thread = None
        logger.info("VTuber Bridge 已关闭。")

    def is_running(self) -> bool:
        return self._server is not None


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    server = AssistantBridgeServer()
    server.start()
    print(f"Bridge listening on http://{server.host}:{server.port}", flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    try:
        # 阻塞主线程,直到 Ctrl+C
        if hasattr(signal, "SIGINT"):
            signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
        while True:
            import time
            time.sleep(86400)
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()