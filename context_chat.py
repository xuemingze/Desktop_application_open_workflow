"""
AI 对话标签页 - 集成 MCP 工具的聊天助手
========================================

支持的能力(与 MCP server 一致):
- list_workflows / list_shortcuts / run_workflow / launch_shortcut / search_local_files
- read_file_content / open_system_file (新增文件操作)

实现方式:
- 用户消息 → 拼系统提示(含工具说明)→ LLM
- 支持多轮 Agent Loop (ReAct 模式)：LLM 可连续调用多次工具 (如先搜索，再打开)
- 解析 action 并调用对应本地函数
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
    QMessageBox, QDialog, QSizePolicy,
)

from context_agent import LLMBackend, OpenAICompatibleBackend, parse_intent_response
from context_toast import ToastIntent
from mcp_embedded import (
    scan_desktop_shortcuts, load_workflows, run_workflow_sync, launch_shortcut_sync,
)
from chat_memory import append_chat_log, cleanup_old_logs
from reminders import create_reminder
from user_profile import get_active_profile_summary

try:
    from search_panel import search_everything
    _HAS_SEARCH = True
except Exception:
    _HAS_SEARCH = False

# 引入 Phase B 的文件工具
try:
    from file_tools import read_file_content_sync, open_system_file_sync
except ImportError:
    def read_file_content_sync(*args, **kwargs): return {"ok": False, "error": "file_tools未安装"}
    def open_system_file_sync(*args, **kwargs): return {"ok": False, "error": "file_tools未安装"}

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
        "description": "用 Everything 全盘搜索本地文件或文件夹。需要 query 参数。",
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
    {
        "name": "read_file_content",
        "description": "安全地读取文本文件内容。遇到报错排查、理解日记、查看配置时使用。",
        "params": {
            "path": "文件的绝对路径",
            "max_lines": "最大读取行数，默认 200 行",
            "read_from_tail": "是否从尾部倒序读取，看日志报错必备"
        },
    },
    {
        "name": "open_system_file",
        "description": "调用 Windows 默认程序直接在用户桌面上打开文件/文件夹，或在资源管理器中定位。",
        "params": {
            "path": "文件或文件夹的绝对路径",
            "method": "default (默认应用打开) 或 explorer (在资源管理器中定位)"
        },
    },
    {
        "name": "create_reminder",
        "description": "当用户要求在未来某个时间提醒他做某事时调用。默认只弹 Toast；如需关联工作流，只创建带按钮的提醒，必须用户到期后点击才运行。",
        "params": {
            "trigger_time": "ISO 时间或中文相对时间，如 2026-06-21T15:00:00、半小时后、明天下午3点",
            "content": "提醒内容",
            "action_type": "toast 或 run_workflow，默认 toast",
            "workflow_name": "可选，action_type=run_workflow 时填写工作流名"
        },
    }
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


def tool_create_reminder(trigger_time: str, content: str, action_type: str = "toast", workflow_name: str = "") -> dict:
    try:
        reminder_id = create_reminder(
            trigger_time=trigger_time,
            content=content,
            action_type=action_type or "toast",
            workflow_name=workflow_name or None,
            created_from_chat=True,
        )
        return {"ok": True, "id": reminder_id, "trigger_time": trigger_time, "content": content}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def tool_search_local_files(query: str, limit: int = 10, path: str = "") -> dict:
    if not _HAS_SEARCH:
        return {"ok": False, "error": "search_panel 不可用"}
    try:
        return search_everything(query=query, limit=limit, sort="date", path=path)
    except Exception as e:
        return {"ok": False, "error": str(e)}


def tool_web_search(query: str, limit: int = 5) -> dict:
    if not _WEB_ENABLED:
        return {"ok": False, "error": "联网开关未开启,请在 AI 对话页上方开启【联网】"}
    if _TAVILY_API_KEY:
        tavily_result = _tool_tavily_search(query, limit)
        if tavily_result.get("ok"):
            return tavily_result
        bing_result = _tool_bing_search(query, limit)
        if bing_result.get("ok"):
            auth_note = "Tavily Key 未授权/无效" if tavily_result.get("auth_error") else f"Tavily 失败：{tavily_result.get('error', '')}"
            bing_result["note"] = f"{auth_note}；已改用 Bing 增强搜索"
        return bing_result
    return _tool_bing_search(query, limit)


def _enhance_web_query(query: str) -> str:
    q = (query or "").strip()
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
                "title": "《异环》娜娜莉培养一图流 - 游民星空",
                "url": "https://www.gamersky.com/handbook/202604/2129360.shtml",
                "snippet": "娜娜莉定位灵属性主力输出。推荐森林萤火之心卡带，优先普攻与极轨终结；弧盘优先专武预备备，配队推荐娜娜莉+主角+九原+早雾。",
                "source_hint": "curated",
            }
        ]
    return []


def _is_low_quality_search_result(title: str, url: str, snippet: str) -> bool:
    text = f"{title} {url} {snippet}".lower()
    bad_domains = ["baike.baidu.com", "hanyu.baidu.com", "zdic.net", "cidian", "baike.sogou.com", "dictionary", "wiktionary"]
    if any(d in text for d in bad_domains):
        return True
    bad_terms = ["汉语文字", "现代汉语", "异体字", "一级字", "读作", "本义", "拼音"]
    return any(t in text for t in bad_terms)


def _tool_tavily_search(query: str, limit: int = 5) -> dict:
    try:
        import urllib.error, urllib.request
        payload = json.dumps({
            "query": query, "max_results": max(1, min(int(limit), 10)),
            "search_depth": "basic", "include_answer": False, "include_raw_content": False,
            "api_key": _TAVILY_API_KEY,
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://api.tavily.com/search", data=payload, method="POST",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {_TAVILY_API_KEY}"}
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8", errors="ignore"))
        results = []
        for item in data.get("results", [])[: max(limit * 2, 10)]:
            title = str(item.get("title", ""))[:200]
            url = str(item.get("url", ""))
            snippet = str(item.get("content", item.get("snippet", "")))[:500]
            if not _is_low_quality_search_result(title, url, snippet):
                results.append({"title": title, "url": url, "snippet": snippet, "score": item.get("score")})
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
        req = urllib.request.Request(
            f"https://www.bing.com/search?q={q}",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0"}
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8", errors="ignore")
        results = []
        blocks = _re.findall(r'<li class="b_algo"[^>]*>.*?</li>', html, _re.DOTALL)
        for b in blocks[: max(limit * 4, 12)]:
            h2 = _re.search(r'<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>\s*</h2>', b, _re.DOTALL)
            if not h2: continue
            href = _html.unescape(h2.group(1))
            title = _html.unescape(_re.sub(r"<[^>]+>", "", h2.group(2))).strip()
            cap = _re.search(r'<div class="b_caption"[^>]*>\s*<p[^>]*>(.*?)</p>', b, _re.DOTALL)
            snippet = _html.unescape(_re.sub(r"<[^>]+>", "", cap.group(1))).strip() if cap else ""
            if not _is_low_quality_search_result(title, href, snippet):
                results.append({"title": title[:200], "url": href, "snippet": snippet[:300]})
            if len(results) >= limit: break
        
        curated = _curated_game_results(query)
        merged_results = _dedupe_search_results(curated + results, limit)
        if not merged_results:
            return {"ok": True, "count": 0, "results": [], "source": "Bing", "query": enhanced_query, "note": "未解析出高质量结果"}
        return {"ok": True, "count": len(merged_results), "results": merged_results, "source": "Bing+Curated" if curated else "Bing", "query": enhanced_query}
    except Exception as e:
        return {"ok": False, "error": str(e)}


_WEB_ENABLED = False
_TAVILY_API_KEY = ""

def set_tavily_api_key(api_key: str) -> None:
    global _TAVILY_API_KEY
    _TAVILY_API_KEY = (api_key or "").strip()

def get_tavily_api_key() -> str:
    return _TAVILY_API_KEY

def set_web_enabled(enabled: bool) -> None:
    global _WEB_ENABLED
    _WEB_ENABLED = bool(enabled)

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
    "read_file_content": lambda args: read_file_content_sync(
        args.get("path", ""),
        int(args.get("max_lines", 200)),
        int(args.get("max_chars", 10000)),
        bool(args.get("read_from_tail", False)),
    ),
    "open_system_file": lambda args: open_system_file_sync(
        args.get("path", ""), args.get("method", "default")
    ),
    "create_reminder": lambda args: tool_create_reminder(
        args.get("trigger_time", "") or args.get("time_expr", ""),
        args.get("content", "") or args.get("task_content", ""),
        args.get("action_type", "toast"),
        args.get("workflow_name", ""),
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
    profile_summary = ""
    try:
        profile_summary = get_active_profile_summary()
    except Exception:
        profile_summary = ""
    profile_block = f"\n{profile_summary}\n" if profile_summary else ""
    return f"""你是一个桌面自动化助手,运行在用户的 Windows 电脑上。用户会用自然语言跟你说话,你需要:
