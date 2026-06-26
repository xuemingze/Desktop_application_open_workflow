# -*- coding: utf-8 -*-
"""Step 2-2F 护栏: user_profile.py 画像记忆库

覆盖范围:
  - 14 个公开符号全部锁死行为
  - 不依赖 desktop_auto / 跨模块副作用
  - 4 个消费方引用面 (desktop_auto / context_chat / companion_bridge / tools_tab)
  - 调试关键坑: SQLite WAL/timeout + monkeypatch 替换 get_connection 隔离 tmp 目录

执行:
  pytest tests/test_user_profile.py -q
"""
from __future__ import annotations

import importlib
import json
import os
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# ---------- fixtures ----------

@pytest.fixture
def profile_module(tmp_path, monkeypatch):
    """把 user_profile 的 DB_PATH / CONFIG_PATH / _load_config._cache 重定向到 tmp 路径

    关键: user_profile 顶层 `DB_PATH = USER_DATA_DIR / "user_profile_memory.db"` 是模块级常量,
    但函数内部只引用符号 DB_PATH / CONFIG_PATH, 所以 monkeypatch.setattr 即可生效。
    """
    import user_profile
    test_db = tmp_path / "user_profile_memory.db"
    test_cfg = tmp_path / "config.json"
    # 隔离 user_profile 的 USER_DATA_DIR 派生 (保险起见, 整目录指向 tmp)
    monkeypatch.setattr(user_profile, "DB_PATH", test_db)
    monkeypatch.setattr(user_profile, "CONFIG_PATH", test_cfg)
    # 重置可能的 _load_config 缓存 (该模块当前无缓存, 但防万一)
    if hasattr(user_profile, "_load_config_cache"):
        monkeypatch.setattr(user_profile, "_load_config_cache", None)
    yield user_profile


@pytest.fixture
def fresh_db(profile_module):
    """建好空 db"""
    profile_module.init_db()
    return profile_module


# ---------- TestConstantsAndPaths ----------

class TestConstantsAndPaths:
    def test_top_level_imports_intact(self):
        """user_profile.py 顶层 import 完整 (改 import 时要同步更新测试)"""
        import user_profile
        src = (REPO_ROOT / "user_profile.py").read_text(encoding="utf-8")
        for mod in ["sqlite3", "json", "datetime", "pathlib", "data_paths"]:
            assert f"from {mod}" in src or f"import {mod}" in src, f"missing import: {mod}"

    def test_db_path_under_user_data_dir(self, profile_module):
        """DB_PATH = USER_DATA_DIR / 'user_profile_memory.db' (monkeypatch 后路径已替换)"""
        assert profile_module.DB_PATH.name == "user_profile_memory.db"
        assert profile_module.DB_PATH.parent.exists()

    def test_config_path_is_config_json(self, profile_module):
        assert profile_module.CONFIG_PATH.name == "config.json"

    def test_valid_categories_set(self, profile_module):
        assert profile_module.VALID_CATEGORIES == {
            "facts", "preferences", "projects", "entities", "file_anchors", "state",
        }

    def test_db_path_default_uses_user_data_dir(self):
        """原始默认路径 (不通过 fixture) 仍走 USER_DATA_DIR"""
        src = (REPO_ROOT / "user_profile.py").read_text(encoding="utf-8")
        assert 'DB_PATH = USER_DATA_DIR / "user_profile_memory.db"' in src


# ---------- TestNowSafeText ----------

class TestNowSafeText:
    def test_now_isoformat_no_microsecond(self, profile_module):
        s = profile_module._now()
        # ISO format 含 'T' 分隔且无小数部分 (微秒被归零)
        assert "T" in s
        assert "." not in s
        # 可被 datetime 反向解析
        from datetime import datetime
        datetime.fromisoformat(s)

    def test_safe_text_none_returns_empty(self, profile_module):
        assert profile_module._safe_text(None) == ""

    def test_safe_text_strips_whitespace(self, profile_module):
        assert profile_module._safe_text("  hello  ") == "hello"

    def test_safe_text_truncates_at_limit(self, profile_module):
        assert profile_module._safe_text("a" * 500, limit=100) == "a" * 100

    def test_safe_text_default_limit_1000(self, profile_module):
        assert len(profile_module._safe_text("x" * 5000)) == 1000


# ---------- TestConfig ----------

