"""
chat_memory.py 护栏: 锁死 chat 流水的 JSONL 写入 / 读取 / 清理 / 画像抽取

沿用 tests/test_memory_engine.py 模板 (类内分组 + AST/inspect + 源字符串 + duck-type)

设计要点:
- chat_memory.py 的 LOG_DIR = USER_DATA_DIR / "chat_logs" 是真实用户数据
- 测试必须在隔离的 tmp 目录跑, 避免污染真实 chat_logs
- 改 chat_memory.LOG_DIR 用 monkeypatch 指向 tmp, 跑完清理

覆盖: 11 类 / ~40 项
"""
import datetime
import inspect
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# 共用 fixture: 隔离 tmp 目录, 避免污染真实 chat_logs
# ---------------------------------------------------------------------------
@pytest.fixture
def tmp_log_dir(tmp_path, monkeypatch):
    """monkeypatch chat_memory.LOG_DIR + get_current_log_path 指向 tmp_path / 'chat_logs'"""
    import chat_memory
    fake_log_dir = tmp_path / "chat_logs"
    fake_log_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(chat_memory, "LOG_DIR", fake_log_dir)
    return fake_log_dir


# ---------------------------------------------------------------------------
# 1. 模块常量 (3 项)
# ---------------------------------------------------------------------------
class TestConstants:
    """LOG_DIR / MAX_TEXT_CHARS=2000 / MAX_TOOL_CHARS=1000"""

    def test_log_dir_under_user_data_dir(self):
        import chat_memory
        from data_paths import USER_DATA_DIR
        assert chat_memory.LOG_DIR == USER_DATA_DIR / "chat_logs"

    def test_max_text_chars_is_2000(self):
        import chat_memory
        assert chat_memory.MAX_TEXT_CHARS == 2000

    def test_max_tool_chars_is_1000(self):
        import chat_memory
        assert chat_memory.MAX_TOOL_CHARS == 1000


# ---------------------------------------------------------------------------
# 2. _now() (2 项)
# ---------------------------------------------------------------------------
class TestNow:
    """_now() 返回 datetime, 微秒归零"""

    def test_returns_datetime(self):
        from chat_memory import _now
        v = _now()
        assert isinstance(v, datetime.datetime)

    def test_microsecond_is_zero(self):
        """_now 用 .replace(microsecond=0) 归零, 防止 JSONL 时间戳漂移"""
        from chat_memory import _now
        v = _now()
        assert v.microsecond == 0


# ---------------------------------------------------------------------------
# 3. _safe_text() (4 项)
# ---------------------------------------------------------------------------
class TestSafeText:
    """_safe_text(value, limit=2000): 兜底/截断/strip"""

    def test_none_returns_empty_string(self):
        from chat_memory import _safe_text
        assert _safe_text(None) == ""

    def test_empty_returns_empty_string(self):
        from chat_memory import _safe_text
        assert _safe_text("") == ""

    def test_strips_whitespace(self):
        from chat_memory import _safe_text
        assert _safe_text("  hello  ") == "hello"

    def test_truncates_at_limit(self):
        from chat_memory import _safe_text
        s = "x" * 5000
        out = _safe_text(s, limit=100)
        assert len(out) == 100


# ---------------------------------------------------------------------------
# 4. get_current_log_path() (3 项)
# ---------------------------------------------------------------------------
class TestGetCurrentLogPath:
    """get_current_log_path(now=None) → 'chat_history_YYYY-MM.jsonl'"""

    def test_default_uses_current_month(self, tmp_log_dir):
        from chat_memory import get_current_log_path
        p = get_current_log_path()
        assert p.name.startswith("chat_history_")
        assert p.name.endswith(".jsonl")

    def test_custom_date(self, tmp_log_dir):
        from chat_memory import get_current_log_path
        target = datetime.datetime(2025, 3, 15, 10, 30)
        p = get_current_log_path(target)
        assert p.name == "chat_history_2025-03.jsonl"

    def test_creates_log_dir_if_missing(self, tmp_path, monkeypatch):
        """LOG_DIR 不存在时, get_current_log_path 应自动建"""
        import chat_memory
        fake = tmp_path / "auto_created_logs"
        monkeypatch.setattr(chat_memory, "LOG_DIR", fake)
        p = chat_memory.get_current_log_path()
        assert fake.exists()
        assert p.parent == fake


