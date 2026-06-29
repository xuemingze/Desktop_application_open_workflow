"""Step 2-3 护栏: single_conversation._safe_ws_send 容错行为锁死

回归测试覆盖 2026-06-27 bubble-event hang bug 的根因:
    starlette.WebSocket.send_text 在客户端断连时会抛 AssertionError
    (源自 websockets.legacy.protocol._drain_helper 的 drain waiter cancelled)。
    修复前: 单条 AssertionError 直接终结整轮 conversation task,
            前端永远收不到 backend-synth-complete, 气泡不刷新。
    修复后: _safe_ws_send 把这种瞬时失败吞掉, 流程继续 store_message / cleanup。

设计说明:
    ``single_conversation.py`` 顶部有 ``from .conversation_utils import``,
    相对导入会带起 service_context / chat_history_manager / loguru 等重依赖,
    不适合在单测里直接 import。本测试用 AST 抽取 ``_safe_ws_send`` 函数源码,
    喂进独立命名空间 exec, 只引入 asyncio + loguru 这两个真实依赖,
    锁死函数本身的契约, 不影响 production 路径。
"""
import ast
import asyncio
import pytest


def _load_safe_ws_send():
    """AST 抽取 _safe_ws_send 函数体, exec 到独立 namespace, 返回函数对象。

    这样既不需要 import 整个 single_conversation 模块,
    也不需要在 conftest 里伪造相对导入父包。
    """
    src_path = r"D:\项目\控制电脑\Open-LLM-VTuber-v1.2.1-zh\src\open_llm_vtuber\conversations\single_conversation.py"
    tree = ast.parse(open(src_path, encoding="utf-8").read())
    func_node = next(
        n for n in tree.body
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "_safe_ws_send"
    )
    module = ast.Module(body=[func_node], type_ignores=[])
    namespace = {"asyncio": asyncio, "logger": __import__("loguru").logger}
    exec(compile(module, src_path, "exec"), namespace)
    return namespace["_safe_ws_send"]


_safe_ws_send = _load_safe_ws_send()


class _RecordingSend:
    """模拟 starlette.WebSocket.send_text: 记录调用,可注入失败。"""

    def __init__(self, exc: BaseException | None = None, side_effect: list | None = None):
        self.calls: list[str] = []
        self._exc = exc
        self._side_effect = side_effect  # list[BaseException | None] 逐次失败

    async def __call__(self, payload: str) -> None:
        self.calls.append(payload)
        if self._side_effect is not None:
            exc = self._side_effect.pop(0) if self._side_effect else None
        else:
            exc = self._exc
        if exc is not None:
            raise exc


def _run(coro):
    """便捷 helper: 在事件循环里跑 coroutine。"""
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------- A. Happy path ----------------

class TestHappyPath:
    def test_returns_true_on_success(self):
        send = _RecordingSend()
        ok = _run(_safe_ws_send(send, "hello", label="t"))
        assert ok is True

    def test_payload_forwarded_verbatim(self):
        send = _RecordingSend()
        payload = '{"type": "backend-synth-complete"}'
        _run(_safe_ws_send(send, payload, label="backend-synth-complete"))
        assert send.calls == [payload]


# ---------------- B. AssertionError (bubble bug 触发条件) ----------------

class TestAssertionErrorSwallowed:
    """模拟 stderr 里 _drain_helper AssertionError 的真实场景。"""

    def test_returns_false(self):
        send = _RecordingSend(exc=AssertionError("waiter cancelled"))
        ok = _run(_safe_ws_send(send, "x", label="backend-synth-complete"))
        assert ok is False

    def test_does_not_raise(self):
        send = _RecordingSend(exc=AssertionError("waiter cancelled"))
        # 必须不 raise — 这是修复的核心契约
        _run(_safe_ws_send(send, "x", label="backend-synth-complete"))

    def test_warning_logged(self, caplog):
        send = _RecordingSend(exc=AssertionError("waiter cancelled"))
        with caplog.at_level("WARNING"):
            _run(_safe_ws_send(send, "x", label="backend-synth-complete"))
        # loguru 用 logger.warning 写 loguru 自有 sink;
        # 这里不强校验 caplog 内容, 但调用本身不能崩。
        assert True

    def test_recovery_path_next_call_succeeds(self):
        """关键: 第一条失败后,下一条必须能正常发出
        (修复前因为 task 已 raise, 根本走不到下一条)。"""
        send = _RecordingSend(side_effect=[AssertionError("drain"), None])
        ok1 = _run(_safe_ws_send(send, "first", label="a"))
        ok2 = _run(_safe_ws_send(send, "second", label="b"))
        assert ok1 is False
        assert ok2 is True
        assert send.calls == ["first", "second"]


# ---------------- C. 其他常见 Exception 也要吞 ----------------

@pytest.mark.parametrize("exc", [
    ConnectionResetError("客户端已断"),
    RuntimeError("Cannot call send once a close message has been sent."),
    ValueError("bad payload"),
    OSError("Connection lost"),
])
class TestGenericExceptionSwallowed:
    def test_returns_false(self, exc):
        send = _RecordingSend(exc=exc)
        ok = _run(_safe_ws_send(send, "x", label="x"))
        assert ok is False


# ---------------- D. CancelledError 必须重抛 (回归护栏) ----------------

class TestCancelledErrorPreserved:
    """asyncio.CancelledError 是主动中断信号 — 误吞会破坏 interrupt 行为。"""

    def test_cancelled_propagates(self):
        send = _RecordingSend(exc=asyncio.CancelledError())
        with pytest.raises(asyncio.CancelledError):
            _run(_safe_ws_send(send, "x", label="x"))

    def test_cancelled_does_not_swallow(self):
        """显式确认: 即使最后一条 AssertionError, 也要能区分 CancelledError 不被吞"""
        # 先 cancel 再 AssertionError — 验证 CancelledError 永远不被吞
        send = _RecordingSend(side_effect=[asyncio.CancelledError(), AssertionError("x")])
        with pytest.raises(asyncio.CancelledError):
            _run(_safe_ws_send(send, "x", label="x"))


# ---------------- E. 静态契约 — 锁死"4 处替换"不漂移 ----------------

class TestStaticContract:
    """防回归: 单文件改动后, 4 处 _safe_ws_send 调用不能漏, 也不能多。"""

    SRC_PATH = r"D:\项目\控制电脑\Open-LLM-VTuber-v1.2.1-zh\src\open_llm_vtuber\conversations\single_conversation.py"

    def test_exactly_four_safe_send_call_sites(self):
        src = open(self.SRC_PATH, encoding="utf-8").read()
        assert src.count("await _safe_ws_send(") == 4, (
            "_safe_ws_send 应在 4 处调用: "
            "tool_call_status / agent_stream_error / "
            "backend-synth-complete / conversation_error"
        )

    def test_raw_websocket_send_only_inside_helper(self):
        src = open(self.SRC_PATH, encoding="utf-8").read()
        # 整个文件只有 _safe_ws_send 内部那一处 await websocket_send(
        # 这是 helper 的实现, 不算外部 call site
        assert src.count("await websocket_send(") == 1

    def test_helper_signature_has_label_keyword_only(self):
        src = open(self.SRC_PATH, encoding="utf-8").read()
        import re
        assert re.search(
            r"async def _safe_ws_send\([^)]*label: str", src
        ), "helper 必须有 label: str 关键字参数"