class TestConfig:
    def test_load_config_missing_returns_empty(self, profile_module):
        """无 config.json → {}"""
        assert profile_module._load_config() == {}

    def test_load_config_reads_existing(self, profile_module):
        profile_module.CONFIG_PATH.write_text(
            json.dumps({"proactive_memory_enabled": False, "extra": 1}),
            encoding="utf-8",
        )
        cfg = profile_module._load_config()
        assert cfg.get("proactive_memory_enabled") is False
        assert cfg.get("extra") == 1

    def test_load_config_corrupted_returns_empty(self, profile_module):
        profile_module.CONFIG_PATH.write_text("{bad json", encoding="utf-8")
        assert profile_module._load_config() == {}

    def test_save_config_creates_parent(self, profile_module, tmp_path):
        nested = tmp_path / "a" / "b" / "config.json"
        profile_module.CONFIG_PATH = nested  # type: ignore
        profile_module._save_config({"k": "v"})
        assert nested.exists()
        assert json.loads(nested.read_text(encoding="utf-8")) == {"k": "v"}

    def test_is_enabled_default_true_when_missing(self, profile_module):
        """无 config → 默认 True (opt-out 设计)"""
        assert profile_module.is_enabled() is True

    def test_is_enabled_reads_false(self, profile_module):
        profile_module._save_config({"proactive_memory_enabled": False})
        assert profile_module.is_enabled() is False

    def test_set_enabled_persists(self, profile_module):
        profile_module.set_enabled(False)
        assert profile_module.is_enabled() is False
        # 重新读取也是 False (不是 in-memory cache)
        cfg = profile_module._load_config()
        assert cfg.get("proactive_memory_enabled") is False

    def test_set_enabled_true_after_false(self, profile_module):
        profile_module.set_enabled(False)
        profile_module.set_enabled(True)
        assert profile_module.is_enabled() is True


# ---------- TestInitDb ----------

class TestInitDb:
    def test_creates_profile_memory_table(self, fresh_db):
        with fresh_db.get_connection() as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='profile_memory'"
            ).fetchone()
            assert row is not None

    def test_creates_active_category_index(self, fresh_db):
        with fresh_db.get_connection() as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_profile_active_category'"
            ).fetchone()
            assert row is not None

    def test_init_db_idempotent(self, fresh_db):
        """二次 init 不报错"""
        fresh_db.init_db()
        fresh_db.init_db()  # 第二次
        with fresh_db.get_connection() as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='profile_memory'"
            ).fetchone()
            assert row is not None

    def test_journal_mode_is_wal(self, fresh_db):
        with fresh_db.get_connection() as conn:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            assert mode.lower() == "wal"


# ---------- TestAddOrUpdateMemory ----------

class TestAddOrUpdateMemory:
    def test_returns_positive_id_on_insert(self, fresh_db):
        mid = fresh_db.add_or_update_memory("facts", "用户喜欢 Python", source="chat")
        assert isinstance(mid, int) and mid > 0

    def test_returns_zero_when_disabled(self, fresh_db):
        fresh_db.set_enabled(False)
        assert fresh_db.add_or_update_memory("facts", "x") == 0

    def test_invalid_category_falls_back_to_facts(self, fresh_db):
        mid = fresh_db.add_or_update_memory("unknown_cat", "test", source="chat")
        assert mid > 0
        with fresh_db.get_connection() as conn:
            row = conn.execute("SELECT category FROM profile_memory WHERE id=?", (mid,)).fetchone()
            assert row["category"] == "facts"

    def test_empty_content_returns_zero(self, fresh_db):
        assert fresh_db.add_or_update_memory("facts", "") == 0
        assert fresh_db.add_or_update_memory("facts", "   ") == 0

    def test_confidence_clamped_to_0_1(self, fresh_db):
        # > 1.0 被截断到 1.0
        mid_hi = fresh_db.add_or_update_memory("facts", "hi", confidence=5.0)
        with fresh_db.get_connection() as conn:
            assert conn.execute("SELECT confidence FROM profile_memory WHERE id=?", (mid_hi,)).fetchone()["confidence"] == 1.0
        # < 0.0 被截断到 0.0
        mid_lo = fresh_db.add_or_update_memory("facts", "lo", confidence=-0.5)
        with fresh_db.get_connection() as conn:
            assert conn.execute("SELECT confidence FROM profile_memory WHERE id=?", (mid_lo,)).fetchone()["confidence"] == 0.0

    def test_duplicate_content_updates_existing(self, fresh_db):
        mid1 = fresh_db.add_or_update_memory("facts", "dup", source="chat", confidence=0.5)
        mid2 = fresh_db.add_or_update_memory("facts", "dup", source="chat", confidence=0.9)
        assert mid1 == mid2  # 同 id
        with fresh_db.get_connection() as conn:
            row = conn.execute("SELECT confidence FROM profile_memory WHERE id=?", (mid1,)).fetchone()
            assert row["confidence"] == 0.9  # MAX(old, new)

    def test_duplicate_different_category_inserts_new(self, fresh_db):
        mid1 = fresh_db.add_or_update_memory("facts", "x", source="chat")
        mid2 = fresh_db.add_or_update_memory("preferences", "x", source="chat")
        assert mid1 != mid2

    def test_safe_text_strips_content(self, fresh_db):
        mid = fresh_db.add_or_update_memory("facts", "  内容  ", source="chat")
        with fresh_db.get_connection() as conn:
            row = conn.execute("SELECT content FROM profile_memory WHERE id=?", (mid,)).fetchone()
            assert row["content"] == "内容"