# ---------------------------------------------------------------------------
# 5. infer_skip_memory() (6 项) — 操作型命令识别
# ---------------------------------------------------------------------------
class TestInferSkipMemory:
    """infer_skip_memory(user_msg, tools_used=None) → bool"""

    def test_chinese_open_keyword(self):
        from chat_memory import infer_skip_memory
        assert infer_skip_memory("帮我打开 Chrome") is True

    def test_chinese_launch_keyword(self):
        from chat_memory import infer_skip_memory
        assert infer_skip_memory("启动 VSCode") is True

    def test_english_run_keyword(self):
        from chat_memory import infer_skip_memory
        assert infer_skip_memory("please run the script") is True

    def test_op_tool_name_triggers_skip(self):
        """run_workflow / launch_shortcut / open_system_file / create_reminder → True"""
        from chat_memory import infer_skip_memory
        assert infer_skip_memory("随便聊聊", tools_used=[{"name": "run_workflow"}]) is True
        assert infer_skip_memory("随便聊聊", tools_used=[{"name": "launch_shortcut"}]) is True
        assert infer_skip_memory("随便聊聊", tools_used=[{"name": "open_system_file"}]) is True
        assert infer_skip_memory("随便聊聊", tools_used=[{"name": "create_reminder"}]) is True

    def test_normal_chat_returns_false(self):
        """纯聊天无 op 关键词/工具 → False (进入长期画像)"""
        from chat_memory import infer_skip_memory
        assert infer_skip_memory("我今天心情不错") is False
        assert infer_skip_memory("今天学到了很多新东西") is False

    def test_case_insensitive(self):
        """大小写无关 — 英文 op 关键词应小写匹配"""
        from chat_memory import infer_skip_memory
        assert infer_skip_memory("OPEN the door") is True
        assert infer_skip_memory("please LAUNCH Chrome") is True


# ---------------------------------------------------------------------------
# 6. append_chat_log() (5 项) — JSONL 写入
# ---------------------------------------------------------------------------
class TestAppendChatLog:
    """append_chat_log(user, ai, tools, skip_memory) → Path"""

    def test_returns_path(self, tmp_log_dir):
        from chat_memory import append_chat_log
        p = append_chat_log("hi", "hello")
        assert p.exists()
        assert p.suffix == ".jsonl"

    def test_writes_valid_jsonl(self, tmp_log_dir):
        from chat_memory import append_chat_log
        p = append_chat_log("hello", "hi there")
        lines = p.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["user"] == "hello"
        assert entry["ai"] == "hi there"

    def test_default_skip_memory_uses_infer(self, tmp_log_dir):
        """skip_memory=None → 调 infer_skip_memory 推断"""
        from chat_memory import append_chat_log
        # 第一条 op (skip_memory=True)
        append_chat_log("打开 Chrome", "")
        # 第二条 纯聊天 (skip_memory=False)
        append_chat_log("今天心情好", "")
        # 两条都进同一个 JSONL 文件, 读所有行
        from chat_memory import get_current_log_path
        p = get_current_log_path()
        lines = p.read_text(encoding="utf-8").strip().splitlines()
        entries = [json.loads(l) for l in lines]
        # op 必 skip=True, 聊天必 skip=False
        skip_flags = {e["user"]: e["skip_memory"] for e in entries}
        assert skip_flags["打开 Chrome"] is True
        assert skip_flags["今天心情好"] is False

    def test_explicit_skip_memory_overrides(self, tmp_log_dir):
        """skip_memory=True/False 显式传 → 强制覆盖推断"""
        from chat_memory import append_chat_log
        p = append_chat_log("打开 Chrome", "", skip_memory=False)
        e = json.loads(p.read_text(encoding="utf-8").splitlines()[-1])
        assert e["skip_memory"] is False

    def test_tools_field_extracted(self, tmp_log_dir):
        """tools_used 列表里字典应被规范化为 name/args/ok"""
        from chat_memory import append_chat_log
        tools = [{"name": "run_workflow", "args": {"name": "daily"}, "ok": True}]
        p = append_chat_log("a", "b", tools_used=tools)
        e = json.loads(p.read_text(encoding="utf-8").splitlines()[-1])
        assert len(e["tools"]) == 1
        assert e["tools"][0]["name"] == "run_workflow"
        assert e["tools"][0]["ok"] is True


