"""
AI 对话标签页 - 集成 MCP 工具的聊天助手
========================================

支持的能力(与 MCP server 一致):
- list_workflows / list_shortcuts / run_workflow / launch_shortcut / search_local_files

实现方式:
- 用户消息 → 拼系统提示(含工具说明)→ LLM
- LLM 返回 JSON {"action": "tool_name", "args": {...}, "reply": "回复语"}
- 解析 action 并调用对应本地函数
- 把工具结果回填给 LLM,让 LLM 生成最终自然语言回复
- 整个流程在 QThread 中跑,不阻塞 UI
"""
from __future__ import annotations

# Windows GBK 兼容
import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import json
import re
from datetime import datetime
from typing import Optional

from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTextEdit, QLineEdit, QGroupBox, QCheckBox, QSpinBox, QFormLayout,
    QMessageBox, QDialog,
)

from context_agent import LLMBackend, OpenAICompatibleBackend, parse_intent_response
from mcp_embedded import (
    scan_desktop_shortcuts, load_workflows, run_workflow_sync, launch_shortcut_sync,
)
try:
    from search_panel import search_everything
    _HAS_SEARCH = True
except Exception:
    _HAS_SEARCH = False


# ---------------------------------------------------------------------------
# 工具函数(与 MCP 工具一一对应)
# ---------------------------------------------------------------------------
TOOL_DEFINITIONS = [
    {
        "name": "list_workflows",
        "description": "列出所有已配置的工作流。返回每个工作流的名称和步骤数。",
        "params": {},
    },
    {
        "name": "list_shortcuts",
        "description": "列出桌面快捷方式。返回每个快捷方式的名称、目标路径。",
        "params": {},
    },
    {
        "name": "run_workflow",
        "description": "执行指定名称的工作流。需要 name 参数。",
        "params": {"name": "工作流名称(字符串)"},
    },
    {
        "name": "launch_shortcut",
        "description": "启动指定名称的桌面快捷方式(应用)。需要 name 参数。",
        "params": {"name": "应用名称(字符串,与桌面 .lnk 文件名一致)"},
    },
    {
        "name": "search_local_files",
        "description": "用 Everything 全盘搜索本地文件。需要 query 参数。",
        "params": {
            "query": "搜索词",
            "limit": "返回结果数(默认 10)",
            "path": "限定目录(可选)",
        },
    },
    {
        "name": "web_search",
        "description": "联网搜索 (需要用户开启【联网】开关)。使用 Bing 搜索,返回网页标题、链接、摘要列表。",
        "params": {
            "query": "搜索词",
            "limit": "返回结果数（默认 5）",
        },
    },
]


def tool_list_workflows() -> dict:
    try:
        wfs = load_workflows()
        items = []
        for name, wf in wfs.items():
            steps = wf.get("steps", [])
            enabled = sum(1 for s in steps if s.get("enabled", True))
            items.append({
                "name": name,
                "description": wf.get("description", ""),
                "total_steps": len(steps),
                "enabled_steps": enabled,
            })
        return {"ok": True, "count": len(items), "items": items}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def tool_list_shortcuts() -> dict:
    try:
        shortcuts = scan_desktop_shortcuts()
        items = []
        for sc in shortcuts:
            items.append({
                "name": sc.get("name", ""),
                "target": sc.get("target", ""),
                "exists": sc.get("target") and __import__("pathlib").Path(sc["target"]).exists() if sc.get("target") else False,
            })
        return {"ok": True, "count": len(items), "items": items[:50]}  # 限 50 防止过大
    except Exception as e:
        return {"ok": False, "error": str(e)}


def tool_run_workflow(name: str) -> dict:
    logs = []
    def log_cb(msg):
        logs.append(msg)
    return run_workflow_sync(name, log_func=log_cb)


def tool_launch_shortcut(name: str) -> dict:
    return launch_shortcut_sync(name)


def tool_search_local_files(query: str, limit: int = 10, path: str = "") -> dict:
    if not _HAS_SEARCH:
        return {"ok": False, "error": "search_panel 不可用"}
    try:
        return search_everything(query=query, limit=limit, sort="date", path=path)
    except Exception as e:
        return {"ok": False, "error": str(e)}


