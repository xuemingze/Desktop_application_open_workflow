"""
desktop_auto_router.py — 双脑路由 (Dynamic Dual-Brain)

给 Open-LLM-VTuber 注入"关键词拦截"路由:
- 🧠 右脑: VTuber 默认 LLM (情感/闲聊/表情)
- 🦾 左脑: 本地桌面基座 (AssistantBridge @ 127.0.0.1:16299)

触发条件 (满足任一即路由到本地基座):
1. 显式触发: @助手 / /cmd 前缀
2. 关键词命中: 打开/关闭/查找/搜索/运行/执行/启动/新建/跑一下/触发
   + 名词: 文件/桌面/路径/工作流/命令/系统/内存/日记/复盘/提醒/画像/记忆/剪贴板

不需要修改 conf.yaml。导入即生效。
"""

import asyncio
import json
import logging
import os
import re
from typing import AsyncIterator, Union, Dict, Any

from .agent.agents.agent_interface import AgentInterface

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 关键词 (用户拍板)
# ---------------------------------------------------------------------------
LOCAL_OPS_KEYWORDS = [
    # 基础动作
    "打开", "关闭", "查找", "搜索", "运行", "执行", "启动",
    "新建", "跑一下", "触发",
    # 资产名词
    "文件", "文件夹", "桌面", "路径", "目录", "窗口", "应用", "程序",
    "软件", "工作流", "命令", "cmd", "powershell",
    "系统", "内存", "cpu", "磁盘",
    "日记", "复盘", "提醒", "闹钟", "画像", "记忆", "剪贴板",
]

# 显式触发前缀
EXPLICIT_PREFIXES = ("@助手", "/cmd", "助手 ", "系统 ")


def should_route_to_desktop(user_text: str) -> bool:
    """判断用户输入是否需要转交本地桌面基座。"""
    if not user_text:
        return False
    text = user_text.lower().strip()
    if any(text.startswith(p.lower()) for p in EXPLICIT_PREFIXES):
        return True
    return any(kw in text for kw in LOCAL_OPS_KEYWORDS)


# ---------------------------------------------------------------------------
# Bridge 调用 (流式)
# ---------------------------------------------------------------------------
BRIDGE_URL = os.environ.get("DESKTOP_BRIDGE_URL", "http://127.0.0.1:16299/v1")
BRIDGE_MODEL = "desktop-auto-v1"

EXPRESSION_PATTERN = re.compile(
    r"\[(neutral|anger|disgust|fear|joy|smirk|sadness|surprise|thinking)\]"
)


async def call_bridge_stream(
    user_text: str,
    chat_history: list = None,
) -> AsyncIterator[str]:
    """
    调用本地 Bridge 流式返回文本。
    表情标签 [xxx] 已经在 Bridge 端注入到文本里(由 VTuber 解析触发 Live2D)。
    """
    import httpx

    # 剥离显式前缀
    clean_text = user_text
    for prefix in EXPLICIT_PREFIXES:
        if clean_text.lower().startswith(prefix.lower()):
            clean_text = clean_text[len(prefix):].strip()
            break

    messages = []
    if chat_history:
        # 只带最近 3 轮,避免太长
        messages.extend(chat_history[-3:])
    messages.append({"role": "user", "content": clean_text})

    payload = {
        "model": BRIDGE_MODEL,
        "messages": messages,
        "stream": True,
    }

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                BRIDGE_URL.rstrip("/") + "/chat/completions",
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = (chunk.get("choices") or [{}])[0].get("delta") or {}
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue
    except httpx.ConnectError:
        logger.warning(f"[Router] Bridge 不可达 ({BRIDGE_URL}), 回退到 VTuber 默认 LLM")
        return
    except Exception as e:
        logger.error(f"[Router] Bridge 调用失败: {e}")
        return


