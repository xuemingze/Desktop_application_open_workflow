# chat_memory.py
# 功能: AI 对话流水 JSONL，30 天滚动清理。统一使用 data_paths.USER_DATA_DIR。

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from data_paths import USER_DATA_DIR

LOG_DIR = USER_DATA_DIR / "chat_logs"
MAX_TEXT_CHARS = 2000
MAX_TOOL_CHARS = 1000


def _now() -> _dt.datetime:
    return _dt.datetime.now().replace(microsecond=0)


def _safe_text(value: str, limit: int = MAX_TEXT_CHARS) -> str:
    return (value or "").strip()[:limit]


def get_current_log_path(now: Optional[_dt.datetime] = None) -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    current_month = (now or _now()).strftime("%Y-%m")
    return LOG_DIR / f"chat_history_{current_month}.jsonl"


def infer_skip_memory(user_msg: str, tools_used: Optional[List[Dict]] = None) -> bool:
    """操作型命令默认不进入长期画像抽取。"""
    text = (user_msg or "").lower()
    op_keywords = [
        "打开", "启动", "运行", "执行", "关闭", "关机", "重启", "删除", "清空",
        "open", "launch", "run", "delete", "shutdown", "restart",
    ]
    tool_names = {str(t.get("name") or t.get("action") or "") for t in (tools_used or []) if isinstance(t, dict)}
    op_tools = {"run_workflow", "launch_shortcut", "open_system_file", "create_reminder"}
    return any(k in text for k in op_keywords) or bool(tool_names & op_tools)


def append_chat_log(
    user_msg: str,
    ai_reply: str,
    tools_used: Optional[List[Dict]] = None,
    skip_memory: Optional[bool] = None,
) -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    if skip_memory is None:
        skip_memory = infer_skip_memory(user_msg, tools_used)
    safe_tools = []
    for item in tools_used or []:
        if not isinstance(item, dict):
            continue
        safe_tools.append({
            "name": _safe_text(str(item.get("name") or item.get("action") or ""), 80),
            "args": _safe_text(json.dumps(item.get("args") or {}, ensure_ascii=False), MAX_TOOL_CHARS),
            "ok": bool(item.get("ok", False)),
        })
    entry = {
        "timestamp": _now().isoformat(),
        "user": _safe_text(user_msg),
        "ai": _safe_text(ai_reply),
        "tools": safe_tools,
        "skip_memory": bool(skip_memory),
    }
    path = get_current_log_path()
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return path


def cleanup_old_logs(retention_days: int = 30) -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    cutoff_date = _now() - _dt.timedelta(days=max(1, int(retention_days or 30)))
    removed = 0
    for log_file in LOG_DIR.glob("chat_history_*.jsonl"):
        try:
            date_str = log_file.stem.replace("chat_history_", "") + "-01"
            file_date = _dt.datetime.strptime(date_str, "%Y-%m-%d")
            if (file_date + _dt.timedelta(days=31)) < cutoff_date:
                log_file.unlink()
                removed += 1
        except Exception:
            pass
    return removed


def iter_chat_logs_for_date(target_date: _dt.datetime) -> Iterable[Dict]:
    path = get_current_log_path(target_date)
    date_prefix = target_date.strftime("%Y-%m-%d")
    if not path.exists():
        return []
    rows: list[Dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                item = json.loads(line)
            except Exception:
                continue
            if str(item.get("timestamp", "")).startswith(date_prefix):
                rows.append(item)
    return rows


def build_chat_memory_digest(target_date: Optional[_dt.datetime] = None, limit: int = 80) -> str:
    target_date = target_date or _now()
    rows = [r for r in iter_chat_logs_for_date(target_date) if not r.get("skip_memory")]
    rows = rows[-max(1, int(limit or 80)):]
    if not rows:
        return ""
    lines = []
    for row in rows:
        ts = str(row.get("timestamp", ""))[11:16]
        user = _safe_text(row.get("user", ""), 500)
        ai = _safe_text(row.get("ai", ""), 500)
        lines.append(f"[{ts}] 用户: {user}\n[{ts}] AI: {ai}")
    return "\n\n".join(lines)
