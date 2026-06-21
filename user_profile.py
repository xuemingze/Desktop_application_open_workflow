# user_profile.py
# 功能: 独立用户画像记忆库。本地 SQLite，默认开启，可停用/清空。

from __future__ import annotations

import datetime as _dt
import json
import sqlite3
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from data_paths import USER_DATA_DIR

DB_PATH = USER_DATA_DIR / "user_profile_memory.db"
CONFIG_PATH = USER_DATA_DIR / "config.json"
VALID_CATEGORIES = {"facts", "preferences", "projects", "entities", "file_anchors", "state"}


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
            CREATE TABLE IF NOT EXISTS profile_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                content TEXT NOT NULL,
                confidence REAL DEFAULT 1.0,
                source TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_profile_active_category ON profile_memory(is_active, category)")
        conn.commit()


def _now() -> str:
    return _dt.datetime.now().replace(microsecond=0).isoformat()


def _safe_text(value: str, limit: int = 1000) -> str:
    return (value or "").strip()[:limit]


def _load_config() -> dict:
    try:
        if CONFIG_PATH.exists():
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_config(cfg: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def is_enabled() -> bool:
    cfg = _load_config()
    return bool(cfg.get("proactive_memory_enabled", True))


def set_enabled(enabled: bool) -> None:
    cfg = _load_config()
    cfg["proactive_memory_enabled"] = bool(enabled)
    _save_config(cfg)


def add_or_update_memory(category: str, content: str, source: str = "chat", confidence: float = 1.0) -> int:
    init_db()
    if not is_enabled():
        return 0
    category = category if category in VALID_CATEGORIES else "facts"
    content = _safe_text(content)
    if not content:
        return 0
    confidence = max(0.0, min(1.0, float(confidence or 1.0)))
    now = _now()
    with get_connection() as conn:
        # 精确重复时只刷新更新时间和置信度，避免无限膨胀。
        row = conn.execute(
            "SELECT id FROM profile_memory WHERE is_active = 1 AND category = ? AND content = ? LIMIT 1",
            (category, content),
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE profile_memory SET confidence = MAX(confidence, ?), source = ?, updated_at = ? WHERE id = ?",
                (confidence, _safe_text(source, 100), now, int(row["id"])),
            )
            conn.commit()
            return int(row["id"])
        cur = conn.execute(
            """
            INSERT INTO profile_memory (category, content, confidence, source, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (category, content, confidence, _safe_text(source, 100), now, now),
        )
        conn.commit()
        return int(cur.lastrowid)


def deprecate_memory(memory_id: int) -> bool:
    init_db()
    with get_connection() as conn:
        conn.execute("UPDATE profile_memory SET is_active = 0, updated_at = ? WHERE id = ?", (_now(), int(memory_id)))
        conn.commit()
        return conn.total_changes > 0


def clear_all_memory() -> None:
    init_db()
    with get_connection() as conn:
        conn.execute("UPDATE profile_memory SET is_active = 0, updated_at = ? WHERE is_active = 1", (_now(),))
        conn.commit()


def get_active_profile_summary(limit_per_category: int = 5) -> str:
    init_db()
    if not is_enabled():
        return ""
    categories = ["preferences", "projects", "facts", "file_anchors", "entities", "state"]
    lines = ["【用户画像记忆】"]
    with get_connection() as conn:
        for cat in categories:
            rows = conn.execute(
                """
                SELECT content FROM profile_memory
                WHERE is_active = 1 AND category = ?
                ORDER BY confidence DESC, updated_at DESC
                LIMIT ?
                """,
                (cat, max(1, int(limit_per_category or 5))),
            ).fetchall()
            if rows:
                lines.append(f"- {cat}:")
                for row in rows:
                    lines.append(f"  * {row['content']}")
    return "\n".join(lines) if len(lines) > 1 else ""


def apply_memory_actions(actions: Iterable[Dict], source: str = "chat") -> int:
    count = 0
    for item in actions or []:
        if not isinstance(item, dict):
            continue
        action = str(item.get("action") or "add").lower()
        if action in {"add", "update"}:
            memory_id = add_or_update_memory(
                category=str(item.get("category") or "facts"),
                content=str(item.get("content") or item.get("fact") or ""),
                source=str(item.get("source") or source),
                confidence=float(item.get("confidence") or 1.0),
            )
            if memory_id:
                count += 1
        elif action in {"deprecate", "delete", "disable"} and item.get("id"):
            if deprecate_memory(int(item["id"])):
                count += 1
    return count


def parse_json_actions(text: str) -> List[Dict]:
    raw = (text or "").strip()
    if not raw:
        return []
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw.split("\n", 1)[-1] if "\n" in raw else raw
    start = raw.find("[")
    end = raw.rfind("]")
    if start >= 0 and end >= start:
        raw = raw[start:end + 1]
    data = json.loads(raw)
    return data if isinstance(data, list) else []


init_db()
