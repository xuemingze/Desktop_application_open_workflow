"""上下文感知 - AI 意图推理层

职责：
1. 接收通过 Gatekeeper 的 ContextCapsule
2. 在独立 QThread 中调用后端模型（Hermes/Qianxia/任何 OpenAI 兼容 API）
3. 解析返回的 JSON（带 Markdown 剥壳容错）
4. 把结果（ToastIntent）emit 回主线程，让 ToastManager 展示

绝不阻塞主线程。
"""
from __future__ import annotations

import json
import re
from typing import Optional

from PySide6.QtCore import QObject, QThread, Signal, Slot, Qt

from context_sensor import ContextCapsule
from context_toast import ToastIntent


SYSTEM_PROMPT = """你是一个桌面辅助 AI。用户刚刚在【{window_title}】中复制了一段内容。
【内容】：{clipboard_text}

请判断用户可能的意图，并决定是否需要主动推荐工具或动作。
只在你有较高把握时才返回 need_action: true。

必须输出以下 JSON 格式，禁止输出其他内容：
{{
  "need_action": true或false,
  "intent": "一句话描述用户意图",
  "suggested_action": "mcp工具名如 search_local_files / run_workflow / launch_shortcut",
  "action_param": "工具参数，如搜索关键词或工作流名",
  "message": "对用户的友好提示语，控制在20字以内"
}}"""


def parse_intent_response(raw: str) -> Optional[dict]:
    """从大模型原始回复中提取 JSON dict。多层剥壳，绝不抛异常。"""
    if not raw:
        return None
    text = raw.strip()

    # 第一步：剥 Markdown 代码块包装
    m = re.search(r"```(?:json|JSON)?\s*\n?([\s\S]+?)\n?```", text)
    if m:
        text = m.group(1).strip()

    # 第二步：尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 第三步：尝试找首个 { 到末尾 } 的子串
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        candidate = text[start : end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    return None


# ---------------------------------------------------------------------------
# 后端调用适配器（可替换）
# ---------------------------------------------------------------------------
class LLMBackend:
    """抽象后端接口"""

    def infer(self, system_prompt: str, user_text: str, timeout: float = 5.0) -> Optional[str]:
        raise NotImplementedError


class EchoBackend(LLMBackend):
    """用于本地测试的兜底后端——不做任何 AI 调用"""

    def infer(self, system_prompt: str, user_text: str, timeout: float = 5.0) -> Optional[str]:
        text = user_text.strip()
        if re.match(r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$", text):
            return json.dumps({
                "need_action": True,
                "intent": "检测到 IP 地址",
                "suggested_action": "search_local_files",
                "action_param": text,
                "message": f"发现 IP {text}，要搜索相关配置吗？",
            }, ensure_ascii=False)
        if "Error" in user_text or "error" in user_text or "Traceback" in user_text:
            return json.dumps({
                "need_action": True,
                "intent": "检测到报错信息",
                "suggested_action": "search_local_files",
                "action_param": text[:30],
                "message": "发现报错，要搜索相关日志吗？",
            }, ensure_ascii=False)
        return json.dumps({"need_action": False}, ensure_ascii=False)


class OpenAICompatibleBackend(LLMBackend):
    """OpenAI 兼容协议后端（适用于 Hermes/Qianlia 等本地代理）"""

    def __init__(self, base_url: str = "http://127.0.0.1:11434/v1",
                 api_key: str = "EMPTY", model: str = "qwen2.5:7b"):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    def infer(self, system_prompt: str, user_text: str, timeout: float = 5.0) -> Optional[str]:
        try:
            import urllib.request
            url = f"{self.base_url}/chat/completions"
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text},
                ],
                "temperature": 0.1,
                "stream": False,
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            choices = data.get("choices") or []
            if not choices:
                return None
            return choices[0].get("message", {}).get("content")
        except Exception:
            return None


# ---------------------------------------------------------------------------
# Worker（运行在 QThread 中）
# ---------------------------------------------------------------------------
class InferenceWorker(QObject):
    """AI 推理 Worker——在独立 QThread 中运行

    通过 process(capsule) 槽接收任务，通过 finished/skipped 信号返回结果。
    """

    finished = Signal(ToastIntent)
    skipped = Signal(str)
    # 外部通过这个信号提交任务——Signal 自动跨线程 queued，避开 Q_ARG(object) 的限制
    _submit = Signal(object)

    def __init__(self, backend: LLMBackend):
        super().__init__()
        self._backend = backend
        # 将 _submit 信号在 worker 内部连接到 process 槽
        self._submit.connect(self.process)

    @Slot(object)
    def process(self, capsule):
        if not capsule.clipboard_text or not capsule.clipboard_text.strip():
            self.skipped.emit("空内容")
            return

        user_text = capsule.clipboard_text
        sys_prompt = SYSTEM_PROMPT.format(
            window_title=capsule.foreground_window or "(未知窗口)",
            clipboard_text=user_text[:500],
        )

        raw = self._backend.infer(sys_prompt, user_text)
        if not raw:
            self.skipped.emit("后端无响应")
            return

        data = parse_intent_response(raw)
        if not data:
            self.skipped.emit("JSON 解析失败")
            return

        if not data.get("need_action"):
            self.skipped.emit("need_action=false")
            return

        intent = ToastIntent(
            intent=data.get("intent", ""),
            message=data.get("message", ""),
            suggested_action=data.get("suggested_action", ""),
            action_param=data.get("action_param", ""),
        )
        self.finished.emit(intent)


# ---------------------------------------------------------------------------
# Manager（主线程组件）
# ---------------------------------------------------------------------------
class ContextAgent(QObject):
    """AI 推理主线程管理——负责接收 capsule、派发给 Worker"""

    intent_ready = Signal(ToastIntent)
    log_signal = Signal(str)

    def __init__(self, backend: Optional[LLMBackend] = None, parent=None):
        super().__init__(parent)
        self._backend = backend or EchoBackend()
        self._thread = QThread()
        self._worker = InferenceWorker(self._backend)
        self._worker.moveToThread(self._thread)

        # Worker 信号 → Manager 槽（在主线程接收，自动跨线程 queued）
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.skipped.connect(self._on_worker_skipped)

        self._thread.start()

    def process(self, capsule: ContextCapsule):
        """主线程入口——用 Signal 发送任务给 Worker（跨线程自动 queued，非阻塞）"""
        # Signal 默认是 queued connection（跨线程），避开 Q_ARG(object) 的 QMetaType 问题
        self._worker._submit.emit(capsule)

    def _on_worker_finished(self, intent: ToastIntent):
        self.intent_ready.emit(intent)
        self.log_signal.emit(f"[AI] 推荐: {intent.intent} → {intent.suggested_action}({intent.action_param})")

    def _on_worker_skipped(self, reason: str):
        self.log_signal.emit(f"[AI] 跳过: {reason}")

    def set_backend(self, backend: LLMBackend):
        """热替换后端（需要重启 Worker）"""
        self.shutdown()
        self._backend = backend
        self.__init__(backend=backend, parent=self.parent())

    def shutdown(self):
        if self._thread:
            self._thread.quit()
            self._thread.wait(2000)