# ---------------------------------------------------------------------------
# Router Agent (wrapper)
# ---------------------------------------------------------------------------
def wrap_agent_with_router(agent, bridge_url: str = None):
    """
    把任意 AgentInterface 包装成 Router Agent。
    命中关键词时走本地 Bridge, 否则走原 agent。
    """
    if bridge_url:
        global BRIDGE_URL
        BRIDGE_URL = bridge_url

    if not isinstance(agent, AgentInterface):
        raise TypeError(f"agent must be AgentInterface, got {type(agent)}")

    router = _RouterAgent(agent)
    logger.info(f"[Router] 已包装 agent ({type(agent).__name__}) → bridge={BRIDGE_URL}")
    return router


class _RouterAgent(AgentInterface):
    """包装原 agent, 在 chat 入口做关键词路由"""

    def __init__(self, original):
        super().__init__()
        self._original = original

    async def chat(self, input_data) -> AsyncIterator:
        # 提取 user_text (兼容 BatchInput / str)
        user_text = getattr(input_data, "text", None) or str(input_data)

        if not should_route_to_desktop(user_text):
            # 右脑: 原 agent 闲聊/情感
            async for out in self._original.chat(input_data):
                yield out
            return

        # 左脑: 转交 Bridge
        logger.info(f"[Router] ⚡ 命中本地操作 → Bridge: {user_text[:80]}")

        # 把 Bridge 流式文本包成 SentenceOutput (BaseOutput 子类)
        from .agent.output_types import SentenceOutput, DisplayText

        accumulated_text = ""
        async for chunk in call_bridge_stream(user_text):
            accumulated_text += chunk
            # 按句号/感叹/问号切句, 模拟 VTuber 的 sentence_divider
            yield SentenceOutput(
                text=accumulated_text,  # 整段累计, 让 TTS 拿到完整一句
                display_text=DisplayText(
                    text=accumulated_text,
                    expression_list=[],  # Bridge 已经把 [xxx] 注入文本, 由 VTuber transformers 处理
                ),
            )

    def handle_interrupt(self, heard_response: str) -> None:
        if hasattr(self._original, "handle_interrupt"):
            self._original.handle_interrupt(heard_response)

    def set_memory_from_history(self, conf_uid: str, history_uid: str) -> None:
        if hasattr(self._original, "set_memory_from_history"):
            self._original.set_memory_from_history(conf_uid, history_uid)


# ---------------------------------------------------------------------------
# 自动注入 (供 run_server.py 调用)
# ---------------------------------------------------------------------------
def inject_router(service_context, bridge_url: str = None):
    """
    把 service_context.agent_engine 包装成 RouterAgent。
    在 service_context.init_agent() 之后调用。
    """
    if service_context.agent_engine is None:
        logger.warning("[Router] agent_engine is None, skipping injection")
        return

    if isinstance(service_context.agent_engine, _RouterAgent):
        logger.debug("[Router] already wrapped, skipping")
        return

    service_context.agent_engine = wrap_agent_with_router(
        service_context.agent_engine,
        bridge_url=bridge_url,
    )


# ---------------------------------------------------------------------------
# 独立测试 (不需要 VTuber)
# ---------------------------------------------------------------------------
async def _test():
    """模拟 VTuber: 命中关键词走 Bridge, 其他走占位"""
    print("=== 测试 1: 命中关键词 ===")
    if should_route_to_desktop("帮我打开桌面文件"):
        print("  → 路由到 Bridge")
        async for chunk in call_bridge_stream("帮我打开桌面文件"):
            print(f"  chunk: {chunk!r}")
    else:
        print("  → 走默认 LLM")

    print("\n=== 测试 2: 闲聊 ===")
    if should_route_to_desktop("你今天心情怎么样?"):
        print("  → 路由到 Bridge")
    else:
        print("  → 走默认 LLM (闲聊)")

    print("\n=== 测试 3: 显式触发 ===")
    if should_route_to_desktop("@助手 帮我搜索桌面上的txt文件"):
        print("  → 路由到 Bridge")
    else:
        print("  → 走默认 LLM")


if __name__ == "__main__":
    asyncio.run(_test())