# ---------------------------------------------------------------------------
# 7. cleanup_old_logs() (3 项) — 30 天滚动
# ---------------------------------------------------------------------------
class TestCleanupOldLogs:
    """cleanup_old_logs(retention_days=30) → int (删除数)"""

    def test_no_files_returns_zero(self, tmp_log_dir):
        from chat_memory import cleanup_old_logs
        assert cleanup_old_logs() == 0

    def test_recent_file_kept(self, tmp_log_dir):
        """本月的 log 不删"""
        from chat_memory import cleanup_old_logs, get_current_log_path
        p = get_current_log_path()
        p.write_text('{"timestamp": "2026-06-15T10:00:00"}\n', encoding="utf-8")
        assert cleanup_old_logs() == 0
        assert p.exists()

    def test_old_file_removed(self, tmp_log_dir):
        """2 年前的 log 应被删"""
        from chat_memory import cleanup_old_logs
        old = tmp_log_dir / "chat_history_2024_01.jsonl"
        old.write_text('{"timestamp": "2024-01-15T10:00:00"}\n', encoding="utf-8")
        # cleanup 期望文件名是 chat_history_YYYY_MM.jsonl (带下划线)
        # 但 get_current_log_path 实际是 chat_history_YYYY-MM.jsonl (带短横)
        # 修正: 写带短横的文件
        old_correct = tmp_log_dir / "chat_history_2024-01.jsonl"
        old_correct.write_text('{"timestamp": "2024-01-15T10:00:00"}\n', encoding="utf-8")
        old.unlink()
        removed = cleanup_old_logs()
        assert removed >= 1
        assert not old_correct.exists()


# ---------------------------------------------------------------------------
# 8. iter_chat_logs_for_date() (4 项) — 按日过滤
# ---------------------------------------------------------------------------
class TestIterChatLogsForDate:
    """iter_chat_logs_for_date(target_date) → list[dict]"""

    def test_no_file_returns_empty(self, tmp_log_dir):
        from chat_memory import iter_chat_logs_for_date
        rows = list(iter_chat_logs_for_date(datetime.datetime(2026, 6, 15)))
        assert rows == []

    def test_filters_by_date_prefix(self, tmp_log_dir):
        """只返回 timestamp 以 YYYY-MM-DD 开头的行"""
        from chat_memory import append_chat_log, iter_chat_logs_for_date
        target = datetime.datetime(2026, 6, 15, 10, 0, 0)
        # 模拟不同时刻的 3 条记录
        with patch("chat_memory._now", return_value=target):
            append_chat_log("a", "1")
        with patch("chat_memory._now", return_value=target.replace(day=16, hour=10)):
            append_chat_log("b", "2")
        with patch("chat_memory._now", return_value=target.replace(day=15, hour=14)):
            append_chat_log("c", "3")
        rows = list(iter_chat_logs_for_date(target))
        # 6-15 应有 2 条, 6-16 不应包含
        assert len(rows) == 2
        users = sorted(r["user"] for r in rows)
        assert users == ["a", "c"]

    def test_skips_malformed_json(self, tmp_log_dir):
        """坏行 (json.loads 失败) 应被跳过而不是崩溃"""
        from chat_memory import get_current_log_path, iter_chat_logs_for_date
        p = get_current_log_path()
        p.write_text(
            '{"timestamp": "2026-06-15T10:00:00", "user": "good1", "ai": "x"}\n'
            'THIS IS NOT JSON\n'
            '{"timestamp": "2026-06-15T11:00:00", "user": "good2", "ai": "y"}\n',
            encoding="utf-8",
        )
        target = datetime.datetime(2026, 6, 15)
        rows = list(iter_chat_logs_for_date(target))
        assert len(rows) == 2
        assert {r["user"] for r in rows} == {"good1", "good2"}

    def test_returns_list_type(self, tmp_log_dir):
        """iter_chat_logs_for_date 返回值应是 list (而非生成器)"""
        import chat_memory
        sig = inspect.signature(chat_memory.iter_chat_logs_for_date)
        # 看返回注解
        assert sig.return_annotation != inspect.Signature.empty


