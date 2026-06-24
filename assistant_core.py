"""
assistant_core.py — 纯逻辑层大脑(无 PySide6 依赖)

复用 context_chat.py / context_agent.py 已经验证的工具集和系统提示词,
可被 GUI (context_chat.py) 和 Bridge (assistant_bridge_server.py) 同时消费。

事件类型 (yield):
  {"type": "text", "content": "..."}                       # 模型自然语言回复(已过滤表情标签)
  {"type": "tool_start", "tool_name": "...", "args": {...}}
  {"type": "tool_finish", "tool_name": "...", "result": {...}}
  {"type": "expression", "hint": "[neutral]"}              # 表情标签(Live2D 用)
  {"type": "error", "content": "..."}
  {"type": "done"}
"""

import json
import logging
import re
import uuid
import urllib.request
import urllib.error
from typing import Generator, Dict, Any, List, Optional

logger = logging.getLogger(__name__)

EXPRESSION_PATTERN = re.compile(
    r"\[(neutral|anger|disgust|fear|joy|smirk|sadness|surprise|thinking)\]"
)


def _parse_intent_lenient(raw: str) -> Optional[dict]:
    """双保险解析: 如果上游 parse_intent_response 仍返回 None, 本函数在
    assistant_core 内部再试一次宽容解析 (控制字符 + 尾部逗号)。"""
    if not raw:
        return None
    text = raw.strip()
    # 剥 Markdown 包装
    m = re.search(r"```(?:json|JSON)?\s*\n?([\s\S]+?)\n?```", text)
    if m:
        text = m.group(1).strip()
    # 找首个 { 到末尾 }
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    candidate = text[start : end + 1]
    # 过滤尾部逗号
    candidate = re.sub(r",\s*([\]}])", r"\1", candidate)
    try:
        return json.loads(candidate, strict=False)
    except json.JSONDecodeError:
        return None

# VTuber 专用增强 system prompt: 告诉模型支持的表情标签 + 注入使用示例
# 当调用方传入含 "VTuber" 关键词的 system_prompt 时,会自动追加这段
VTUBER_EXPRESSION_HINT = (
    "\n\n## 表情与动作\n"
    "你正在驱动一个虚拟形象 VTuber。请在回复文本中按需插入以下表情标签,"
    "Live2D 模型会根据标签切换表情。注意:标签仅作为语义标记,实际播放的语音(TTS)会被自动过滤掉这些标签本身。\n"
    "可用标签:[neutral] [anger] [disgust] [fear] [joy] [smirk] [sadness] [surprise] [thinking]\n"
    '示例:"[smirk] 哼,既然你都开口了,那我就大发慈悲帮你查一下。[neutral]"'
)


