# reminders.py
# 功能: 本地提醒任务库 + 到期查询。统一使用 data_paths.USER_DATA_DIR。

from __future__ import annotations

import datetime as _dt
import re as _re
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional

from data_paths import USER_DATA_DIR

# CST (UTC+8) 时区修复：避免 Windows BIOS=UTC 导致 datetime.now() 返回 UTC 而非本地时间
_CST = _dt.timezone(_dt.timedelta(hours=8))

def _now() -> _dt.datetime:
    """返回当前 CST 时间（naive，不带时区信息但值为本地时间）"""
    return _dt.datetime.now(_CST).replace(microsecond=0)

DB_PATH = USER_DATA_DIR / "reminders.sqlite"
_VALID_ACTIONS = {"toast", "run_workflow"}
_VALID_STATUS = {"pending", "done", "delayed", "dismissed"}


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trigger_time TEXT NOT NULL,
                content TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                action_type TEXT DEFAULT 'toast',
                workflow_name TEXT,
                created_from_chat INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reminders_status_time ON reminders(status, trigger_time)")
        conn.commit()


# _now() 已在上方定义（CST 时区感知，防止 Windows BIOS=UTC 导致时间偏差）
# 这里不再重复定义，以保持时区一致性


def _safe_text(value: str, limit: int = 500) -> str:
    return (value or "").strip()[:limit]


def parse_time_expr(time_expr: str, base: Optional[_dt.datetime] = None) -> str:
    """把 ISO/常见中文相对时间解析为本地 ISO 字符串。

    支持: 2026-06-21T15:00:00, 2026-06-21 15:00, 半小时后, 10分钟后, 2小时后,
    明天下午3点, 明天15:30。
    """
    text = (time_expr or "").strip()
    if not text:
        raise ValueError("time_expr 不能为空")
    base = base or _now()

    # ISO / 常见绝对时间
    normalized = text.replace("/", "-").replace(" ", "T", 1)
    for candidate in (normalized, text):
        try:
            return _dt.datetime.fromisoformat(candidate).replace(microsecond=0).isoformat()
        except Exception:
            pass
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            return _dt.datetime.strptime(text.replace("/", "-"), fmt).replace(microsecond=0).isoformat()
        except Exception:
            pass

    if "半小时" in text or "半个小时" in text:
        return (base + _dt.timedelta(minutes=30)).isoformat()
    m = _re.search(r"(\d+)\s*(分钟|分|小时|个小时|天)后", text)
    if m:
        num = int(m.group(1))
        unit = m.group(2)
        if unit in {"分钟", "分"}:
            delta = _dt.timedelta(minutes=num)
        elif unit in {"小时", "个小时"}:
            delta = _dt.timedelta(hours=num)
        else:
            delta = _dt.timedelta(days=num)
        return (base + delta).replace(microsecond=0).isoformat()

    # 明天/今天 + 上午/下午 + N点[:MM]
    day_offset = 1 if "明天" in text else 0
    if "今天" in text or "明天" in text:
        m = _re.search(r"(上午|下午|晚上|中午)?\s*(\d{1,2})(?:[:：点](\d{1,2})?)?", text)
        if m:
            period = m.group(1) or ""
            hour = int(m.group(2))
            minute = int(m.group(3) or 0)
            if period in {"下午", "晚上"} and hour < 12:
                hour += 12
            if period == "中午" and hour < 12:
                hour += 12
            target = (base + _dt.timedelta(days=day_offset)).replace(hour=hour, minute=minute, second=0, microsecond=0)
            if target <= base:
                target += _dt.timedelta(days=1)
            return target.isoformat()

    raise ValueError(f"无法解析提醒时间: {time_expr}")


def create_reminder(
    trigger_time: str,
    content: str,
    action_type: str = "toast",
    workflow_name: Optional[str] = None,
    created_from_chat: bool = True,
) -> int:
    init_db()
    action_type = action_type if action_type in _VALID_ACTIONS else "toast"
    trigger_iso = parse_time_expr(trigger_time)
    content = _safe_text(content, 500)
    workflow_name = _safe_text(workflow_name or "", 200) or None
    now = _now().isoformat()
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO reminders (trigger_time, content, status, action_type, workflow_name, created_from_chat, created_at, updated_at)
            VALUES (?, ?, 'pending', ?, ?, ?, ?, ?)
            """,
            (trigger_iso, content, action_type, workflow_name, 1 if created_from_chat else 0, now, now),
        )
        conn.commit()
        return int(cur.lastrowid)


def get_due_reminders(now: Optional[_dt.datetime] = None, limit: int = 20) -> List[Dict]:
    init_db()
    now_iso = (now or _now()).isoformat()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM reminders
            WHERE status = 'pending' AND trigger_time <= ?
            ORDER BY trigger_time ASC
            LIMIT ?
            """,
            (now_iso, int(limit or 20)),
        ).fetchall()
    return [dict(row) for row in rows]


def get_all_pending_reminders(limit: int = 100) -> List[Dict]:
    """获取所有状态为 pending 的提醒，不限制时间（含未来时间）"""
    init_db()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM reminders
            WHERE status = 'pending'
            ORDER BY trigger_time ASC
            LIMIT ?
            """,
            (int(limit or 100),),
        ).fetchall()
    return [dict(row) for row in rows]


def update_reminder_status(reminder_id: int, status: str, delay_minutes: Optional[int] = None) -> bool:
    init_db()
    status = status if status in _VALID_STATUS else "dismissed"
    now = _now()
    with get_connection() as conn:
        if status == "delayed" and delay_minutes:
            new_time = (now + _dt.timedelta(minutes=int(delay_minutes))).isoformat()
            conn.execute(
                "UPDATE reminders SET status = 'pending', trigger_time = ?, updated_at = ? WHERE id = ?",
                (new_time, now.isoformat(), int(reminder_id)),
            )
        else:
            conn.execute(
                "UPDATE reminders SET status = ?, updated_at = ? WHERE id = ?",
                (status, now.isoformat(), int(reminder_id)),
            )
        conn.commit()
        return conn.total_changes > 0


init_db()