1. 理解用户意图
2. 决定是否需要调用工具
3. 如果需要,**严格按 JSON 格式**输出工具调用指令
4. 如果不需要(闲聊/确认/信息查询),直接给出友好回答

【当前运行状态】
- 联网开关: {web_state}
- {web_rule}
{profile_block}
【可用工具】
{tools_text}

【输出格式】

需要工具时:
{{
  "action": "工具名",
  "args": {{ "参数名": "参数值" }},
  "reply": "对用户说的话,告诉用户在做什么 (此项可选)"
}}

不需要工具时:
{{
  "action": null,
  "reply": "直接回答用户"
}}

【规则】
- 只输出 JSON,不要有其他文字
- 工具名必须从上面列表中选
- 工具调用不要嵌套,一次只调一个
- **用户说"打开XX文件夹" / "打开XX文件" / "查看XX" 时：**
  如果你不知道绝对路径，请先调用 `search_local_files`。获取绝对路径后，**必须立即在下一步调用 `open_system_file` 来打开它**。绝不可仅仅在回复里描述“我找到了该文件”而拒绝打开操作。
- search_local_files 多结果选择规则：
  1. 优先选择不在 backups 文件夹里的路径。
  2. 如果都有/都没有 backups，优先选 date_modified 最近的那条。
  3. 绝对不要列出所有结果让用户选，你必须自主做决定。