class AssistantCore:
    """
    复用 context_chat 的工具集和 chat 流程(基于自定义 JSON action 协议)。
    不依赖 PySide6,可以在任意线程 / 进程里跑。
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:16260/v1",
        api_key: str = "EMPTY",
        model: str = "desktop-auto-v1",
        timeout: float = 30.0,
        max_turns: int = 3,
        web_enabled: Optional[bool] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_turns = max_turns
        self.web_enabled = web_enabled

        # 延迟导入,避免循环依赖 / GUI 副作用
        from context_chat import (
            TOOL_DEFINITIONS,
            TOOL_DISPATCH,
            build_chat_system_prompt,
        )
        from context_agent import parse_intent_response

        self.TOOL_DEFINITIONS = TOOL_DEFINITIONS
        self.TOOL_DISPATCH = TOOL_DISPATCH
        self.build_chat_system_prompt = build_chat_system_prompt
        self.parse_intent_response = parse_intent_response

    # ---------- 内部:调 LLM (非流式) ----------
    def _call_llm(self, messages: List[Dict[str, str]]) -> Optional[str]:
        """单次非流式 chat 调用。"""
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
            "stream": False,
        }
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            choices = data.get("choices") or []
            if not choices:
                return None
            return choices[0].get("message", {}).get("content")
        except urllib.error.HTTPError as e:
            # 精准捕获 HTTP 错误,读取真实 body(可能是 "Token limit exceeded" 等)
            error_body = e.read().decode("utf-8", errors="ignore")
            logger.error("LLM HTTP 错误 %s: %s", e.code, error_body)
            raise Exception(f"API 请求失败 ({e.code}): {error_body}")
        except Exception as e:
            logger.error("LLM 调用发生未知错误: %s", e)
            raise

    # ---------- 主入口 ----------
    def process_chat_request(
        self,
        user_text: str,
        context: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        """
        处理单轮 chat 请求,产出事件流。
        context: {"chat_history": [...]} 可选,历史 messages
        system_prompt: 自定义 system prompt;若不传,用 context_chat 的 build_chat_system_prompt
        """
        history = (context or {}).get("chat_history", []) or []
        sys_prompt = system_prompt or self.build_chat_system_prompt(
            web_enabled=self.web_enabled
        )
        # VTuber 模式:自动追加表情提示
        if system_prompt and "VTuber" in system_prompt:
            sys_prompt = sys_prompt + VTUBER_EXPRESSION_HINT

        messages: List[Dict[str, str]] = [{"role": "system", "content": sys_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_text})

        try:
            for turn in range(self.max_turns):
                # 【改进 1-A】第二轮开始前先给过渡文本,避免 VTuber 呆站
                if turn > 0:
                    yield {"type": "text", "content": "好的,请稍等,我正在处理..."}
                    yield {"type": "expression", "hint": "[thinking]"}

                raw = self._call_llm(messages)
                if raw is None:
                    yield {"type": "error", "content": "后端无响应"}
                    return

                parsed = self.parse_intent_response(raw) or _parse_intent_lenient(raw) or {}
                action = parsed.get("action")
                reply = (parsed.get("reply") or "").strip()
                args = parsed.get("args") or {}

                # 表情识别 (从 reply 和 raw 中提取)
                for m in EXPRESSION_PATTERN.findall(reply or raw or ""):
                    yield {"type": "expression", "hint": f"[{m}]"}

                # 过滤表情标签,避免 TTS 念出 "[smile]" 这种字眼
                clean_reply = EXPRESSION_PATTERN.sub("", reply).strip()
                clean_raw_fallback = (
                    EXPRESSION_PATTERN.sub("", raw[:1000]).strip() if raw else ""
                )

                # 没工具调用,直接结束
                if not action or action not in self.TOOL_DISPATCH:
                    if clean_reply:
                        yield {"type": "text", "content": clean_reply}
                    elif clean_raw_fallback:
                        yield {"type": "text", "content": clean_raw_fallback}
                    return

                # 有 reply 先抛一段自然语言
                if clean_reply:
                    yield {"type": "text", "content": clean_reply}
                else:
                    # 【改进 1-B】AI 决定调工具但没给 reply,手动补一句让 VTuber 有话说
                    yield {"type": "text", "content": f"正在为您执行 {action} 操作..."}

                yield {"type": "tool_start", "tool_name": action, "args": args}

                try:
                    result = self.TOOL_DISPATCH[action](args)
                except Exception as e:
                    logger.exception("Tool %s failed", action)
                    result = {"ok": False, "error": str(e)}

                yield {"type": "tool_finish", "tool_name": action, "result": result}

                # 准备下一轮:把 raw + 工具结果喂回去
                messages.append({"role": "assistant", "content": raw})
                # 防止单次 result 过大撑爆 Context Window
                result_str = json.dumps(result, ensure_ascii=False)
                if len(result_str) > 6000:
                    result_str = result_str[:6000] + "...(输出过长已截断)"

                if turn < self.max_turns - 1:
                    instruction = (
                        "请决定下一步操作:如果任务已完成,请将 action 设为 null 并回复纯文本;"
                        "如果需要其他工具请继续输出 JSON。"
                    )
                else:
                    instruction = (
                        "执行完毕。这是最后一轮交互。请基于工具结果给用户一个简洁友好的最终回复"
                        "(必须用纯文本,action 设为 null,不再调用工具)。"
                    )
                messages.append({
                    "role": "user",
                    "content": f"工具 {action} 执行完毕。结果:\n```json\n{result_str}\n```\n{instruction}",
                })

            yield {"type": "done"}

        except Exception as e:
            logger.exception("process_chat_request failed")
            yield {"type": "error", "content": str(e)}


def collect_result(
    core: AssistantCore,
    user_text: str,
    context: dict = None,
    system_prompt: str = None,
) -> Dict[str, Any]:
    """把生成器收敛成单一 dict(给 Bridge HTTP 接口用)。"""
    text_parts: List[str] = []
    tool_calls: List[Dict] = []
    expression_hint = "[neutral]"
    errors: List[str] = []

    for event in core.process_chat_request(user_text, context, system_prompt):
        et = event["type"]
        if et == "text":
            text_parts.append(event["content"])
        elif et == "tool_start":
            tool_calls.append({
                "name": event["tool_name"],
                "args": event.get("args"),
                "result": None,
            })
        elif et == "tool_finish":
            if (
                tool_calls
                and tool_calls[-1]["name"] == event["tool_name"]
                and tool_calls[-1]["result"] is None
            ):
                tool_calls[-1]["result"] = event.get("result")
            else:
                tool_calls.append({
                    "name": event["tool_name"],
                    "result": event.get("result"),
                })
        elif et == "expression":
            expression_hint = event["hint"]
        elif et == "error":
            errors.append(event["content"])

    return {
        "assistant_text": "".join(text_parts),
        "tool_calls": tool_calls,
        "expression_hint": expression_hint,
        "error": "; ".join(errors) if errors else None,
        "request_id": str(uuid.uuid4()),
    }