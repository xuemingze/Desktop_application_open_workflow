"""
vtuber_bridge.py - Open-LLM-VTuber 桥接模块
"""
import json
import logging
import urllib.request
import urllib.error

log = logging.getLogger("vtuber_bridge")


class VTuberBridge:
    def __init__(self, backend_url: str = "http://127.0.0.1:18888", enabled: bool = False):
        self.backend_url = backend_url.rstrip("/")
        self.enabled = enabled

    def _post(self, path: str, data: dict) -> bool:
        if not self.enabled:
            return False
        try:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                f"{self.backend_url}{path}",
                data=body,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status in (200, 201)
        except Exception as e:
            log.debug(f"[VTuberBridge] POST {path} failed: {e}")
        return False

    def notify_event(self, message: str) -> bool:
        """推送感知事件到桌宠"""
        return self._post("/api/chat", {"message": message, "user": "desktop-auto"})

    def speak(self, text: str) -> bool:
        """直接让桌宠说话"""
        return self._post("/api/speak", {"text": text})

    def set_expression(self, expression: str) -> bool:
        return self._post("/api/expression", {"expression": expression})

    def play_motion(self, motion: str) -> bool:
        return self._post("/api/motion", {"motion": motion})