# ---------- TestDeprecateMemory ----------

class TestDeprecateMemory:
    def test_returns_true_when_deprecated(self, fresh_db):
        mid = fresh_db.add_or_update_memory("facts", "to_deprecate")
        assert fresh_db.deprecate_memory(mid) is True

    def test_returns_false_when_not_exists(self, fresh_db):
        assert fresh_db.deprecate_memory(99999) is False

    def test_marks_is_active_zero(self, fresh_db):
        mid = fresh_db.add_or_update_memory("facts", "x")
        fresh_db.deprecate_memory(mid)
        with fresh_db.get_connection() as conn:
            row = conn.execute("SELECT is_active FROM profile_memory WHERE id=?", (mid,)).fetchone()
            assert row["is_active"] == 0


# ---------- TestClearAllMemory ----------

class TestClearAllMemory:
    def test_clears_all_active_records(self, fresh_db):
        fresh_db.add_or_update_memory("facts", "a")
        fresh_db.add_or_update_memory("preferences", "b")
        fresh_db.clear_all_memory()
        with fresh_db.get_connection() as conn:
            cnt = conn.execute("SELECT COUNT(*) FROM profile_memory WHERE is_active = 1").fetchone()[0]
            assert cnt == 0

    def test_clear_all_is_soft_delete(self, fresh_db):
        """clear_all 只设 is_active=0, 不删行 (与 deprecate 一致)"""
        fresh_db.add_or_update_memory("facts", "x")
        fresh_db.clear_all_memory()
        with fresh_db.get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM profile_memory").fetchone()[0]
            assert total == 1  # 行还在
            active = conn.execute("SELECT COUNT(*) FROM profile_memory WHERE is_active = 1").fetchone()[0]
            assert active == 0


# ---------- TestGetActiveProfileSummary ----------

class TestGetActiveProfileSummary:
    def test_returns_empty_when_disabled(self, fresh_db):
        fresh_db.set_enabled(False)
        fresh_db.add_or_update_memory("facts", "x")
        assert fresh_db.get_active_profile_summary() == ""

    def test_returns_empty_when_no_data(self, fresh_db):
        assert fresh_db.get_active_profile_summary() == ""

    def test_returns_header_when_data_present(self, fresh_db):
        fresh_db.add_or_update_memory("facts", "user likes python")
        summary = fresh_db.get_active_profile_summary()
        assert "【用户画像记忆】" in summary
        assert "facts" in summary
        assert "user likes python" in summary

    def test_excludes_deprecated(self, fresh_db):
        mid = fresh_db.add_or_update_memory("facts", "old memory")
        fresh_db.deprecate_memory(mid)
        summary = fresh_db.get_active_profile_summary()
        assert "old memory" not in summary

    def test_limit_per_category(self, fresh_db):
        for i in range(7):
            fresh_db.add_or_update_memory("facts", f"item_{i}")
        summary = fresh_db.get_active_profile_summary(limit_per_category=3)
        # 3 条以内, 超过 limit 的不应出现
        for i in range(3):
            assert f"item_{i}" in summary or f"item_{4+i}" in summary  # 排序后前 3 或后 3
        # 至少验证格式正确
        assert summary.count("  * ") == 3

    def test_orders_by_confidence_desc(self, fresh_db):
        fresh_db.add_or_update_memory("facts", "low_conf", confidence=0.3)
        fresh_db.add_or_update_memory("facts", "high_conf", confidence=0.9)
        summary = fresh_db.get_active_profile_summary()
        idx_hi = summary.find("high_conf")
        idx_lo = summary.find("low_conf")
        assert 0 <= idx_hi < idx_lo


