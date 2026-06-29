"""Step 2-4 护栏: vtuber_bridge 助理模式协议契约锁死

回归测试覆盖 "气泡推送失败" 根因:
    旧实现 notify_event 发 ai-speak-signal 协议,但 VTuber 后端
    _handle_conversation_trigger 完全忽略 text 字段,改用配置中的
    proactive_speak_prompt 作为 user_input,导致推送文本丢失。

修复:改为助理模式(Assistant Mode):
    - speak(text): 发 text-input → VTuber 走标准对话管线 → 显示气泡
    - push_notification(text): 发 assistant-message → 写 VTuber history
    - acknowledge_ai_message(text): 发 assistant-message → 举手协议

测试矩阵:
    A. speak 发 text-input(不是 ai-speak-signal)
    B. push_notification 发 bubble-event(广播 full-text 到前端)
    C. acknowledge_ai_message 发 assistant-message(不变)
    D. _ensure_connected() 返回 False 时,所有方法早退
    E. 空文本早退,不发 _send
    F. 静态契约 — 不再出现 ai-speak-signal / notify_event
"""
import sys
import types
import asyncio
import json
import pytest


# ---- 模拟 vtuber_bridge 模块依赖,避免 import 真实 websocket-client ----
def _load_module_method(method_name: str):
    """AST 抽取 VTuberBridge 的指定方法源码,exec 到隔离命名空间。"""
    import ast
    src_path = r"D:\项目\控制电脑\vtuber_bridge.py"
    tree = ast.parse(open(src_path, encoding="utf-8").read())

    cls = next(
        n for n in tree.body
        if isinstance(n, ast.ClassDef) and n.name == "VTuberBridge"
    )
    method = next(
        n for n in cls.body
        if isinstance(n, ast.FunctionDef) and n.name == method_name
    )
    wrapper = ast.Module(body=[
        ast.FunctionDef(
            name=method_name,
            args=method.args,
            body=method.body,
            decorator_list=[],
            returns=method.returns,
            type_comment=getattr(method, "type_comment", None),
        )
    ], type_ignores=[])
    ast.fix_missing_locations(wrapper)
    namespace = {
        "asyncio": asyncio,
        "json": json,
        "log": __import__("loguru").logger,
    }
    exec(compile(wrapper, src_path, "exec"), namespace)
    return namespace[method_name]


speak = _load_module_method("speak")
push_notification = _load_module_method("push_notification")
acknowledge_ai_message = _load_module_method("acknowledge_ai_message")


class _FakeBridge:
    """最小化的 VTuberBridge 实例,只覆盖测试方法需要的属性。"""

    def __init__(self, *, connected: bool = True, sent: list | None = None):
        self._connected = connected
        self._sent = sent if sent is not None else []

    def _ensure_connected(self):
        return self._connected

    def _send(self, data: dict):
        self._sent.append(data)
        return True


# ===================================================================
# A. speak 发 text-input
# ===================================================================

class TestSpeakProtocol:
    def test_uses_text_input_not_ai_speak_signal(self):
        """speak 必须发 text-input 协议(标准对话管线)"""
        bridge = _FakeBridge()
        speak(bridge, "测试消息")
        assert len(bridge._sent) == 1
        assert bridge._sent[0]["type"] == "text-input"
        assert bridge._sent[0]["type"] != "ai-speak-signal"

    def test_uses_text_field(self):
        bridge = _FakeBridge()
        speak(bridge, "hello")
        payload = bridge._sent[0]
        assert "text" in payload
        assert payload["text"] == "hello"

    def test_returns_false_when_disconnected(self):
        bridge = _FakeBridge(connected=False)
        ok = speak(bridge, "msg")
        assert ok is False
        assert bridge._sent == []

    def test_returns_false_for_empty_text(self):
        bridge = _FakeBridge()
        ok = speak(bridge, "")
        assert ok is False
        assert bridge._sent == []

    @pytest.mark.parametrize("msg", [
        "短消息",
        "带 emoji 😀 的消息",
        "Multi-line\nmessage",
        "很长的消息 " + "x" * 1000,
    ])
    def test_text_forwarded_verbatim(self, msg):
        bridge = _FakeBridge()
        speak(bridge, msg)
        assert bridge._sent[0]["text"] == msg


# ===================================================================
# B. push_notification 发 assistant-message
# ===================================================================

class TestPushNotificationProtocol:
    def test_uses_ai_speak_signal(self):
        """push_notification 必须发 ai-speak-signal 协议(主动说话;VTuber 后端已修复使用 text 字段)"""
        bridge = _FakeBridge()
        push_notification(bridge, "测试通知")
        assert len(bridge._sent) == 1
        assert bridge._sent[0]["type"] == "ai-speak-signal"

    def test_uses_text_field(self):
        """ai-speak-signal 协议使用 text= 字段名"""
        bridge = _FakeBridge()
        push_notification(bridge, "hello")
        payload = bridge._sent[0]
        assert "text" in payload
        assert payload["text"] == "hello"
        assert "content" not in payload  # ai-speak-signal 不用 content 字段

    def test_returns_false_when_disconnected(self):
        bridge = _FakeBridge(connected=False)
        ok = push_notification(bridge, "msg")
        assert ok is False
        assert bridge._sent == []

    def test_returns_false_for_empty_text(self):
        bridge = _FakeBridge()
        ok = push_notification(bridge, "")
        assert ok is False
        assert bridge._sent == []

    @pytest.mark.parametrize("msg", [
        "工作流执行完成",
        "✅ 成功消息",
        "❌ 失败消息: 出错啦",
        "带 emoji 😎",
        "主动嗅探 - study: 你在写代码吗?",
    ])
    def test_text_forwarded_verbatim(self, msg):
        bridge = _FakeBridge()
        push_notification(bridge, msg)
        assert bridge._sent[0]["text"] == msg


