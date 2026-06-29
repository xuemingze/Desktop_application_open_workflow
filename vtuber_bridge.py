"""
vtuber_bridge.py - Open-LLM-VTuber 桥接模块（助理模式）

通过 WebSocket 连接到 Open-LLM-VTuber 后端 (ws://127.0.0.1:12393/client-ws)
以"助理模式"工作: 本系统(Desktop-Auto Assistant)作为 AI 大脑,
VTuber 作为前端渲染层。

协议说明 (Assistant Mode):
  - speak(text):   发送 text-input → VTuber 走完整对话管线
                    → 调用本系统的 AssistantBridge (port 16299)
                    → VTuber 前端显示气泡 + TTS + Live2D
  - push_notification(text): 发送 assistant-message
                    只写 VTuber chat history,不触发 LLM,不显示气泡
                    (配合本地 ToastBubble 使用)
  - acknowledge_ai_message(text): 发送 assistant-message
                    举手发言专用,与 push_notification 同协议,语义不同

后端默认端口: 12393
"""
import json
import logging
import threading
import time

log = logging.getLogger("vtuber_bridge")

# websocket-client 在 requirements.txt 中已声明
try:
    import websocket
    HAS_WS = True
except ImportError:
    HAS_WS = False


class VTuberBridge:
    """
    通过 WebSocket 连接到 Open-LLM-VTuber 的桥接器(助理模式)。

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
        """在新线程中建立 WebSocket 连接（自动重连: VTuber 后端随时启动均可连接）"""
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
            self._thread = threading.Thread(
                target=ws.run_forever,
                kwargs={"reconnect": 5},  # 断线后每 5 秒自动重连
                daemon=True,
            )
            self._thread.start()
            log.info(f"[VTuberBridge] WebSocket 连接线程已启动(自动重连): {self.backend_url}")
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
            log.warning(f"[VTuberBridge] 发送失败: {e}")
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

    # =================================================================
    # 助理模式核心 API
    # =================================================================

    def speak(self, text: str) -> bool:
        """
        让桌宠说话——通过标准 text-input 协议触发完整对话管线。

        执行流程:
          1. 发送 text-input → VTuber 后端
          2. VTuber 调用 LLM 后端(即本系统的 AssistantBridge :16299)
          3. AssistantBridge 生成回复
          4. VTuber 前端显示气泡 + TTS + Live2D

        注意: text 会以"用户消息"身份进入 VTuber chat,但回复由我们的
        助理桥接器控制,最终气泡显示的是助理的回复内容。

        适用场景: 助理主动发起的对话(主动嗅探结果、定时提醒等)
        """
        if not text:
            return False
        if not self._ensure_connected():
            return False
        ok = self._send({
            "type": "text-input",
            "text": text,
        })
        if ok:
            log.debug(f"[VTuberBridge] speak(text-input) sent: {text[:50]}")
        return ok

    def push_notification(self, text: str) -> bool:
        """
        推送主动发言——通过 ai-speak-signal 协议让 VTuber 主动说话。

        VTuber 后端 _handle_conversation_trigger (已修复):
          1. 使用 data["text"] 作为 LLM user_input(不再忽略)
          2. 先发 full-text 到前端(气泡即时显示)
          3. 调用 LLM 后端(本系统的 AssistantBridge :16299)
          4. 助理桥接器回复 → 前端气泡 + TTS + Live2D

        适用场景: 主动嗅探结果、工作流执行状态、后台通知等需要展示在
        VTuber 前端的气泡内容。
        """
        if not text:
            return False
        if not self._ensure_connected():
            return False
        ok = self._send({
            "type": "ai-speak-signal",
            "text": text,
        })
        if ok:
            log.debug(f"[VTuberBridge] push_notification(ai-speak-signal) sent: {text[:50]}")
        return ok

    def acknowledge_ai_message(self, text: str) -> bool:
        """
        举手发言:把指定文本以 AI 身份写入 VTuber 后端 chat history。

        适用场景:用户点击主动嗅探推送的气泡 = "举手" = 把气泡文案作为
        AI 已说过的话写入历史,让后续 LLM 推理能引用"我刚才问了这个问题"。

        关键契约:
          - 发 type='assistant-message'(对应后端 assistant-message 协议)
          - 不触发新一轮 LLM(否则用户没说话 AI 也会续说)
          - 失败时返回 False,不抛异常(降级不影响主流程)
        """
        if not text:
            return False
        if not self._ensure_connected():
            return False
        ok = self._send({
            "type": "assistant-message",
            "text": text,
        })
        if ok:
            log.debug(f"[VTuberBridge] assistant-message sent: {text[:50]}")
        return ok

    # =================================================================
    # 其他控制 API
    # =================================================================

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
