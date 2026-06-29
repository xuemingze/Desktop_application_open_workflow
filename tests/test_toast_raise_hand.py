"""
气泡-举手-发言 护栏测试(Step 2-3A,B+A 方案 — 助理模式)

目标行为(Assistant Mode):
  - 主动嗅探触发气泡时,用 push_notification 写 VTuber history
  - 用户点击气泡(举手)= 把气泡文案以 AI 身份写入 VTuber 后端 chat history
  - UI 区分:已举手气泡显示"已举手 ✓"标记
  - 新协议:assistant-message(后端已支持,前端用 push_notification)
  - notify_event / send_user_message 已移除

锁住的核心契约:
  T1. _on_behavior_question 不调 send_user_message,只调 push_notification
  T2. on_toast_clicked 调 acknowledge_ai_message(intent.message)
  T3. acknowledge_ai_message 发 assistant-message 协议,不动 push_notification/speak
  T4. _append_assistant 文本包含"已举手 ✓"标记
  T5. notify_event / send_user_message 已从 vtuber_bridge 移除
"""
from __future__ import annotations

import re
import sys
import warnings
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# 确保项目根目录在 sys.path,否则 import vtuber_bridge 会失败
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTEXT_TAB = REPO_ROOT / "context_tab.py"
CONTEXT_CHAT = REPO_ROOT / "context_chat.py"
VTUBER_BRIDGE = REPO_ROOT / "vtuber_bridge.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _method_body(src: str, name: str) -> str:
    """提取方法体直到下一个 def/class 或文件末尾或注释分隔线,容错处理末尾方法"""
    pattern = rf"def {name}\(self[^)]*\)[^:]*:(.*?)(?=\n    def |\nclass |\n    # =+|\Z)"
    m = re.search(pattern, src, re.DOTALL)
    if not m:
        return ""
    return m.group(1)


# ---------------------------------------------------------------------------
# T1. _on_behavior_question 不调 send_user_message,调 push_notification
# ---------------------------------------------------------------------------

class TestNoPollutionOnProactiveSniff:
    """主动嗅探推送必须不污染 user 上下文"""

    def test_on_behavior_question_does_not_call_send_user_message(self):
        src = _read(CONTEXT_TAB)
        body = _method_body(src, "_on_behavior_question")
        assert body, "_on_behavior_question 方法体未找到"
        assert "send_user_message" not in body, (
            "_on_behavior_question 仍然调 send_user_message —— "
            "这会污染 VTuber 后端 chat history(把主动嗅探当 user 输入)"
        )

    def test_on_behavior_question_calls_push_notification(self):
        src = _read(CONTEXT_TAB)
        body = _method_body(src, "_on_behavior_question")
        assert body
        assert "push_notification" in body, (
            "_on_behavior_question 必须调 push_notification 写 VTuber history"
        )

    def test_on_behavior_question_does_not_call_notify_event(self):
        """助理模式:notify_event 已移除,用 push_notification 替代"""
        src = _read(CONTEXT_TAB)
        body = _method_body(src, "_on_behavior_question")
        assert body
        assert "notify_event" not in body, (
            "notify_event 已移除,应使用 push_notification"
        )


# ---------------------------------------------------------------------------
# T2. on_toast_clicked 调 acknowledge_ai_message(intent.message)
# ---------------------------------------------------------------------------

class TestRaiseHandSendsAssistantMessage:
    """用户点击气泡 = 举手 = 把气泡文案以 AI 身份写进后端 history"""

    def test_on_toast_clicked_calls_acknowledge_ai_message(self):
        src = _read(CONTEXT_CHAT)
        body = _method_body(src, "on_toast_clicked")
        assert body, "on_toast_clicked 方法体未找到"
        assert "acknowledge_ai_message" in body, (
            "on_toast_clicked 必须调 acknowledge_ai_message —— "
            "举手时把气泡文案作为 AI 已说过的话传给 VTuber 后端"
        )
        assert "intent.message" in body, (
            "acknowledge_ai_message 应该收到 intent.message(气泡文案)"
        )

    def test_on_toast_clicked_writes_assistant_role(self):
        src = _read(CONTEXT_CHAT)
        body = _method_body(src, "on_toast_clicked")
        assert body
        # 举手必须把气泡文案以 assistant 角色写到本项目 chat UI
        assert "_append_assistant" in body, (
            "举手后应该把气泡文案以 assistant 角色写入本项目 chat UI"
        )


# ---------------------------------------------------------------------------
# T3. acknowledge_ai_message 协议契约
# ---------------------------------------------------------------------------

class TestAcknowledgeAiMessageContract:
    """acknowledge_ai_message 必须发 assistant-message 协议,不污染"""

    def test_acknowledge_ai_message_exists(self):
        src = _read(VTUBER_BRIDGE)
        assert "def acknowledge_ai_message" in src, (
            "vtuber_bridge 必须有 acknowledge_ai_message 方法 —— "
            "对应 VTuber 后端 assistant-message 协议"
        )

    def test_acknowledge_ai_message_sends_assistant_message_type(self):
        src = _read(VTUBER_BRIDGE)
        body = _method_body(src, "acknowledge_ai_message")
        assert body, "acknowledge_ai_message 方法体未找到"
        assert '"assistant-message"' in body or "'assistant-message'" in body, (
            "acknowledge_ai_message 必须发 type='assistant-message'"
        )

    def test_acknowledge_ai_message_does_not_trigger_llm(self):
        """关键契约:举手不触发新一轮 LLM,否则用户没说话也会收到 AI 续说"""
        src = _read(VTUBER_BRIDGE)
        body = _method_body(src, "acknowledge_ai_message")
        assert body
        assert "send_user_message" not in body, (
            "acknowledge_ai_message 不能调 send_user_message(那是污染源)"
        )
        # 助理模式:不会出现 ai-speak-signal / notify_event / speak
        assert "ai-speak-signal" not in body, (
            "acknowledge_ai_message 不能发 ai-speak-signal(会触发后端 LLM 重新生成内容)"
        )
        assert "speak" not in body, (
            "acknowledge_ai_message 不能调 speak(会触发 text-input 管线)"
        )
        assert "push_notification" not in body, (
            "acknowledge_ai_message 不能调 push_notification(语义冲突)"
        )


