r"""Step 2-2D: assistant_core.py thinking 过滤行为锁死 (与 companion_bridge.py:367 同模板)

覆盖范围 (7 项):
1. strip_thinking 移除 <think>...</think> 单行块
2. strip_thinking 移除 <thinking>...</thinking> 多行块
3. strip_thinking 同时处理多个 thinking 块
4. strip_thinking 对无 thinking 块的纯文本透传
5. strip_thinking 对 None/空字符串安全
6. AssistantCore.process_chat_request 流式产出不含 <think> 残留
7. build_chat_system_prompt 的 system prompt 含 "禁止输出 <think>" 强约束 (LLM 端双保险)

执行方式:
    cd /d D:\项目\控制电脑
    .venv\Scripts\python -m pytest tests/test_assistant_core.py -v
"""
import pathlib
import re
import sys

import pytest


# 让测试能直接 import 同目录的模块
ROOT = pathlib.Path(r'D:\项目\控制电脑')
sys.path.insert(0, str(ROOT))

from assistant_core import (
    THINKING_PATTERN,
    strip_thinking,
    AssistantCore,
)
from context_chat import build_chat_system_prompt


# ---------- A. THINKING_PATTERN 模板本身 ----------

class TestThinkingPatternTemplate:
    """锁死正则模板,防止被无意改写为更宽松的版本(例如忘记 '?ing')。"""

    def test_pattern_matches_think(self):
        assert THINKING_PATTERN.search("<think>内部</think>") is not None

    def test_pattern_matches_thinking(self):
        assert THINKING_PATTERN.search("<thinking>内部</thinking>") is not None

    def test_pattern_multiline(self):
        text = "<think>\nline1\nline2\n</think>"
        assert THINKING_PATTERN.search(text) is not None

    def test_pattern_case_sensitive_lowercase(self):
        # 大写 THINK 不应被匹配 (Qwen 等模型实际输出的是小写)
        assert THINKING_PATTERN.search("<THINK>no</THINK>") is None


# ---------- B. strip_thinking 行为 ----------

class TestStripThinking:
    """strip_thinking 是 process_chat_request 与 TTS 前的最后一道闸。"""

    def test_removes_single_think_block(self):
        out = strip_thinking("<think>用户在问天气</think>今天晴,25 度。")
        assert "<think>" not in out
        assert "用户" not in out
        assert "今天晴" in out

    def test_removes_thinking_multiline_block(self):
        raw = (
            "<thinking>\n"
            "让我分析一下:用户需要打开浏览器\n"
            "工具是 launch_application\n"
            "</thinking>\n"
            "好的,这就帮你打开浏览器。"
        )
        out = strip_thinking(raw)
        assert "<thinking>" not in out
        assert "分析" not in out
        assert "好的" in out
        assert out.startswith("好的")

    def test_removes_multiple_blocks(self):
        raw = "<think>a</think>中<think>b</think>尾"
        out = strip_thinking(raw)
        assert "<think>" not in out
        assert "a" not in out and "b" not in out
        assert "中" in out and "尾" in out

    def test_pure_text_passthrough(self):
        text = "今天天气不错,适合出门散步。"
        assert strip_thinking(text) == text

    def test_handles_empty_and_none(self):
        # 双保险: None 不应抛异常,空串返回空串
        assert strip_thinking("") == ""
        assert strip_thinking(None) == ""

    def test_strips_surrounding_whitespace(self):
        # 防止 reasoning 块吃掉后留下前导/尾部空格
        out = strip_thinking("<think>x</think>  重要结论  ")
        assert out == "重要结论"


# ---------- C. AssistantCore.process_chat_request 端到端流 ----------

class _FakeCore(AssistantCore):
    """绕过真实 LLM HTTP, 直接返回预先编排的 raw。"""
    def __init__(self, raw_response: str):
        # 不走父类 __init__,只留最少的属性
        self._raw = raw_response
        self.max_turns = 1
        self.web_enabled = False
        # parse_intent_response 兼容: 让 _parse_intent_lenient 解析
        from context_chat import TOOL_DEFINITIONS, TOOL_DISPATCH
        from context_agent import parse_intent_response
        self.TOOL_DEFINITIONS = TOOL_DEFINITIONS
        self.TOOL_DISPATCH = TOOL_DISPATCH
        self.build_chat_system_prompt = build_chat_system_prompt
        self.parse_intent_response = parse_intent_response

    def _call_llm(self, messages):
        return self._raw


class TestProcessChatRequestThinkingFilter:
    """锁死端到端: 即便 LLM 输出了 thinking 块, yield 的 text 事件里也不应出现。"""

    RAW_WITH_THINK = (
        "<think>"
        "用户想开浏览器,我要用 launch_application"
        "</think>"
        '{"action": null, "reply": "好的,正在为您打开浏览器。"}'
    )

    def _collect_text(self, raw):
        core = _FakeCore(raw)
        events = list(core.process_chat_request("帮我打开浏览器"))
        return [e for e in events if e.get("type") == "text"]

    def test_text_event_has_no_think_residue(self):
        texts = self._collect_text(self.RAW_WITH_THINK)
        joined = "".join(t["content"] for t in texts)
        assert "<think>" not in joined
        assert "</think>" not in joined
        assert "launch_application" not in joined  # reasoning 内容也不能漏

    def test_text_event_keeps_real_reply(self):
        texts = self._collect_text(self.RAW_WITH_THINK)
        joined = "".join(t["content"] for t in texts)
        assert "正在为您打开浏览器" in joined


# ---------- D. System Prompt 强约束 (LLM 端双保险) ----------

class TestSystemPromptAntiThinkingConstraint:
    """build_chat_system_prompt 的输出必须包含明确的"禁止输出 think"约束,
    与客户端正则 strip_thinking 形成双保险。"""

    def test_prompt_mentions_think_tag(self):
        prompt = build_chat_system_prompt(web_enabled=False)
        # 必须出现 <think 或 <thinking 字面量
        assert "<think" in prompt or "<thinking" in prompt, (
            "system prompt 缺失 '禁止输出 <think>' 强约束, 客户端过滤一旦失效将裸奔"
        )

    def test_prompt_contains_ban_phrase(self):
        prompt = build_chat_system_prompt(web_enabled=False)
        # 中文禁止语义: 至少含一个 "禁止" / "不得" / "绝不能" 关键词
        assert any(kw in prompt for kw in ("禁止", "不得", "绝不能")), (
            "system prompt 缺少明确的'禁止输出'语义关键词"
        )

    def test_prompt_dual_insurance_clause(self):
        prompt = build_chat_system_prompt(web_enabled=False)
        # 双保险提示词: 提示模型客户端会用正则剥离, 以增强其顺从度
        # (允许关键词任一即可)
        assert any(
            kw in prompt
            for kw in ("双保险", "正则", "强制剥离", "客户端", "源头避免")
        ), "system prompt 缺少'双保险'语义提示"