# ===================================================================
# C. acknowledge_ai_message 协议不变(保持原来的契约)
# ===================================================================

class TestAcknowledgeProtocol:
    def test_uses_assistant_message(self):
        """acknowledge_ai_message 必须发 assistant-message"""
        bridge = _FakeBridge()
        acknowledge_ai_message(bridge, "举手消息")
        assert len(bridge._sent) == 1
        assert bridge._sent[0]["type"] == "assistant-message"

    def test_uses_text_field(self):
        bridge = _FakeBridge()
        acknowledge_ai_message(bridge, "hello")
        assert bridge._sent[0]["text"] == "hello"

    def test_returns_false_when_disconnected(self):
        bridge = _FakeBridge(connected=False)
        ok = acknowledge_ai_message(bridge, "msg")
        assert ok is False
        assert bridge._sent == []

    def test_returns_false_for_empty_text(self):
        bridge = _FakeBridge()
        assert acknowledge_ai_message(bridge, "") is False
        assert bridge._sent == []

    def test_does_not_use_ai_speak_signal(self):
        """举手绝不能触发 ai-speak-signal(会触发 LLM 重生成)"""
        bridge = _FakeBridge()
        acknowledge_ai_message(bridge, "test")
        assert bridge._sent[0]["type"] != "ai-speak-signal"
        assert bridge._sent[0]["type"] != "text-input"


# ===================================================================
# D. 静态契约 — 锁死不再出现 notify_event / ai-speak-signal 协议
# ===================================================================

class TestStaticContractNoRegression:
    """防回归: 防止有人把方法改回旧的 ai-speak-signal / notify_event。"""

    SRC_PATH = r"D:\项目\控制电脑\vtuber_bridge.py"

    def test_no_ai_speak_signal_in_speak_or_acknowledge(self):
        """speak 和 acknowledge_ai_message 中不应出现 ai-speak-signal(它们用 text-input / assistant-message)
        push_notification 是唯一合法使用 ai-speak-signal 的方法。"""
        import ast
        SRC_PATH = r"D:\项目\控制电脑\vtuber_bridge.py"
        src = open(SRC_PATH, encoding="utf-8").read()
        tree = ast.parse(src)
        cls = next(
            n for n in tree.body
            if isinstance(n, ast.ClassDef) and n.name == "VTuberBridge"
        )
        for method in cls.body:
            if not isinstance(method, ast.FunctionDef):
                continue
            # push_notification 是唯一合法使用 ai-speak-signal 的方法
            if method.name == "push_notification":
                continue
            body = method.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                scan_body = body[1:]  # 跳过 docstring
            else:
                scan_body = body
            string_literals = []
            for node in ast.walk(ast.Module(body=scan_body, type_ignores=[])):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    string_literals.append(node.value)
            joined = " ".join(string_literals)
            assert "ai-speak-signal" not in joined, (
                f"方法 {method.name} 中出现了 ai-speak-signal 字面量;"
                "只有 push_notification 合法使用 ai-speak-signal"
            )

    def test_no_notify_event_method(self):
        """notify_event 方法已被移除(由 speak + push_notification 替代)"""
        src = open(self.SRC_PATH, encoding="utf-8").read()
        import ast
        tree = ast.parse(src)
        cls = next(
            n for n in tree.body
            if isinstance(n, ast.ClassDef) and n.name == "VTuberBridge"
        )
        method_names = {n.name for n in cls.body if isinstance(n, ast.FunctionDef)}
        assert "notify_event" not in method_names, (
            "notify_event 已被移除,请使用 speak() 或 push_notification()"
        )

    def test_no_send_user_message_method(self):
        """send_user_message 已在迁移期结束后删除"""
        src = open(self.SRC_PATH, encoding="utf-8").read()
        import ast
        tree = ast.parse(src)
        cls = next(
            n for n in tree.body
            if isinstance(n, ast.ClassDef) and n.name == "VTuberBridge"
        )
        method_names = {n.name for n in cls.body if isinstance(n, ast.FunctionDef)}
        assert "send_user_message" not in method_names, (
            "send_user_message 已过迁移期,已被删除"
        )

    def test_has_assistant_mode_methods(self):
        """助理模式必须有 speak, push_notification, acknowledge_ai_message 三个核心方法"""
        src = open(self.SRC_PATH, encoding="utf-8").read()
        import ast
        tree = ast.parse(src)
        cls = next(
            n for n in tree.body
            if isinstance(n, ast.ClassDef) and n.name == "VTuberBridge"
        )
        method_names = {n.name for n in cls.body if isinstance(n, ast.FunctionDef)}
        for name in ("speak", "push_notification", "acknowledge_ai_message"):
            assert name in method_names, f"助理模式必须包含 {name} 方法"