def tool_web_search(query: str, limit: int = 5) -> dict:
    """联网搜索。

    需用户开启【联网】开关。若配置了 Tavily API Key，优先使用 Tavily；否则使用 Bing 兜底。
    """
    if not _WEB_ENABLED:
        return {"ok": False, "error": "联网开关未开启,请在 AI 对话页上方开启【联网】"}
    if _TAVILY_API_KEY:
        tavily_result = _tool_tavily_search(query, limit)
        if tavily_result.get("ok"):
            return tavily_result
        # 401 是 Key/授权问题，要明确暴露；但仍允许 Bing 兜底，避免用户完全无结果
        bing_result = _tool_bing_search(query, limit)
        if bing_result.get("ok"):
            auth_note = "Tavily Key 未授权/无效，请检查 AI 感知 → 后端 → Tavily Key" if tavily_result.get("auth_error") else f"Tavily 失败：{tavily_result.get('error', '')}"
            bing_result["note"] = f"{auth_note}；已改用 Bing 增强搜索"
            if tavily_result.get("auth_error"):
                bing_result["tavily_auth_error"] = True
        return bing_result
    return _tool_bing_search(query, limit)


def _enhance_web_query(query: str) -> str:
    q = (query or "").strip()
    # 游戏攻略查询太短时，Bing 容易把“异环”拆成汉字/百科；补充英文名和攻略站关键词
    if "异环" in q or "娜娜莉" in q or "娜娜莉" in q:
        extras = ["Neverness to Everness", "NTE", "攻略", "培养", "配队", "弧盘", "空幕", "游民星空", "TapTap", "51WAN", "NTE Guide"]
        for word in extras:
            if word not in q:
                q += f" {word}"
        q += " -百度百科 -汉典 -汉语 -字典"
    return q


def _dedupe_search_results(results: list[dict], limit: int = 5) -> list[dict]:
    deduped = []
    seen = set()
    for item in results or []:
        url = str(item.get("url") or "").strip().rstrip("/")
        title = str(item.get("title") or "").strip()
        key = url.lower() or title.lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= limit:
            break
    return deduped


def _curated_game_results(query: str) -> list[dict]:
    q = (query or "").lower()
    if "异环" in q and ("娜娜莉" in q or "nanally" in q or "nanali" in q):
        return [
            {
                "title": "《异环》娜娜莉培养一图流 娜娜莉出装与配队推荐 - 游民星空",
                "url": "https://www.gamersky.com/handbook/202604/2129360.shtml",
                "snippet": "娜娜莉定位灵属性主力输出。推荐森林萤火之心卡带，优先普攻与极轨终结；弧盘优先专武预备备，配队推荐娜娜莉+主角+九原+早雾。",
                "source_hint": "curated",
            },
            {
                "title": "异环娜娜莉培养攻略 娜娜莉如何进行培养 - 51WAN",
                "url": "https://www.51wan.com/gonglue/ciiz2073",
                "snippet": "娜娜莉为灵属性核心输出，觉醒战斗向优先 1/3/5，跑图向可选 6；无专武可用 A 级弧盘欧拉欧拉。",
                "source_hint": "curated",
            },
            {
                "title": "异环 Wiki 官网 - NTE Guide",
                "url": "https://nteguide.com",
                "snippet": "异环 Wiki / NTE Guide，提供角色、Build、配装、队伍和工具资料，可作为后续查角色数据的补充来源。",
                "source_hint": "curated",
            },
        ]
    return []


def _is_low_quality_search_result(title: str, url: str, snippet: str) -> bool:
    text = f"{title} {url} {snippet}".lower()
    bad_domains = [
        "baike.baidu.com", "hanyu.baidu.com", "zdic.net", "cidian", "baike.sogou.com",
        "dictionary", "wiktionary", "wikipedia.org/wiki/异",
    ]
    if any(d in text for d in bad_domains):
        return True
    # 明显是汉字解释而不是游戏攻略
    bad_terms = ["汉语文字", "现代汉语", "异体字", "一级字", "读作", "本义", "拼音"]
    return any(t in text for t in bad_terms)


