"""
vtuber_bridge.py - Open-LLM-VTuber 桥接模块

通过 WebSocket 连接到 Open-LLM-VTuber 后端 (ws://127.0.0.1:12393/client-ws)
发送 text-input 消息触发 AI 对话。

后端默认端口: 12393
"""
import json
import logging
import threading
import time
import asyncio

log = logging.getLogger("vtuber_bridge")

# websocket-client 在 requirements.txt 中已声明
try:
    import websocket
    HAS_WS = True
except ImportError:
    HAS_WS = False


class VTuberBridge:
    """
    通过 WebSocket 连接到 Open-LLM-VTuber 的桥接器。

    Open-LLM-VTuber 后端端口: 12393 (conf.yaml 中配置)
    WebSocket 端点: ws://<host>:<port>/client-ws
    """

    def __init__(
        self,
        backend_url: str = "http://127.0.0.1:12393",
        enabled: bool = False,
    ):
        # 存储 HTTP URL，展示给用户，连接时转换为 WS
        self._http_url = backend_url.rstrip("/")
        self.backend_url = backend_url
        self.enabled = enabled
        self._ws = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._running = False
        self._retry_count = 0
        self._max_retries = 3

    def _connect(self) -> bool:
        """在新线程中建立 WebSocket 连接"""
        if not HAS_WS:
            log.warning("[VTuberBridge] websocket-client 未安装")
            return False
        # HTTP URL -> WS URL
        ws_url = self._http_url.replace("http://", "ws://").replace("https://", "wss://")
        ws_url = f"{ws_url}/client-ws"
        try:
            ws = websocket.WebSocketApp(
                ws_url,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
                on_open=self._on_open,
            )
            self._ws = ws
            self._running = True
            self._thread = threading.Thread(target=ws.run_forever, daemon=True)
            self._thread.start()
            log.info(f"[VTuberBridge] WebSocket 连接线程已启动: {self.backend_url}")
            return True
        except Exception as e:
            log.warning(f"[VTuberBridge] WebSocket 连接失败: {e}")
            return False

    def _disconnect(self):
        """断开 WebSocket 连接"""
        with self._lock:
            self._running = False
            if self._ws:
                try:
                    self._ws.close()
                except Exception:
                    pass
                self._ws = None

    def _on_message(self, ws, message: str):
        """收到服务端消息（通常不需要处理）"""
        try:
            data = json.loads(message)
            log.debug(f"[VTuberBridge] 收到消息: {data.get('type', message[:100])}")
        except Exception:
            pass

    def _on_error(self, ws, error):
        log.warning(f"[VTuberBridge] WebSocket 错误: {error}")
        self._retry_count += 1

    def _on_close(self, ws, close_status_code, close_msg):
        log.info(f"[VTuberBridge] WebSocket 关闭: {close_status_code} {close_msg}")
        self._running = False

    def _on_open(self, ws):
        log.info("[VTuberBridge] WebSocket 已连接")
        self._retry_count = 0

    def _send(self, data: dict) -> bool:
        """发送 JSON 消息到 WebSocket"""
        if not self._running or not self._ws:
            return False
        try:
            with self._lock:
                self._ws.send(json.dumps(data, ensure_ascii=False))
            return True
        except Exception as e:
            log.debug(f"[VTuberBridge] 发送失败: {e}")
            return False

    def _ensure_connected(self) -> bool:
        """确保连接活跃，断了则重连"""
        if not self.enabled:
            return False
        with self._lock:
            if self._running and self._ws:
                return True
        # 需要重连
        if self._retry_count < self._max_retries:
            return self._connect()
        return False

    def notify_event(self, message: str) -> bool:
        """
        向桌宠推送感知事件，触发 AI 回复 + TTS + 动画。
        """
        if not self._ensure_connected():
            return False
        ok = self._send({
            "type": "text-input",
            "text": message,
        })
        if ok:
            log.debug(f"[VTuberBridge] 已发送: {message[:50]}")
        return ok

    def speak(self, text: str) -> bool:
        """直接让桌宠说一段话"""
        if not self._ensure_connected():
            return False
        return self._send({
            "type": "ai-speak-signal",
            "text": text,
        })

    def set_expression(self, expression: str) -> bool:
        """设置桌宠表情"""
        if not self._ensure_connected():
            return False
        return self._send({
            "type": "expression-change",
            "expression": expression,
        })

    def play_motion(self, motion: str) -> bool:
        """播放指定动作"""
        if not self._ensure_connected():
            return False
        return self._send({
            "type": "motion-change",
            "motion": motion,
        })

    def close(self):
        """关闭桥接，释放资源"""
        self._disconnect()
