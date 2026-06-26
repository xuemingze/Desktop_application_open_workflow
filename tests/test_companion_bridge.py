# -*- coding: utf-8 -*-
"""Step 2-2G 护栏: companion_bridge.py 桌宠桥接层 (简化版, 专注核心不变量)

覆盖范围:
  - 4 个端点路由 (do_GET/do_POST)
  - thinking 过滤 (教训 #1 双保险 — 核心不可变量)
  - _log / _get_data_dir / CompanionBridgeThread 启停
  - 源不变量: 不依赖 Qt / 5 消费方引用面 / 顶层 import
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture
def cb_module():
    import companion_bridge as cb
    return cb


# ---------- TestConstants ----------

class TestConstants:
    def test_default_port_is_16260(self, cb_module):
        assert cb_module.DEFAULT_PORT == 16260

    def test_log_prefix_in_source(self, cb_module):
        """_log 输出前缀 [CompanionBridge]"""
        src = (REPO_ROOT / "companion_bridge.py").read_text(encoding="utf-8")
        assert '[CompanionBridge]' in src

    def test_get_data_dir_returns_user_data_dir(self, cb_module):
        result = cb_module._get_data_dir()
        from data_paths import USER_DATA_DIR
        assert result == USER_DATA_DIR


# ---------- TestCompanionAPIHandlerBase ----------

class TestCompanionAPIHandlerBase:
    def test_subclass_of_base_http_request_handler(self, cb_module):
        from http.server import BaseHTTPRequestHandler
        assert issubclass(cb_module.CompanionAPIHandler, BaseHTTPRequestHandler)

    def test_handler_has_required_methods(self, cb_module):
        for m in ["do_GET", "do_POST", "do_OPTIONS", "log_message",
                  "_send_json", "_check_token", "_handle_status",
                  "_handle_models", "_handle_run_workflow", "_handle_chat_completions"]:
            assert hasattr(cb_module.CompanionAPIHandler, m), f"missing: {m}"

    def test_log_message_disabled_in_source(self, cb_module):
        """log_message 默认实现是 pass (禁用 apache 日志)"""
        import inspect
        src = inspect.getsource(cb_module.CompanionAPIHandler.log_message)
        assert "pass" in src


# ---------- TestDoGetRouting ----------

class TestDoGetRouting:
    def _make_handler(self, cb_module, path):
        h = cb_module.CompanionAPIHandler.__new__(cb_module.CompanionAPIHandler)
        h.path = path
        h.config = cb_module.CompanionAPIHandler.config
        h._handle_status = MagicMock()
        h._handle_models = MagicMock()
        h._send_json = MagicMock()
        return h

    def test_do_get_routes_to_status(self, cb_module):
        h = self._make_handler(cb_module, "/api/status")
        h.do_GET()
        h._handle_status.assert_called_once()

    def test_do_get_routes_to_models(self, cb_module):
        h = self._make_handler(cb_module, "/v1/models")
        h.do_GET()
        h._handle_models.assert_called_once()

    def test_do_get_404_for_unknown_path(self, cb_module):
        h = self._make_handler(cb_module, "/unknown/path")
        h.do_GET()
        h._send_json.assert_called_once_with(404, {"ok": False, "error": "Not Found"})


# ---------- TestDoPostRouting ----------

class TestDoPostRouting:
    def _make_handler(self, cb_module, path):
        h = cb_module.CompanionAPIHandler.__new__(cb_module.CompanionAPIHandler)
        h.path = path
        h.config = cb_module.CompanionAPIHandler.config
        h.headers = {}
        h._check_token = MagicMock(return_value=True)
        h._handle_run_workflow = MagicMock()
        h._handle_chat_completions = MagicMock()
        h._send_json = MagicMock()
        return h

    def test_do_post_routes_to_run_workflow(self, cb_module):
        h = self._make_handler(cb_module, "/api/action/run_workflow")
        h.do_POST()
        h._check_token.assert_called_once()
        h._handle_run_workflow.assert_called_once()

    def test_do_post_routes_to_chat_completions(self, cb_module):
        h = self._make_handler(cb_module, "/v1/chat/completions")
        h.do_POST()
        h._handle_chat_completions.assert_called_once()

    def test_do_post_rejects_unauthorized(self, cb_module):
        h = self._make_handler(cb_module, "/api/action/run_workflow")
        h._check_token = MagicMock(return_value=False)
        h.do_POST()
        h._handle_run_workflow.assert_not_called()
        h._send_json.assert_called_once_with(401, {"ok": False, "error": "Unauthorized"})

    def test_do_post_404_for_unknown_path(self, cb_module):
        h = self._make_handler(cb_module, "/api/foo")
        h.do_POST()
        h._send_json.assert_called_once_with(404, {"ok": False, "error": "Not Found"})


# ---------- TestCheckToken ----------

class TestCheckToken:
    def test_check_token_passes_when_disabled(self, cb_module):
        h = cb_module.CompanionAPIHandler.__new__(cb_module.CompanionAPIHandler)
        h.config = {"token": ""}
        h.headers = {"Authorization": ""}
        assert h._check_token() is True

    def test_check_token_passes_when_correct(self, cb_module):
        h = cb_module.CompanionAPIHandler.__new__(cb_module.CompanionAPIHandler)
        h.config = {"token": "secret123"}
        h.headers = {"Authorization": "Bearer secret123"}
        assert h._check_token() is True

    def test_check_token_fails_when_wrong(self, cb_module):
        h = cb_module.CompanionAPIHandler.__new__(cb_module.CompanionAPIHandler)
        h.config = {"token": "secret123"}
        h.headers = {"Authorization": "Bearer wrong"}
        assert h._check_token() is False


# ---------- TestCompanionBridgeThread ----------

class TestCompanionBridgeThread:
    def test_default_port_is_16260(self, cb_module):
        t = cb_module.CompanionBridgeThread()
        assert t.port == 16260

    def test_default_port_override(self, cb_module):
        t = cb_module.CompanionBridgeThread(port=9999)
        assert t.port == 9999

    def test_initial_state(self, cb_module):
        t = cb_module.CompanionBridgeThread()
        assert t._thread is None
        assert t._httpd is None
        assert t._running is False
        assert t.log_signal is None
        assert t.status_signal is None

    def test_update_config_merges_into_class_config(self, cb_module):
        t = cb_module.CompanionBridgeThread()
        cb_module.CompanionAPIHandler.config.clear()
        t.update_config({"enabled": True, "token": "abc"})
        assert cb_module.CompanionAPIHandler.config["enabled"] is True
        assert cb_module.CompanionAPIHandler.config["token"] == "abc"

    def test_start_skipped_when_disabled(self, cb_module):
        cb_module.CompanionAPIHandler.config = {"enabled": False}
        t = cb_module.CompanionBridgeThread()
        t._emit_log = MagicMock()
        t._emit_status = MagicMock()
        t.start()
        t._emit_log.assert_called_once()
        assert "已禁用" in t._emit_log.call_args[0][0]
        assert t._thread is None

    def test_stop_when_not_running_is_safe(self, cb_module):
        t = cb_module.CompanionBridgeThread()
        t._emit_log = MagicMock()
        t._emit_status = MagicMock()
        t.stop()  # 不抛
        assert t._running is False


# ---------- TestThinkingFilter (核心不变量) ----------

class TestThinkingFilter:
    """教训 #1 双保险: companion_bridge 的 chat_completions 必须剥离 thinking 块"""

    def test_thinking_pattern_present(self):
        """源码含 re.sub(<think>...</think>) 模式"""
        src = (REPO_ROOT / "companion_bridge.py").read_text(encoding="utf-8")
        # 必含 re.sub + <think> + </think>
        assert "re.sub" in src
        assert "<think>" in src
        assert "</think>" in src

    def test_thinking_strip_in_chat_completions(self):
        """thinking 过滤在 _handle_chat_completions 内 (而不是别处)"""
        src = (REPO_ROOT / "companion_bridge.py").read_text(encoding="utf-8")
        # 找到 _handle_chat_completions 函数体
        import re
        m = re.search(r"def _handle_chat_completions.*?(?=\n    def |\nclass )", src, re.DOTALL)
        assert m, "_handle_chat_completions 未找到"
        body = m.group(0)
        assert "<think>" in body, "thinking 过滤必须在 _handle_chat_completions 内"

    def test_strip_runs_before_send(self):
        """strip 必须发生在 _send_json/_send_chat_stream 之前"""
        src = (REPO_ROOT / "companion_bridge.py").read_text(encoding="utf-8")
        import re
        m = re.search(r"def _handle_chat_completions.*?(?=\n    def |\nclass )", src, re.DOTALL)
        body = m.group(0)
        strip_pos = body.find("<think>")
        send_pos = body.find("_send_json(200")
        assert strip_pos > 0 and send_pos > 0
        assert strip_pos < send_pos, "thinking strip 必须在 _send_json(200) 之前"