- **【硬性禁止】绝对禁止在输出中包含 <think>...</think> 或 <thinking>...</thinking> 之类的内部推理/思考块。**
  - 不管是 JSON 里的 reply 字段,还是 action 工具调用的上下文,都**不得**出现这类标签。
  - 内部推理应当在你"内心"完成,直接产出最终结论/JSON 即可。
  - 客户端会用正则强制剥离这类标签,但**你也必须从源头避免输出**,这是双保险。
"""


# ---------------------------------------------------------------------------
# 后台 Worker (多轮 Agent Loop 核心升级)
# ---------------------------------------------------------------------------
class ChatWorker(QThread):
    """在独立线程跑: 用户消息 → AssistantCore → 事件流 → GUI 信号

    重构后:不再自己处理 LLM/工具调用,完全委托给 AssistantCore。
    保留所有原有信号名以兼容 GUI 绑定。
    """

    thinking = Signal(str)                # "正在思考..." / "正在处理结果..."
    tool_call = Signal(str, dict)          # 调用的工具名 + 参数
    tool_result = Signal(str, dict)        # 工具结果
    assistant_message = Signal(str)        # 最终回复(不含表情标签)
    expression = Signal(str)               # 表情信号 (供 UI/头像绑定)
    error = Signal(str)                    # 错误
    log = Signal(str)                      # 调试日志

    def __init__(
        self,
        backend: "LLMBackend" = None,       # 向后兼容:旧调用方传 LLMBackend,会自动构造 AssistantCore
        history: list[dict] = None,
        user_msg: str = "",
        timeout: float = 30.0,
        web_enabled: bool = False,
        core: "AssistantCore" = None,       # 新调用方直接传 AssistantCore(推荐)
    ):
        super().__init__()
        self._backend = backend            # 兼容旧调用
        self._history = history or []
        self._user_msg = user_msg
        self._timeout = timeout
        self._web_enabled = web_enabled

        # 优先使用显式传入的 core;否则从 backend 构造;再否则用默认
        if core is not None:
            self._core = core
        elif backend is not None:
            # 从 LLMBackend 构造 AssistantCore(向后兼容)
            from assistant_core import AssistantCore
            self._core = AssistantCore(
                base_url=getattr(backend, "base_url", "http://127.0.0.1:16260/v1"),
                api_key=getattr(backend, "api_key", "EMPTY"),
                model=getattr(backend, "model", "desktop-auto-v1"),
                timeout=timeout,
                web_enabled=web_enabled,
            )
        else:
            from assistant_core import AssistantCore
            self._core = AssistantCore(web_enabled=web_enabled)

    def run(self):
        try:
            self.thinking.emit("正在思考...")
            sys_prompt = self._core.build_chat_system_prompt(web_enabled=self._web_enabled)
            context = {"chat_history": list(self._history)}

            # 累积 assistant_message(可能多个 text 事件拼接)
            pending_text: list[str] = []
            turn_count = 0

            for event in self._core.process_chat_request(
                user_text=self._user_msg,
                context=context,
                system_prompt=sys_prompt,
            ):
                et = event["type"]

                if et == "text":
                    pending_text.append(event["content"])
                elif et == "tool_start":
                    # 把累积的 text 先发射出去,避免和工具状态混在一起
                    if pending_text:
                        self.thinking.emit("".join(pending_text))
                        pending_text.clear()
                    self.tool_call.emit(
                        event["tool_name"],
                        event.get("args") or {},
                    )
                    turn_count += 1
                elif et == "tool_finish":
                    self.tool_result.emit(
                        event["tool_name"],
                        event.get("result") or {},
                    )
                elif et == "expression":
                    # 表情信号 - 供给 GUI 头像/动画模块使用
                    self.expression.emit(event['hint'])
                elif et == "error":
                    self.error.emit(event["content"])
                elif et == "done":
                    break

            # 最终回复
            if pending_text:
                final_text = "".join(pending_text).strip()
                if final_text:
                    self.assistant_message.emit(final_text)
                elif turn_count == 0:
                    self.assistant_message.emit("(无回复)")

        except Exception as e:
            import traceback
            self.error.emit(f"{e}\n{traceback.format_exc()}")

# ---------------------------------------------------------------------------
class ContextChatTab(QWidget):
    """AI 对话标签页 - 调用 MCP 工具的聊天助手"""

    backend_changed = Signal(object)        # 让父级同步后端
    log_signal = Signal(str)                # 转发到 context_tab 主日志
    html_appended = Signal(str)             # 同步给小聊天窗
    toast_broadcast = Signal(object)        # 广播到 context_tab toast 系统

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self._backend: LLMBackend = OpenAICompatibleBackend()  # 默认
        self._history: list[dict] = []        # 对话历史 [{role, content}]
        self._worker: Optional[ChatWorker] = None
        self._pending_user_msg: str = ""
        self._pending_tools: list[dict] = []
        self._next_context: list[dict] = []   # 点击气泡后注入给下一轮 AI 的隐藏上下文
        self._inline_status_active = False    # 本轮是否已在对话区显示状态 AI 行
        self._inline_status_phase = ""
        self._max_history = 20               # 保留最近 20 轮
        try:
            cleanup_old_logs(retention_days=30)
        except Exception:
            pass
        self._build_ui()
        self.setMaximumWidth(900)

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
        hint = QLabel("支持:列出/执行工作流 / 启动应用 / 搜文件 / 读文件 / 打开文件")
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
        self.chat_view.setMaximumHeight(450)
        self.chat_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        root.addWidget(self.chat_view, stretch=1)

        # 输入区
        input_hud = QWidget()
        iv = QVBoxLayout(input_hud)
        input_row = QHBoxLayout()
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("例: 帮我打开微信 / 跑一下 zzz日常 工作流 / 搜索并打开酒馆文件夹")
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

        self.chk_show_proactive_push = QCheckBox("显示主动推送")
        self.chk_show_proactive_push.setChecked(False)
        self.chk_show_proactive_push.setToolTip("关闭后，气泡主动推荐不会自动同步到 AI 对话记录")
        ctrl_row.addWidget(self.chk_show_proactive_push)

        self.chk_log_toast_actions = QCheckBox("记录气泡点击动作")
        self.chk_log_toast_actions.setChecked(False)
        self.chk_log_toast_actions.setToolTip("关闭后，点击气泡不会在 AI 对话里追加动作说明")
        ctrl_row.addWidget(self.chk_log_toast_actions)

        # 联网开关
        self.chk_web = QCheckBox("🌐 联网")
        self.chk_web.setToolTip("开启后,AI 可以调用 web_search 工具 (Bing) 进行联网搜索")
        self.chk_web.toggled.connect(self._on_web_toggle)
        ctrl_row.addWidget(self.chk_web)

        ctrl_row.addStretch()

        btn_clear = QPushButton("🧹 清空")
        btn_clear.clicked.connect(self._on_clear)
        ctrl_row.addWidget(btn_clear)

        iv.addLayout(ctrl_row)
        root.addWidget(input_hud)

        # 状态栏
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: #666; font-size: 11px; padding: 4px;")
        root.addWidget(self.status_label)

        # 欢迎语
        self._append_system(
            "👋 你好!我是你的桌面自动化助手。\n"
            "你可以让我:\n"
            "  • 搜索并打开文件夹/文件 (例: '帮我打开酒馆文件夹')\n"
            "  • 读取日志内容排错 (例: '帮我读取桌面auto的log日志看看')\n"
            "  • 执行工作流(例: '跑一下 zzz日常')\n\n"
            "💡 提示: 先在「⚙️ 后端」标签页配好 LLM。"
        )

    # ---- 后端接入 ----
    def set_backend(self, backend: LLMBackend):
        self._backend = backend

    # ---- 用户发送 ----
    def add_next_context(self, content: str, visible_hint: str = ""):
        content = (content or "").strip()
        if not content:
            return
        self._next_context.append({"role": "system", "content": content[:2000]})
        self._next_context = self._next_context[-5:]
        if visible_hint:
            self._append_system(visible_hint)

    def send_text(self, text: str):
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
            self._append_system("⚠️ 当前后端不支持对话，请在「⚙️ 后端」选择 OpenAI 兼容协议。")
            self.status_label.setText("⚠️ 后端未就绪")
            return

        try:
            set_web_enabled(self.chk_web.isChecked())
        except Exception:
            pass

        self._pending_user_msg = text
        self._pending_tools = []
        self._append_user(text)
        self.input_edit.clear()
        self.btn_send.setEnabled(False)
        self.status_label.setText("💭 思考中…")
        self._inline_status_active = False
        self._inline_status_phase = ""

        history_for_worker = []
        if self.chk_keep_history.isChecked():
            history_for_worker.extend(list(self._history))
        if self._next_context:
            history_for_worker.extend(self._next_context)
            self._next_context = []
            
        self._worker = ChatWorker(
            backend=self._backend,
            history=history_for_worker,
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
            is_replying = "生成" in msg or "回复" in msg
            if is_replying:
                self.status_label.setText("✨ 回复中…")
                if self._inline_status_phase != "replying":
                    self._append_assistant_status("✨ 回复中…")
                    self._inline_status_active = True
                    self._inline_status_phase = "replying"
            else:
                self.status_label.setText(f"💭 {msg}")
                if not self._inline_status_active or self._inline_status_phase != "thinking":
                    self._append_assistant_status(f"💭 {msg}")
                    self._inline_status_active = True
                    self._inline_status_phase = "thinking"

    @Slot(str, dict)
    def _on_tool_call(self, action: str, args: dict):
        self.log_signal.emit(f"[AI对话] 调用工具: {action}({args})")
        self._pending_tools.append({"name": action, "args": args, "ok": False})
        if self.chk_show_thinking.isChecked():
            args_str = ", ".join(f"{k}={v}" for k, v in args.items())
            self._append_system(f"🔧 调用工具: {action}({args_str})")

    @Slot(str, dict)
    def _on_tool_result(self, action: str, result: dict):
        self.log_signal.emit(f"[AI对话] {action} 结果: {json.dumps(result, ensure_ascii=False)[:200]}")
        ok = result.get("ok", False)
        for item in reversed(self._pending_tools):
            if item.get("name") == action and item.get("ok") is False:
                item["ok"] = bool(ok)
                break
        icon = "✅" if ok else "❌"
        intent = ToastIntent(
            intent=f"{icon} {action}",
            message=f"AI 已调用工具: {action}",
            suggested_action="",
            action_param="",
        )
        self.toast_broadcast.emit(intent)
        if self.chk_show_thinking.isChecked():
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
        self._inline_status_active = False
        self._inline_status_phase = ""
        self._append_assistant(msg)
        if self.chk_keep_history.isChecked():
            self._history.append({"role": "user", "content": self._pending_user_msg or "(上轮)"})
            self._history.append({"role": "assistant", "content": msg})
            while len(self._history) > self._max_history * 2:
                self._history.pop(0)
        try:
            append_chat_log(self._pending_user_msg or "", msg, tools_used=self._pending_tools)
        except Exception as e:
            # 业务路径异常: 写聊天流水是 local IO,失败需要可追溯
            import traceback as _tb
            self.log_signal.emit(
                f"[AI对话] 写入聊天流水失败: {e}\n{_tb.format_exc()}"
            )

    @Slot(str)
    def _on_error(self, msg: str):
        self._append_system(f"❌ 错误: {msg}")
        self.log_signal.emit(f"[AI对话] 错误: {msg}")
        self.status_label.setText("❌ 出错")

    @Slot()
    def _on_worker_finished(self):
        self.btn_send.setEnabled(True)
        self.status_label.setText("就绪")
        self._inline_status_active = False
        self._inline_status_phase = ""
        if self._worker:
            self._worker.deleteLater()
            self._worker = None

    def _on_clear(self):
        self.chat_view.clear()
        self._history.clear()
        self._append_system("🧹 已清空对话历史")

    def _on_web_toggle(self, checked: bool):
        from context_chat import set_web_enabled
        set_web_enabled(checked)
        state = "✅ 已开启 - AI 可调用 web_search 联网搜索" if checked else "❌ 已关闭 - 不可调用联网工具"
        self._append_system(f"🌐 联网开关: {state}")

    def on_intent(self, intent):
        try:
            if not getattr(self, "chk_show_proactive_push", None) or not self.chk_show_proactive_push.isChecked():
                return
            msg = getattr(intent, "message", "") or ""
            sug = getattr(intent, "suggested_action", "") or ""
            param = getattr(intent, "action_param", "") or ""
            tag = getattr(intent, "intent", "") or ""
            text = msg
            if sug:
                text += f"\n\n[操作: {sug}" + (f" / {param}" if param else "") + "]"
            self._append_assistant(f"💡 [主动推送 / {tag}]\n{text}")
        except Exception as e:
            self._append_system(f"❌ on_intent 出错: {e}")

    def on_toast_clicked(self, intent):
        try:
            # 举手(把气泡文案以 AI 身份写进 VTuber 后端 chat history)放在门控之前
            # —— 举手是核心交互,不应被"是否在 AI 对话页显示动作"的 checkbox 门控
            # 取主窗口的 _vtuber_bridge(由 MainWindow._init_vtuber_bridge 初始化)
            win = self.window()
            bridge = getattr(win, "_vtuber_bridge", None) if win else None
            if bridge and getattr(bridge, "enabled", False):
                ok = bridge.acknowledge_ai_message(intent.message)
                self._append_log(f"[举手] acknowledge_ai_message OK={ok}")
            else:
                self._append_log("[举手] 桥接未就绪,跳过 ack")
            # UI 反馈:本地 chat 标记已举手(也始终执行,与 checkbox 解耦)
            self._append_assistant(f"✅ 已举手 ✓ {intent.message}")

            # 以下是受 chk_log_toast_actions 门控的"在 AI 对话页显示动作记录"逻辑
            if not getattr(self, "chk_log_toast_actions", None) or not self.chk_log_toast_actions.isChecked():
                return
            msg = getattr(intent, "message", "") or ""
            sug = getattr(intent, "suggested_action", "") or ""
            param = getattr(intent, "action_param", "") or ""
            self._append_user(f"👆 点击了气泡 [操作: {sug}{' / ' + param if param else ''}]\n原消息: {msg}")
        except Exception as e:
            self._append_system(f"❌ on_toast_clicked 出错: {e}")

    def on_action_executed(self, intent):
        try:
            if not getattr(self, "chk_log_toast_actions", None) or not self.chk_log_toast_actions.isChecked():
                return
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

    def _append_user(self, text: str):
        ts = datetime.now().strftime("%H:%M:%S")
        html = (
            f'<div style="margin:6px 0; padding:8px; background:#dbeafe; border-radius:6px;">'
            f'<b style="color:#1e40af;">🧑 你</b> <span style="color:#888; font-size:10px;">[{ts}]</span><br>'
            f'<span style="color:#1e3a8a;">{self._esc(text)}</span>'
            f'</div>'
        )
        self._append_html(html)

    def _append_assistant_status(self, text: str):
        ts = datetime.now().strftime("%H:%M:%S")
        html = (
            f'<div style="margin:6px 0; padding:8px; background:#ecfdf5; border:1px dashed #86efac; border-radius:6px;">'
            f'<b style="color:#16a34a;">🤖 助手</b> <span style="color:#888; font-size:10px;">[{ts}]</span><br>'
            f'<span style="color:#15803d;">{self._esc(text)}</span>'
            f'</div>'
        )
        self._append_html(html)

    def _append_assistant(self, text: str):
        ts = datetime.now().strftime("%H:%M:%S")
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
        sb = self.chat_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    @staticmethod
    def _esc(text: str) -> str:
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class MiniChatDialog(QDialog):
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
        self.chat_view.setStyleSheet("QTextEdit { background:#fafafa; border:1px solid #e5e7eb; border-radius:6px; padding:8px; }")
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