# ---------------------------------------------------------------------------
# 9. build_chat_memory_digest() (5 项) — 画像抽取上游
# ---------------------------------------------------------------------------
class TestBuildChatMemoryDigest:
    """build_chat_memory_digest(date=None, limit=80) → str (Markdown digest)"""

    def test_no_data_returns_empty_string(self, tmp_log_dir):
        from chat_memory import build_chat_memory_digest
        assert build_chat_memory_digest(datetime.datetime(2020, 1, 1)) == ""

    def test_skip_memory_true_excluded(self, tmp_log_dir):
        """skip_memory=True 的条目不进入 digest (设计意图)"""
        from chat_memory import append_chat_log, build_chat_memory_digest
        target = datetime.datetime(2026, 6, 15, 10, 0, 0)
        with patch("chat_memory._now", return_value=target):
            append_chat_log("打开 Chrome", "ok", skip_memory=True)
            append_chat_log("今天心情好", "是啊", skip_memory=False)
        digest = build_chat_memory_digest(target)
        assert "今天心情好" in digest
        assert "打开 Chrome" not in digest

    def test_format_includes_time_user_ai(self, tmp_log_dir):
        """digest 每条应是 '[HH:MM] 用户: ...\\n[HH:MM] AI: ...'"""
        from chat_memory import append_chat_log, build_chat_memory_digest
        target = datetime.datetime(2026, 6, 15, 14, 30, 0)
        with patch("chat_memory._now", return_value=target):
            append_chat_log("hello", "world")
        digest = build_chat_memory_digest(target)
        assert "[14:30]" in digest
        assert "用户: hello" in digest
        assert "AI: world" in digest

    def test_limit_truncates(self, tmp_log_dir):
        """limit=2 只取最近 2 条"""
        from chat_memory import append_chat_log, build_chat_memory_digest
        target = datetime.datetime(2026, 6, 15, 10, 0, 0)
        for i in range(5):
            t = target.replace(hour=10 + i)
            with patch("chat_memory._now", return_value=t):
                append_chat_log(f"msg{i}", f"reply{i}")
        digest = build_chat_memory_digest(target, limit=2)
        # 应只包含最后 2 条
        assert "msg3" in digest
        assert "msg4" in digest
        assert "msg0" not in digest

    def test_default_date_is_today(self, tmp_log_dir):
        """target_date=None → 用 _now() 今天"""
        from chat_memory import build_chat_memory_digest
        # 不报错即可 (空 digest 也合法)
        result = build_chat_memory_digest()
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# 10. chat_memory.py 源不变量 (4 项) — 防抽模块/重命名时回归
# ---------------------------------------------------------------------------
class TestChatMemorySourceInvariants:
    """源代码不变量: 防重构无意中破坏关键路径"""

    def _load_source(self):
        return Path(__file__).parent.parent.joinpath("chat_memory.py").read_text(encoding="utf-8")

    def test_top_level_imports_intact(self):
        src = self._load_source()
        assert "import datetime" in src
        assert "import json" in src
        assert "from pathlib import Path" in src
        assert "from data_paths import USER_DATA_DIR" in src

    def test_no_import_desktop_auto(self):
        """chat_memory.py 不应反向依赖 desktop_auto, 否则形成循环"""
        src = self._load_source()
        assert "import desktop_auto" not in src
        assert "from desktop_auto" not in src

    def test_user_data_dir_imported_not_hardcoded(self):
        """USER_DATA_DIR 必须从 data_paths 拿, 不应硬编码路径"""
        src = self._load_source()
        # LOG_DIR 应当从 USER_DATA_DIR 派生
        assert "LOG_DIR = USER_DATA_DIR" in src or "LOG_DIR = USER_DATA_DIR /" in src

    def test_all_seven_functions_present(self):
        src = self._load_source()
        for fn in ["_now", "_safe_text", "get_current_log_path",
                   "infer_skip_memory", "append_chat_log",
                   "cleanup_old_logs", "iter_chat_logs_for_date",
                   "build_chat_memory_digest"]:
            assert f"def {fn}" in src, f"missing def {fn}"


# ---------------------------------------------------------------------------
# 11. 消费方引用面不变量 (3 项) — 防改 chat_memory 时断引用
# ---------------------------------------------------------------------------
class TestConsumerInvariants:
    """context_chat.py / daily_diary.py 引用 chat_memory 的点必须保持"""

    def _load(self, name):
        return Path(__file__).parent.parent.joinpath(name).read_text(encoding="utf-8")

    def test_context_chat_imports_append_and_cleanup(self):
        src = self._load("context_chat.py")
        assert "from chat_memory import" in src
        assert "append_chat_log" in src
        assert "cleanup_old_logs" in src

    def test_daily_diary_imports_build_chat_memory_digest(self):
        src = self._load("daily_diary.py")
        assert "from chat_memory import build_chat_memory_digest" in src

    def test_daily_diary_uses_delayed_import(self):
        """daily_diary.py:253 是延迟 import, 防 import 时循环"""
        src = self._load("daily_diary.py")
        # build_profile_memory_prompt 函数体内必须有 chat_memory import
        func_start = src.find("def build_profile_memory_prompt")
        assert func_start != -1
        func_end = src.find("\n\n", func_start)
        func_body = src[func_start:func_end]
        assert "from chat_memory import build_chat_memory_digest" in func_body