# ---------- TestSourceInvariants ----------

class TestSourceInvariants:
    def _src(self):
        return (REPO_ROOT / "companion_bridge.py").read_text(encoding="utf-8")

    def test_no_import_desktop_auto(self):
        src = self._src()
        assert "import desktop_auto" not in src
        assert "from desktop_auto" not in src

    def test_no_import_context_chat(self):
        src = self._src()
        assert "from context_chat" not in src

    def test_imports_user_profile(self):
        src = self._src()
        assert "from user_profile import get_active_profile_summary" in src

    def test_imports_data_paths(self):
        src = self._src()
        assert "from data_paths import USER_DATA_DIR" in src

    def test_imports_mcp_embedded(self):
        src = self._src()
        assert "from mcp_embedded import run_workflow_sync" in src

    def test_imports_log_bus(self):
        src = self._src()
        assert "from log_bus import log_bus" in src

    def test_imports_activity_log(self):
        src = self._src()
        assert "from activity_log import ActivityLogDB" in src

    def test_uses_threading_thread(self):
        src = self._src()
        assert "threading.Thread" in src

    def test_uses_http_server(self):
        src = self._src()
        assert "HTTPServer" in src
        assert "BaseHTTPRequestHandler" in src

    def test_no_qt_import_lines(self):
        """架构关键: companion_bridge 走标准库, 不能引入 Qt"""
        import re
        src = self._src()
        import_lines = [ln for ln in src.splitlines()
                        if re.match(r'^\s*(import|from)\s', ln)]
        combined = "\n".join(import_lines)
        assert "PySide6" not in combined
        assert "PyQt" not in combined