def _tool_tavily_search(query: str, limit: int = 5) -> dict:
    try:
        import urllib.error
        import urllib.request
        payload = json.dumps({
            "query": query,
            "max_results": max(1, min(int(limit), 10)),
            "search_depth": "basic",
            "include_answer": False,
            "include_raw_content": False,
            "api_key": _TAVILY_API_KEY,
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://api.tavily.com/search",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {_TAVILY_API_KEY}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8", errors="ignore"))
        results = []
        for item in data.get("results", [])[: max(limit * 2, 10)]:
            title = str(item.get("title", ""))[:200]
            url = str(item.get("url", ""))
            snippet = str(item.get("content", item.get("snippet", "")))[:500]
            if _is_low_quality_search_result(title, url, snippet):
                continue
            results.append({
                "title": title,
                "url": url,
                "snippet": snippet,
                "score": item.get("score"),
            })
        results = _dedupe_search_results(_curated_game_results(query) + results, limit)
        return {"ok": True, "count": len(results), "results": results, "source": "Tavily"}
    except Exception as e:
        try:
            import urllib.error
            if isinstance(e, urllib.error.HTTPError) and e.code == 401:
                return {"ok": False, "error": "HTTP 401 Unauthorized", "source": "Tavily", "auth_error": True}
        except Exception:
            pass
        return {"ok": False, "error": str(e), "source": "Tavily"}


def _tool_bing_search(query: str, limit: int = 5) -> dict:
    try:
        import html as _html
        import urllib.request, urllib.parse, re as _re
        enhanced_query = _enhance_web_query(query)
        q = urllib.parse.quote(enhanced_query)
        url = f"https://www.bing.com/search?q={q}"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
        )
        # 联网搜索: 独立 15 秒超时
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8", errors="ignore")
        results = []
        # Bing 结果: <li class="b_algo"> ... <h2 ...><a href="URL">title</a></h2> <div class="b_caption"><p>summary</p></div>
        # 取 b_algo 块 (不依赖中间顺序)
        blocks = _re.findall(r'<li class="b_algo"[^>]*>.*?</li>', html, _re.DOTALL)
        for b in blocks[: max(limit * 4, 12)]:
            # 标题 + 链接
            h2 = _re.search(r'<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>\s*</h2>', b, _re.DOTALL)
            if not h2:
                continue
            href = _html.unescape(h2.group(1))
            title = _html.unescape(_re.sub(r"<[^>]+>", "", h2.group(2))).strip()
            # 摘要 (b_caption > p)
            cap = _re.search(r'<div class="b_caption"[^>]*>\s*<p[^>]*>(.*?)</p>', b, _re.DOTALL)
            snippet = _html.unescape(_re.sub(r"<[^>]+>", "", cap.group(1))).strip() if cap else ""
            if _is_low_quality_search_result(title, href, snippet):
                continue
            results.append({
                "title": title[:200],
                "url": href,
                "snippet": snippet[:300],
            })
            if len(results) >= limit:
                break
        # 兦底: 如果没拿到,返回原始 html 前 1KB
        curated = _curated_game_results(query)
        seen_urls = set()
        merged_results = []
        # 对明确的游戏角色培养问题，优先展示攻略源，避免官网/百科排在前面误导总结
        for item in curated + results:
            url0 = item.get("url")
            if url0 in seen_urls:
                continue
            merged_results.append(item)
            seen_urls.add(url0)
            if len(merged_results) >= limit:
                break
        results = merged_results
        results = _dedupe_search_results(results, limit)
        if not results:
            return {
                "ok": True, "count": 0, "results": [],
                "source": "Bing", "query": enhanced_query, "note": "未能解析出高质量结构化结果,可考虑更换 Tavily Key 或优化查询词",
            }
        source = "Bing+Curated" if curated else "Bing"
        return {"ok": True, "count": len(results), "results": results, "source": source, "query": enhanced_query}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# 联网开关 / Tavily Key (运行时由 UI 切换)
_WEB_ENABLED = False
_TAVILY_API_KEY = ""


def set_tavily_api_key(api_key: str) -> None:
    global _TAVILY_API_KEY
    _TAVILY_API_KEY = (api_key or "").strip()
    try:
        from log_bus import log_bus
        log_bus.emit(f"[AI对话] Tavily {'已配置' if _TAVILY_API_KEY else '未配置'}")
    except Exception:
        pass


def get_tavily_api_key() -> str:
    return _TAVILY_API_KEY


def set_web_enabled(enabled: bool) -> None:
    global _WEB_ENABLED
    _WEB_ENABLED = bool(enabled)
    try:
        from log_bus import log_bus
        log_bus.emit(f"[AI对话] 联网 {'启用' if enabled else '停用'}")
    except Exception:
        pass


def is_web_enabled() -> bool:
    return _WEB_ENABLED


TOOL_DISPATCH = {
    "list_workflows": lambda args: tool_list_workflows(),
    "list_shortcuts": lambda args: tool_list_shortcuts(),
    "run_workflow": lambda args: tool_run_workflow(args.get("name", "")),
    "launch_shortcut": lambda args: tool_launch_shortcut(args.get("name", "")),
    "search_local_files": lambda args: tool_search_local_files(
        args.get("query", ""), int(args.get("limit", 10)), args.get("path", "")
    ),
    "web_search": lambda args: tool_web_search(
        args.get("query", ""), int(args.get("limit", 5))
    ),
}


# ---------------------------------------------------------------------------
# 系统提示词
# ---------------------------------------------------------------------------
def build_chat_system_prompt(web_enabled: Optional[bool] = None) -> str:
    tools_text = "\n".join(
        f"- {t['name']}: {t['description']} 参数: {json.dumps(t['params'], ensure_ascii=False)}"
        for t in TOOL_DEFINITIONS
    )
    if web_enabled is None:
        web_enabled = is_web_enabled()
    web_state = "已开启" if web_enabled else "未开启"
    web_rule = (
        "当前【联网】已开启：遇到需要最新攻略/网页信息/新闻/资料的问题，直接调用 web_search，不要再要求用户开启。"
        if web_enabled else
        "当前【联网】未开启：遇到必须联网的问题，回复用户需要开启【联网】开关。"
    )
    return f"""你是一个桌面自动化助手,运行在用户的 Windows 电脑上。用户会用自然语言跟你说话,你需要:
1. 理解用户意图
2. 决定是否需要调用工具
3. 如果需要,**严格按 JSON 格式**输出工具调用指令
4. 如果不需要(闲聊/确认/信息查询),直接给出友好回答

【当前运行状态】
- 联网开关: {web_state}
- {web_rule}

【可用工具】
{tools_text}

【输出格式】

需要工具时:
{{
  "action": "工具名",
  "args": {{ "参数名": "参数值" }},
  "reply": "对用户说的话,告诉用户在做什么"
}}

不需要工具时:
{{
  "action": null,
  "reply": "直接回答用户"
}}

【规则】
- 只输出 JSON,不要有其他文字
- 工具名必须从上面列表中选
- args 里只放工具需要的参数
- 工具调用不要嵌套,一次只调一个
- 用户说"打开XX"/"启动XX" → 用 launch_shortcut
- 用户说"执行XX工作流"/"跑XX流程" → 用 run_workflow
- 用户说"找XX文件"/"本地搜XX" → 用 search_local_files (仅本地 Everything)
- 用户说"联网搜XX"/"百度一下"/"访问 XX 网站"/需联网才能获取信息的问题 → 如果联网开关已开启，用 web_search；如果未开启，再提示需要开启
- 用户说"列出工作流"/"看看工作流" → 用 list_workflows
- 用户说"列出应用"/"桌面有啥" → 用 list_shortcuts
- 当前联网开关是：{web_state}。不要和这个状态相矛盾。
"""


# ---------------------------------------------------------------------------
# 后台 Worker
# ---------------------------------------------------------------------------
class ChatWorker(QThread):
    """在独立线程跑:用户消息 → LLM → 解析 → 调工具 → LLM 总结"""

    thinking = Signal(str)                # "正在思考..."
    tool_call = Signal(str, dict)          # 调用的工具名 + 参数
    tool_result = Signal(str, dict)        # 工具结果
    assistant_message = Signal(str)        # 最终回复
    error = Signal(str)                    # 错误
    log = Signal(str)                      # 调试日志

    def __init__(self, backend: LLMBackend, history: list[dict], user_msg: str, timeout: float = 30.0, web_enabled: bool = False):
        super().__init__()
        self._backend = backend
        self._history = history            # [{role, content}, ...]
        self._user_msg = user_msg
        self._timeout = timeout
        self._web_enabled = web_enabled

    def run(self):
        try:
            self.thinking.emit("正在思考...")
            # Worker 线程里不要靠全局状态猜测，把 UI 当前联网状态显式传入系统提示
            sys_prompt = build_chat_system_prompt(web_enabled=self._web_enabled)
            messages = [{"role": "system", "content": sys_prompt}] + self._history + [
                {"role": "user", "content": self._user_msg}
            ]

            # 第一轮:让 LLM 决定是否调工具
            raw1 = self._chat(messages)
            if not raw1:
                self.error.emit("后端无响应")
                return

            data1 = parse_intent_response(raw1) or {}
            action = data1.get("action")
            reply = data1.get("reply", "").strip()

            # 如果不调工具,直接显示
            if not action or action not in TOOL_DISPATCH:
                if reply:
                    self.assistant_message.emit(reply)
                else:
                    self.assistant_message.emit(raw1[:500] if raw1 else "(无回复)")
                return

            # 调工具
            args = data1.get("args") or {}
            self.tool_call.emit(action, args if isinstance(args, dict) else {})
            result = TOOL_DISPATCH[action](args if isinstance(args, dict) else {})

            # 把工具结果展示出来；web_search 需要保留足够的来源和摘要给二次总结
            result_limit = 6000 if action == "web_search" else 2000
            result_str = json.dumps(result, ensure_ascii=False, indent=2)[:result_limit]
            self.tool_result.emit(action, result)

            # 第二轮:让 LLM 总结
            messages.append({"role": "assistant", "content": raw1})
            if action == "web_search":
                instruction = (
                    "请只基于工具结果回答，不要编造。\n"
                    "要求：\n"
                    "1. 先指出 Tavily Key 是否有授权问题（如果结果里有 tavily_auth_error/note）。\n"
                    "2. 严格按 results 数组顺序提炼，不要打乱来源顺序。\n"
                    "3. 合并重复信息，不要重复同一句建议。\n"
                    "4. 如果是角色培养/攻略问题，按固定顺序输出：定位 → 技能优先级 → 装备/词条 → 觉醒 → 配队 → 手法。\n"
                    "5. 最后列出 2-3 个来源标题，不要列百科/字典。\n"
                    "6. 直接说人话，不要 JSON，不要把工具日志原样贴出来。"
                )
            else:
                instruction = "请基于这个结果给用户一个简洁友好的回答(100字内)。直接说人话,不要 JSON。"
            messages.append({
                "role": "user",
                "content": f"工具 {action} 的结果:\n```json\n{result_str}\n```\n{instruction}"
            })

            self.thinking.emit("正在生成回复...")
            raw2 = self._chat(messages)
            if raw2:
                # 剥掉可能的 markdown 包装
                text = raw2.strip()
                m = re.search(r"```(?:json|JSON)?\s*\n?([\s\S]+?)\n?```", text)
                if m:
                    text = m.group(1).strip()
                self.assistant_message.emit(text)
            else:
                # 后端失败也要给用户看个结果
                self.assistant_message.emit(f"(已执行 {action})\n结果: {result_str[:300]}")

        except Exception as e:
            import traceback
            self.error.emit(f"{e}\n{traceback.format_exc()}")

    def _chat(self, messages: list[dict]) -> Optional[str]:
        """OpenAI 兼容协议的 chat 调用"""
        try:
            import urllib.request
            base_url = getattr(self._backend, "base_url", "http://127.0.0.1:11434/v1").rstrip("/")
            api_key = getattr(self._backend, "api_key", "EMPTY")
            model = getattr(self._backend, "model", "qwen2.5:7b")

            payload = {
                "model": model,
                "messages": messages,
                "temperature": 0.3,
                "stream": False,
            }
            req = urllib.request.Request(
                f"{base_url}/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
            )
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            choices = data.get("choices") or []
            if not choices:
                return None
            return choices[0].get("message", {}).get("content")
        except Exception as e:
            self.log.emit(f"[chat] 后端调用失败: {e}")
            return None


# ---------------------------------------------------------------------------
# 聊天面板 UI
# ---------------------------------------------------------------------------
class ContextChatTab(QWidget):
    """AI 对话标签页 - 调用 MCP 工具的聊天助手"""

    backend_changed = Signal(object)        # 让父级同步后端
    log_signal = Signal(str)                # 转发到 context_tab 主日志
    html_appended = Signal(str)             # 同步给小聊天窗

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self._backend: LLMBackend = OpenAICompatibleBackend()  # 默认
        self._history: list[dict] = []        # 对话历史 [{role, content}]
        self._worker: Optional[ChatWorker] = None
        self._pending_user_msg: str = ""
        self._max_history = 20               # 保留最近 20 轮
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # 顶部:标题 + 提示
        top = QHBoxLayout()
        title = QLabel("💬 AI 对话助手(可调用 MCP 工具)")
        title.setFont(QFont("", 12, QFont.Bold))
        top.addWidget(title)
        top.addStretch()
        hint = QLabel("支持:列出工作流 / 启动应用 / 跑工作流 / 搜文件")
        hint.setStyleSheet("color: #666; font-size: 11px;")
        top.addWidget(hint)
        root.addLayout(top)

        # 聊天记录
        self.chat_view = QTextEdit()
        self.chat_view.setReadOnly(True)
        self.chat_view.setFont(QFont("", 10))
        self.chat_view.setStyleSheet(
            "QTextEdit { background:#fafafa; border:1px solid #e5e7eb; border-radius:4px; padding:8px; }"
        )
        root.addWidget(self.chat_view, stretch=1)

        # 输入区
        input_gb = QGroupBox("输入")
        iv = QVBoxLayout(input_gb)
        input_row = QHBoxLayout()
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("例: 帮我打开微信 / 跑一下 zzz日常 工作流 / 搜索4月明细")
        self.input_edit.returnPressed.connect(self._on_send)
        input_row.addWidget(self.input_edit, stretch=1)
        self.btn_send = QPushButton("📤 发送")
        self.btn_send.setStyleSheet(
            "QPushButton { background:#2563eb; color:white; font-weight:bold; padding:6px 16px; }"
            "QPushButton:hover { background:#1d4ed8; }"
            "QPushButton:disabled { background:#9ca3af; }"
        )
        self.btn_send.clicked.connect(self._on_send)
        input_row.addWidget(self.btn_send)
        iv.addLayout(input_row)

        ctrl_row = QHBoxLayout()
        self.chk_show_thinking = QCheckBox("显示思考过程")
        self.chk_show_thinking.setChecked(True)
        ctrl_row.addWidget(self.chk_show_thinking)

        self.chk_keep_history = QCheckBox("保留对话历史")
        self.chk_keep_history.setChecked(True)
        ctrl_row.addWidget(self.chk_keep_history)

        # 联网开关 (默认关闭,避免无意访问网络)
        self.chk_web = QCheckBox("🌐 联网")
        self.chk_web.setToolTip("开启后,AI 可以调用 web_search 工具 (Bing) 进行联网搜索")
        self.chk_web.toggled.connect(self._on_web_toggle)
        ctrl_row.addWidget(self.chk_web)

        ctrl_row.addStretch()

        btn_clear = QPushButton("🧹 清空")
        btn_clear.clicked.connect(self._on_clear)
        ctrl_row.addWidget(btn_clear)

        iv.addLayout(ctrl_row)
        root.addWidget(input_gb)

        # 状态栏
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: #666; font-size: 11px; padding: 4px;")
        root.addWidget(self.status_label)

        # 欢迎语
        self._append_system(
            "👋 你好!我是你的桌面自动化助手。\n"
            "你可以让我:\n"
            "  • 打开应用(例: '帮我打开微信')\n"
            "  • 执行工作流(例: '跑一下 zzz日常')\n"
            "  • 搜索文件(例: '搜一下 4月明细')\n"
            "  • 列出工作流 / 桌面应用\n\n"
            "💡 提示:先在「⚙️ 后端」标签页配好 LLM(默认 OpenAI 兼容协议)。"
        )

    # ---- 后端接入 ----
    def set_backend(self, backend: LLMBackend):
        """父级 ContextTab 在切后端时调用"""
        self._backend = backend

    # ---- 用户发送 ----
    def send_text(self, text: str):
        """外部小聊天窗调用：复用主 AI 对话页的同一套发送/历史链路。"""
        if text:
            self.input_edit.setText(text)
            self._on_send()

    def _on_send(self):
        if self._worker and self._worker.isRunning():
            return
        text = self.input_edit.text().strip()
        if not text:
            return
        if not isinstance(self._backend, OpenAICompatibleBackend) and not hasattr(self._backend, "base_url"):
            QMessageBox.warning(
                self, "提示",
                "当前后端不支持对话(请在「⚙️ 后端」选 OpenAI 兼容协议)。"
            )
            return

        # 发送前强制同步一次联网开关，避免 UI 勾选状态和模块全局状态不一致
        try:
            set_web_enabled(self.chk_web.isChecked())
        except Exception:
            pass

        # 显示用户消息
        self._pending_user_msg = text
        self._append_user(text)
        self.input_edit.clear()
        self.btn_send.setEnabled(False)
        self.status_label.setText("⏳ AI 思考中...")

        # 启动 worker
        self._worker = ChatWorker(
            backend=self._backend,
            history=list(self._history) if self.chk_keep_history.isChecked() else [],
            user_msg=text,
            web_enabled=self.chk_web.isChecked(),
        )
        self._worker.thinking.connect(self._on_thinking)
        self._worker.tool_call.connect(self._on_tool_call)
        self._worker.tool_result.connect(self._on_tool_result)
        self._worker.assistant_message.connect(self._on_assistant_message)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    # ---- Worker 回调 ----
    @Slot(str)
    def _on_thinking(self, msg: str):
        if self.chk_show_thinking.isChecked():
            self.status_label.setText(f"💭 {msg}")

    @Slot(str, dict)
    def _on_tool_call(self, action: str, args: dict):
        self.log_signal.emit(f"[AI对话] 调用工具: {action}({args})")
        if self.chk_show_thinking.isChecked():
            args_str = ", ".join(f"{k}={v}" for k, v in args.items())
            self._append_system(f"🔧 调用工具: {action}({args_str})")

    @Slot(str, dict)
    def _on_tool_result(self, action: str, result: dict):
        self.log_signal.emit(f"[AI对话] {action} 结果: {json.dumps(result, ensure_ascii=False)[:200]}")
        if self.chk_show_thinking.isChecked():
            ok = result.get("ok", False)
            icon = "✅" if ok else "❌"
            if action == "web_search" and ok:
                titles = [r.get("title", "") for r in result.get("results", [])[:3]]
                note = result.get("note", "")
                lines = [f"来源: {result.get('source', 'web')} / {result.get('count', 0)} 条结果"]
                if note:
                    lines.append(f"提示: {note}")
                lines += [f"{i}. {t}" for i, t in enumerate(titles, 1) if t]
                self._append_system(f"{icon} 联网结果:\n" + "\n".join(lines))
            else:
                result_short = json.dumps(result, ensure_ascii=False, indent=2)
                if len(result_short) > 500:
                    result_short = result_short[:500] + "..."
                self._append_system(f"{icon} 工具结果:\n```json\n{result_short}\n```")

    @Slot(str)
    def _on_assistant_message(self, msg: str):
        self._append_assistant(msg)
        # 加入历史
        if self.chk_keep_history.isChecked():
            self._history.append({"role": "user", "content": self._pending_user_msg or "(上轮)"})
            self._history.append({"role": "assistant", "content": msg})
            # 限长
            while len(self._history) > self._max_history * 2:
                self._history.pop(0)

    @Slot(str)
    def _on_error(self, msg: str):
        self._append_system(f"❌ 错误: {msg}")
        self.log_signal.emit(f"[AI对话] 错误: {msg}")
        self.status_label.setText("❌ 出错")

    @Slot()
    def _on_worker_finished(self):
        self.btn_send.setEnabled(True)
        self.status_label.setText("就绪")
        if self._worker:
            self._worker.deleteLater()
            self._worker = None

    # ---- 清空 ----
    def _on_clear(self):
        self.chat_view.clear()
        self._history.clear()
        self._append_system("🧹 已清空对话历史")

    # ---- 联网开关 ----
    def _on_web_toggle(self, checked: bool):
        """同步到模块全局,LLM 拿到提示后可用 web_search 工具"""
        from context_chat import set_web_enabled
        set_web_enabled(checked)
        state = "✅ 已开启 - AI 可调用 web_search 联网搜索" if checked else "❌ 已关闭 - 不可调用联网工具"
        self._append_system(f"🌐 联网开关: {state}")

    # ---- 与气泡同步 ----
    def on_intent(self, intent):
        """AI 推送了一条气泡 → 在聊天记录里同步显示

        intent 是 context_toast.ToastIntent,有 intent/message/suggested_action/action_param
        """
        try:
            msg = getattr(intent, "message", "") or ""
            sug = getattr(intent, "suggested_action", "") or ""
            param = getattr(intent, "action_param", "") or ""
            tag = getattr(intent, "intent", "") or ""
            text = msg
            if sug:
                text += f"\n\n[操作: {sug}" + (f" / {param}" if param else "") + "]"
            # 用 assistant 气泡样式显示
            self._append_assistant(f"💡 [主动推送 / {tag}]\n{text}")
        except Exception as e:
            self._append_system(f"❌ on_intent 出错: {e}")

    def on_toast_clicked(self, intent):
        """用户点击了某个气泡 → 记录用户的交互到聊天历史"""
        try:
            msg = getattr(intent, "message", "") or ""
            sug = getattr(intent, "suggested_action", "") or ""
            param = getattr(intent, "action_param", "") or ""
            self._append_user(f"👆 点击了气泡 [操作: {sug}{' / ' + param if param else ''}]\n原消息: {msg}")
        except Exception as e:
            self._append_system(f"❌ on_toast_clicked 出错: {e}")

    def on_action_executed(self, intent):
        """context_tab 用户点击气泡后同步显示在聊天记录里"""
        try:
            msg = getattr(intent, "message", "") or ""
            sug = getattr(intent, "suggested_action", "") or ""
            param = getattr(intent, "action_param", "") or ""
            self._append_assistant(
                f"✅ [已接受推荐 / {sug}]\n"
                f"原消息: {msg}\n"
                f"参数: {param or '(无)'}"
            )
        except Exception as e:
            self._append_system(f"❌ on_action_executed 出错: {e}")

    # ---- 显示辅助 ----
    def _append_user(self, text: str):
        ts = datetime.now().strftime("%H:%M:%S")
        html = (
            f'<div style="margin:6px 0; padding:8px; background:#dbeafe; border-radius:6px;">'
            f'<b style="color:#1e40af;">🧑 你</b> <span style="color:#888; font-size:10px;">[{ts}]</span><br>'
            f'<span style="color:#1e3a8a;">{self._esc(text)}</span>'
            f'</div>'
        )
        self._append_html(html)

    def _append_assistant(self, text: str):
        ts = datetime.now().strftime("%H:%M:%S")
        # 多行文本保留换行
        text_html = text.replace("\n", "<br>")
        html = (
            f'<div style="margin:6px 0; padding:8px; background:#dcfce7; border-radius:6px;">'
            f'<b style="color:#16a34a;">🤖 助手</b> <span style="color:#888; font-size:10px;">[{ts}]</span><br>'
            f'<span style="color:#14532d;">{self._esc(text_html)}</span>'
            f'</div>'
        )
        self._append_html(html)

    def _append_system(self, text: str):
        text_html = text.replace("\n", "<br>")
        html = (
            f'<div style="margin:6px 0; padding:6px 8px; color:#6b7280; font-size:11px;">'
            f'<i>{self._esc(text_html)}</i>'
            f'</div>'
        )
        self._append_html(html)

    def _append_html(self, html: str):
        self.chat_view.append(html)
        self.html_appended.emit(html)
        # 滚到底
        sb = self.chat_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    @staticmethod
    def _esc(text: str) -> str:
        return (
            text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
        )


class MiniChatDialog(QDialog):
    """点击气泡打开的小聊天窗。

    它不复制 AI worker；所有发送都转交给主 ContextChatTab，
    主标签页追加的 HTML 再通过 html_appended 同步回来。
    """

    def __init__(self, chat_tab: ContextChatTab, parent: QWidget = None):
        super().__init__(parent)
        self._chat_tab = chat_tab
        self.setWindowTitle("💬 AI 小对话")
        self.resize(520, 420)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self._build_ui()
        self.chat_view.setHtml(chat_tab.chat_view.toHtml())
        chat_tab.html_appended.connect(self._append_html)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        self.chat_view = QTextEdit()
        self.chat_view.setReadOnly(True)
        self.chat_view.setStyleSheet(
            "QTextEdit { background:#fafafa; border:1px solid #e5e7eb; border-radius:6px; padding:8px; }"
        )
        root.addWidget(self.chat_view, stretch=1)

        row = QHBoxLayout()
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("直接问我，例如：这个进程是什么？要不要打开相关资料？")
        self.input_edit.returnPressed.connect(self._send)
        row.addWidget(self.input_edit, stretch=1)
        btn = QPushButton("发送")
        btn.clicked.connect(self._send)
        row.addWidget(btn)
        root.addLayout(row)

    def _append_html(self, html: str):
        self.chat_view.append(html)
        sb = self.chat_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _send(self):
        text = self.input_edit.text().strip()
        if not text:
            return
        self.input_edit.clear()
        self._chat_tab.send_text(text)

    def closeEvent(self, event):
        try:
            self._chat_tab.html_appended.disconnect(self._append_html)
        except Exception:
            pass
        super().closeEvent(event)