# ---------------------------------------------------------------------------
# T4. UI 区分:已举手气泡显示"已举手 ✓"
# ---------------------------------------------------------------------------

class TestRaiseHandUIFeedback:
    """B+A 的 'B':举手后 UI 给用户反馈"""

    def test_on_toast_clicked_appends_raised_marker(self):
        src = _read(CONTEXT_CHAT)
        body = _method_body(src, "on_toast_clicked")
        assert body
        assert "已举手" in body or "raised" in body.lower(), (
            "举手后 UI 应该显示'已举手 ✓'标记,给用户反馈(B+A 方案的 B 部分)"
        )


# ---------------------------------------------------------------------------
# T5. notify_event / send_user_message 已从 vtuber_bridge 移除
# ---------------------------------------------------------------------------

class TestOldProtocolsRemoved:
    """notify_event 和 send_user_message 已在助理模式中移除"""

    def test_notify_event_not_in_vtuber_bridge(self):
        src = _read(VTUBER_BRIDGE)
        assert "def notify_event" not in src, (
            "notify_event 已移除(ai-speak-signal 协议会丢失文本),请用 push_notification"
        )

    def test_send_user_message_not_in_vtuber_bridge(self):
        src = _read(VTUBER_BRIDGE)
        assert "def send_user_message" not in src, (
            "send_user_message 已过迁移期,已被删除"
        )


# ---------------------------------------------------------------------------
# 行为级测试:用真实类实例验证方法签名 & 调用关系
# ---------------------------------------------------------------------------

class TestBridgeBehavior:
    """用真实类实例验证方法签名 & 调用的协议类型"""

    def _build_bridge(self):
        from vtuber_bridge import VTuberBridge
        return VTuberBridge(enabled=True)

    def test_acknowledge_ai_message_signature(self):
        bridge = self._build_bridge()
        assert hasattr(bridge, "acknowledge_ai_message"), "acknowledge_ai_message 方法必须存在"
        import inspect
        sig = inspect.signature(bridge.acknowledge_ai_message)
        assert "text" in sig.parameters, "acknowledge_ai_message 必须有 text 参数"

    def test_acknowledge_ai_message_calls_send_with_assistant_message_type(self):
        bridge = self._build_bridge()
        bridge._send = MagicMock(return_value=True)
        bridge._ensure_connected = MagicMock(return_value=True)

        bridge.acknowledge_ai_message("看到你打开了 XXX,是想做 XXX 吗?")

        bridge._send.assert_called_once()
        payload = bridge._send.call_args[0][0]
        assert payload["type"] == "assistant-message", (
            f"必须发 assistant-message,实际发了 {payload.get('type')!r}"
        )
        assert payload["text"] == "看到你打开了 XXX,是想做 XXX 吗?"

    def test_acknowledge_ai_message_does_not_trigger_llm(self):
        """关键:acknowledge 不能调 send_user_message(污染源)也不能发 ai-speak-signal(LLM 重生成)"""
        bridge = self._build_bridge()
        bridge._send = MagicMock(return_value=True)
        bridge._ensure_connected = MagicMock(return_value=True)

        bridge.acknowledge_ai_message("test")

        # 检查所有发出去的 payload
        for call in bridge._send.call_args_list:
            payload = call[0][0]
            assert payload["type"] not in ("text-input", "ai-speak-signal"), (
                f"acknowledge 不能发 {payload['type']} —— 会污染或触发 LLM 重生成"
            )


# ---------------------------------------------------------------------------
# 协议级测试:确保 vtuber_bridge 在调用失败时不抛异常(降级)
# ---------------------------------------------------------------------------

class TestAcknowledgeGracefulDegradation:
    """举手降级:WebSocket 没连/方法不存在时,on_toast_clicked 不应崩"""

    def test_acknowledge_returns_false_when_not_connected(self):
        from vtuber_bridge import VTuberBridge
        bridge = VTuberBridge(enabled=False)  # disabled → _ensure_connected 返回 False
        result = bridge.acknowledge_ai_message("test")
        assert result is False, "未连接时 acknowledge_ai_message 应返回 False,不抛异常"

    def test_acknowledge_returns_false_for_empty_text(self):
        from vtuber_bridge import VTuberBridge
        bridge = VTuberBridge(enabled=True)
        bridge._send = MagicMock(return_value=True)
        bridge._ensure_connected = MagicMock(return_value=True)
        assert bridge.acknowledge_ai_message("") is False
        assert bridge.acknowledge_ai_message(None) is False
        bridge._send.assert_not_called()  # 空文本根本不该调 _send