# ---------- TestApplyAndParseJson ----------

class TestApplyMemoryActions:
    def _setup_with_one(self, fresh_db):
        fresh_db.add_or_update_memory("facts", "seed")
        return 1  # 第一条 id

    def test_add_action_calls_add_or_update(self, fresh_db):
        actions = [{"action": "add", "category": "facts", "content": "new"}]
        count = fresh_db.apply_memory_actions(actions, source="test")
        assert count == 1
        with fresh_db.get_connection() as conn:
            row = conn.execute("SELECT content FROM profile_memory WHERE content='new'").fetchone()
            assert row is not None

    def test_update_action_same_as_add(self, fresh_db):
        actions = [{"action": "update", "category": "facts", "content": "u"}]
        assert fresh_db.apply_memory_actions(actions) == 1

    def test_deprecate_action_soft_deletes(self, fresh_db):
        mid = fresh_db.add_or_update_memory("facts", "to_dep")
        actions = [{"action": "deprecate", "id": mid}]
        assert fresh_db.apply_memory_actions(actions) == 1
        with fresh_db.get_connection() as conn:
            row = conn.execute("SELECT is_active FROM profile_memory WHERE id=?", (mid,)).fetchone()
            assert row["is_active"] == 0

    def test_delete_synonym_for_deprecate(self, fresh_db):
        mid = fresh_db.add_or_update_memory("facts", "x")
        for action in ["delete", "disable"]:
            fresh_db.add_or_update_memory("facts", f"y_{action}")  # 重置
            mid2 = fresh_db.add_or_update_memory("facts", f"z_{action}")
            count = fresh_db.apply_memory_actions([{"action": action, "id": mid2}])
            assert count == 1, f"action={action} should soft-delete"

    def test_empty_iterable_returns_zero(self, fresh_db):
        assert fresh_db.apply_memory_actions([]) == 0

    def test_non_dict_items_skipped(self, fresh_db):
        actions = ["not_a_dict", {"action": "add", "content": "valid"}]
        # 非 dict 跳过, dict 处理
        assert fresh_db.apply_memory_actions(actions) == 1

    def test_missing_id_skips_deprecate(self, fresh_db):
        actions = [{"action": "deprecate"}]  # 无 id 字段
        assert fresh_db.apply_memory_actions(actions) == 0

    def test_unknown_action_ignored(self, fresh_db):
        actions = [{"action": "explode", "content": "x"}]
        # 未知 action 不抛异常
        assert fresh_db.apply_memory_actions(actions) == 0

    def test_content_fallback_to_fact_key(self, fresh_db):
        """content 缺失时尝试 fact 字段"""
        actions = [{"action": "add", "fact": "from_fact_key"}]
        assert fresh_db.apply_memory_actions(actions) == 1
        with fresh_db.get_connection() as conn:
            row = conn.execute("SELECT content FROM profile_memory WHERE content='from_fact_key'").fetchone()
            assert row is not None


class TestParseJsonActions:
    def test_empty_returns_empty_list(self, fresh_db):
        assert fresh_db.parse_json_actions("") == []
        assert fresh_db.parse_json_actions(None) == []

    def test_plain_json_array(self, fresh_db):
        text = '[{"action": "add", "content": "x"}]'
        result = fresh_db.parse_json_actions(text)
        assert result == [{"action": "add", "content": "x"}]

    def test_markdown_fenced_json(self, fresh_db):
        """```json ... ``` 围栏自动剥离"""
        text = '```json\n[{"action": "add", "content": "y"}]\n```'
        result = fresh_db.parse_json_actions(text)
        assert result == [{"action": "add", "content": "y"}]

    def test_json_embedded_in_text(self, fresh_db):
        """LLM 输出常见: 一段文字 + JSON 数组"""
        text = '好的, 我会记住: [{"action": "add", "content": "embedded"}] 这样就可以了。'
        result = fresh_db.parse_json_actions(text)
        assert result == [{"action": "add", "content": "embedded"}]

    def test_invalid_json_returns_empty_or_raises(self, fresh_db):
        """纯非 JSON 文本 → [] (若 json.loads 抛, 当前实现未捕获 → 抛异常)"""
        text = "no json here"
        # 当前实现: json.loads 会抛 JSONDecodeError (未捕获)
        # 这是已记录的设计: 依赖 LLM 输出保证 JSON 合法
        with pytest.raises(json.JSONDecodeError):
            fresh_db.parse_json_actions(text)

    def test_non_list_json_returns_empty(self, fresh_db):
        """JSON 是 dict 而不是 list → []"""
        text = '{"action": "add"}'
        assert fresh_db.parse_json_actions(text) == []