# ---------- TestConsumerInvariants ----------

class TestConsumerInvariants:
    def _load(self, name):
        return (REPO_ROOT / name).read_text(encoding="utf-8")

    def test_desktop_auto_uses_app_bridges_for_companion(self):
        src = self._load("desktop_auto.py")
        assert "self.bridges._companion_bridge" in src

    def test_context_tab_references_companion_port(self):
        """context_tab 引用 companion_bridge 端口 16260"""
        src_bytes = (REPO_ROOT / "context_tab.py").read_bytes()
        assert b"16260" in src_bytes or b"companion" in src_bytes.lower() or "vtuber" in src_bytes.decode("utf-8", errors="replace").lower()

    def test_context_tab_calls_notify_event(self):
        """context_tab 应调用 notify_event (推送气泡入口)"""
        text = (REPO_ROOT / "context_tab.py").read_text(encoding="utf-8", errors="replace")
        assert "notify_event" in text

    def test_build_spec_includes_companion_bridge(self):
        src = self._load("build.spec")
        assert "'companion_bridge'" in src or '"companion_bridge"' in src


# ---------- TestBubbleEventKey (for bug fix verification) ----------

class TestBubbleEventKey:
    """为 '气泡进入 VTuber 聊天上下文' bug 修复预留不变量"""

    def test_vtuber_bridge_has_notify_event(self):
        """vtuber_bridge 提供 notify_event (气泡事件推送, 不进 chat context)"""
        import vtuber_bridge
        assert hasattr(vtuber_bridge.VTuberBridge, "notify_event")

    def test_vtuber_bridge_should_have_send_user_message(self):
        """新增: 气泡修复后必须存在 send_user_message (text-input 类型, 进 chat context)"""
        import vtuber_bridge
        assert hasattr(vtuber_bridge.VTuberBridge, "send_user_message"), \
            "BUG 修复未到位: vtuber_bridge 缺 send_user_message 方法, 气泡无法进入 VTuber 聊天上下文"

    def test_context_tab_should_call_send_user_message(self):
        """新增: context_tab 推送气泡时也应调用 send_user_message"""
        text = (REPO_ROOT / "context_tab.py").read_text(encoding="utf-8", errors="replace")
        assert "send_user_message" in text, \
            "BUG 修复未到位: context_tab 未调用 send_user_message, 气泡不进 VTuber 聊天上下文"