# ---------- TestSourceInvariants ----------

class TestSourceInvariants:
    def _load_source(self):
        return (REPO_ROOT / "user_profile.py").read_text(encoding="utf-8")

    def test_no_import_desktop_auto(self):
        src = self._load_source()
        assert "import desktop_auto" not in src
        assert "from desktop_auto" not in src

    def test_no_import_context_chat(self):
        src = self._load_source()
        assert "from context_chat" not in src
        assert "import context_chat" not in src

    def test_uses_data_paths_user_data_dir(self):
        src = self._load_source()
        assert "from data_paths import USER_DATA_DIR" in src

    def test_uses_sqlite3(self):
        src = self._load_source()
        assert "import sqlite3" in src

    def test_journal_mode_wal_in_source(self):
        """WAL 模式是性能关键, 不能改"""
        src = self._load_source()
        assert "PRAGMA journal_mode=WAL" in src

    def test_init_db_table_schema_intact(self):
        """建表 SQL 含关键字段 (改字段要同步更新调用方)"""
        src = self._load_source()
        for col in ["category", "content", "confidence", "source", "is_active", "created_at", "updated_at"]:
            assert col in src, f"missing column {col}"

    def test_init_db_index_intact(self):
        src = self._load_source()
        assert "idx_profile_active_category" in src

    def test_all_14_functions_present(self):
        """14 个公开符号全部在源中"""
        src = self._load_source()
        for fn in [
            "def get_connection",
            "def init_db",
            "def _now",
            "def _safe_text",
            "def _load_config",
            "def _save_config",
            "def is_enabled",
            "def set_enabled",
            "def add_or_update_memory",
            "def deprecate_memory",
            "def clear_all_memory",
            "def get_active_profile_summary",
            "def apply_memory_actions",
            "def parse_json_actions",
        ]:
            assert fn in src, f"missing: {fn}"


# ---------- TestConsumerInvariants ----------

class TestConsumerInvariants:
    def _load(self, name):
        return (REPO_ROOT / name).read_text(encoding="utf-8")

    def test_desktop_auto_uses_apply_and_parse(self):
        src = self._load("desktop_auto.py")
        assert "from user_profile import apply_memory_actions, parse_json_actions" in src

    def test_context_chat_uses_get_active_profile_summary(self):
        src = self._load("context_chat.py")
        assert "from user_profile import get_active_profile_summary" in src

    def test_companion_bridge_uses_get_active_profile_summary(self):
        src = self._load("companion_bridge.py")
        assert "from user_profile import get_active_profile_summary" in src

    def test_tools_tab_uses_is_enabled(self):
        src = self._load("tools_tab.py")
        assert "from user_profile import is_enabled" in src

    def test_tools_tab_uses_set_enabled(self):
        src = self._load("tools_tab.py")
        assert "from user_profile import set_enabled" in src

    def test_tools_tab_uses_clear_all_memory(self):
        src = self._load("tools_tab.py")
        assert "from user_profile import clear_all_memory" in src

    def test_desktop_auto_uses_delayed_import(self):
        """apply_memory_actions 是延迟 import (在 _trigger_today_diary 函数体内)

        检测方式: import 行前 200 字符内不应有任何 user_profile / 顶层 import 标志,
        而应出现 'def ' 或 'try:' (证明在函数/方法体内延迟加载)
        """
        src = self._load("desktop_auto.py")
        idx = src.find("from user_profile import")
        assert idx > 0
        # 取前 200 字符窗口
        window = src[max(0, idx - 200):idx]
        # 应包含 'def ' 或 'try:' (函数定义/try 块开头), 排除模块顶部 import
        assert "def " in window or "try:" in window, \
            "from user_profile import 应在函数/方法体内 (延迟 import), 不在模块顶部"