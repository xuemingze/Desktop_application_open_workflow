"""
Step 2-2D 护栏: daily_diary.py 公开 API 锁定

沿用 tests/test_memory_engine.py 模板(类内分组 + AST 不变量 + 源字符串断言):
- 9 个不变量类, ~43 项
- 纯加测试, 不动 daily_diary.py / desktop_auto.py / build.spec
- 跑完应 ~216 passed, 0 regression
"""
import gc
import re
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# 共用 helper: ActivityLogDB 没 close(), 需手动释放 _local.conn 避免 Windows 锁文件
# ---------------------------------------------------------------------------
def _close_db(db):
    """ActivityLogDB 用 threading.local 持 sqlite 连接, 必须手动关."""
    conn = getattr(db._local, "conn", None)
    if conn is not None:
        conn.close()
        del db._local.conn
    del db
    gc.collect()


def _make_db():
    """返回 (tmp_ctx, db) ; 测试结束需 tmp_ctx.cleanup()"""
    tmp_ctx = tempfile.TemporaryDirectory()
    db_path = Path(tmp_ctx.name) / "test.db"
    from activity_log import ActivityLogDB
    db = ActivityLogDB(db_path)
    return tmp_ctx, db


# ---------------------------------------------------------------------------
# 1. DiaryScheduler 类 (8 项) — QObject 调度器, 1 分钟对表一次
# ---------------------------------------------------------------------------
class TestDiaryScheduler:
    """DiaryScheduler: 1 分钟轮询, first_hour:30 触发, 每天最多 max_prompts 次"""

    def test_import_class(self):
        from daily_diary import DiaryScheduler
        assert DiaryScheduler is not None

    def test_subclass_of_qobject(self):
        from daily_diary import DiaryScheduler
        from PySide6.QtCore import QObject
        assert issubclass(DiaryScheduler, QObject)

    def test_signal_trigger_diary_prompt(self):
        from daily_diary import DiaryScheduler
        import inspect
        src = inspect.getsource(DiaryScheduler)
        assert "trigger_diary_prompt = Signal(str)" in src

    def test_init_defaults(self):
        from daily_diary import DiaryScheduler
        import inspect
        sig = inspect.signature(DiaryScheduler.__init__)
        params = list(sig.parameters.keys())
        assert "parent" in params
        assert "first_hour" in params
        assert "max_prompts" in params

    def test_init_default_first_hour_22(self):
        from daily_diary import DiaryScheduler
        import inspect
        sig = inspect.signature(DiaryScheduler.__init__)
        assert sig.parameters["first_hour"].default == 22

    def test_init_default_max_prompts_2(self):
        from daily_diary import DiaryScheduler
        import inspect
        sig = inspect.signature(DiaryScheduler.__init__)
        assert sig.parameters["max_prompts"].default == 2

    def test_check_trigger_method_exists(self):
        from daily_diary import DiaryScheduler
        assert hasattr(DiaryScheduler, "_check_trigger")
        assert callable(DiaryScheduler._check_trigger)

    def test_timer_60s(self):
        from daily_diary import DiaryScheduler
        import inspect
        src = inspect.getsource(DiaryScheduler)
        assert "60_000" in src or "60000" in src


# ---------------------------------------------------------------------------
# 2. extract_daily_summary (5 项) — SQLite 分类汇总 + Top 窗口
# ---------------------------------------------------------------------------
class TestExtractDailySummary:
    """extract_daily_summary: 返回 (category_stats, top_windows) 两段 Markdown"""

    def test_import(self):
        from daily_diary import extract_daily_summary
        assert callable(extract_daily_summary)

    def test_returns_tuple_of_two_strings(self):
        from daily_diary import extract_daily_summary
        tmp_ctx, db = _make_db()
        try:
            cat, top = extract_daily_summary(db, datetime(2020, 1, 1))
            assert isinstance(cat, str)
            assert isinstance(top, str)
        finally:
            _close_db(db)
            tmp_ctx.cleanup()

    def test_empty_db_returns_fallback_strings(self):
        from daily_diary import extract_daily_summary
        tmp_ctx, db = _make_db()
        try:
            cat, top = extract_daily_summary(db, datetime(2020, 1, 1))
            # 找不到表时应返回 "今日暂无..." fallback
            assert "暂无" in cat or "暂无" in top
        finally:
            _close_db(db)
            tmp_ctx.cleanup()

    def test_fallback_on_db_error(self):
        """当 db 是 mock 抛异常时, 应走 except 返回 fallback 而不是崩溃"""
        from daily_diary import extract_daily_summary

        class BrokenDB:
            def _get_conn(self):
                raise sqlite3.OperationalError("no such table")

            def _get_table_name(self, ts):
                return "activity_2020_01"

        cat, top = extract_daily_summary(BrokenDB(), datetime(2020, 1, 1))
        assert "暂无" in cat
        assert "暂无" in top

    def test_accepts_none_target_date(self):
        """target_date=None 时应走 datetime.now(), 不崩溃"""
        from daily_diary import extract_daily_summary
        tmp_ctx, db = _make_db()
        try:
            cat, top = extract_daily_summary(db, None)
            assert isinstance(cat, str)
            assert isinstance(top, str)
        finally:
            _close_db(db)
            tmp_ctx.cleanup()


# ---------------------------------------------------------------------------
# 3. extract_chunk_summary (4 项) — 工作切片聚合
# ---------------------------------------------------------------------------
class TestExtractChunkSummary:
    """extract_chunk_summary: 返回 (meta, grouped, fallback) 三元组"""

    def test_import(self):
        from daily_diary import extract_chunk_summary
        assert callable(extract_chunk_summary)

    def test_returns_three_strings(self):
        from daily_diary import extract_chunk_summary
        tmp_ctx, db = _make_db()
        try:
            meta, grouped, fallback = extract_chunk_summary(db, 0.0, 3600.0)
            assert isinstance(meta, str)
            assert isinstance(grouped, str)
            assert isinstance(fallback, str)
        finally:
            _close_db(db)
            tmp_ctx.cleanup()

    def test_fallback_on_exception(self):
        from daily_diary import extract_chunk_summary

        class BrokenDB:
            def _get_conn(self):
                raise sqlite3.DatabaseError("disk full")

            def _parse_activity_table_month(self, name):
                return None

        meta, grouped, fallback = extract_chunk_summary(BrokenDB(), 0.0, 1.0)
        assert "失败" in meta
        assert "暂无" in grouped
        assert "失败" in fallback

    def test_meta_contains_timestamp(self):
        from daily_diary import extract_chunk_summary
        tmp_ctx, db = _make_db()
        try:
            start = datetime(2020, 6, 15, 14, 30).timestamp()
            end = datetime(2020, 6, 15, 16, 0).timestamp()
            meta, _, _ = extract_chunk_summary(db, start, end)
            assert "2020-06-15" in meta
            assert "切片时间" in meta
        finally:
            _close_db(db)
            tmp_ctx.cleanup()


# ---------------------------------------------------------------------------
# 4. build_diary_prompt (4 项)
# ---------------------------------------------------------------------------
class TestBuildDiaryPrompt:
    """build_diary_prompt: 返回 (system_prompt, user_prompt)"""

    def test_import(self):
        from daily_diary import build_diary_prompt
        assert callable(build_diary_prompt)

    def test_returns_tuple(self):
        from daily_diary import build_diary_prompt
        tmp_ctx, db = _make_db()
        try:
            result = build_diary_prompt(db, datetime(2020, 1, 1))
            assert isinstance(result, tuple)
            assert len(result) == 2
        finally:
            _close_db(db)
            tmp_ctx.cleanup()

    def test_system_prompt_uses_template(self):
        from daily_diary import build_diary_prompt
        tmp_ctx, db = _make_db()
        try:
            sys_p, _ = build_diary_prompt(db, datetime(2020, 1, 1))
            # DIARY_PROMPT_TEMPLATE 关键短语必须出现
            assert "私人复盘助手" in sys_p
            assert "今日活动统计" in sys_p
            assert "Markdown" in sys_p
        finally:
            _close_db(db)
            tmp_ctx.cleanup()

    def test_user_prompt_contains_trigger(self):
        from daily_diary import build_diary_prompt
        tmp_ctx, db = _make_db()
        try:
            _, user_p = build_diary_prompt(db, datetime(2020, 1, 1))
            assert "Markdown" in user_p
            assert "日记" in user_p or "复盘" in user_p
        finally:
            _close_db(db)
            tmp_ctx.cleanup()


# ---------------------------------------------------------------------------
# 5. build_chunk_prompt (3 项)
# ---------------------------------------------------------------------------
class TestBuildChunkPrompt:
    """build_chunk_prompt: 返回 (system_prompt, user_prompt, fallback_markdown)"""

    def test_import(self):
        from daily_diary import build_chunk_prompt
        assert callable(build_chunk_prompt)

    def test_returns_three_tuple(self):
        from daily_diary import build_chunk_prompt
        tmp_ctx, db = _make_db()
        try:
            result = build_chunk_prompt(db, 0.0, 3600.0)
            assert isinstance(result, tuple)
            assert len(result) == 3
        finally:
            _close_db(db)
            tmp_ctx.cleanup()

    def test_system_uses_chunk_template(self):
        from daily_diary import build_chunk_prompt
        tmp_ctx, db = _make_db()
        try:
            sys_p, _, _ = build_chunk_prompt(db, 0.0, 3600.0)
            assert "私人工作记忆整理助手" in sys_p
            assert "切片元数据" in sys_p
            assert "本地聚合" in sys_p
        finally:
            _close_db(db)
            tmp_ctx.cleanup()


# ---------------------------------------------------------------------------
# 6. build_profile_memory_prompt (4 项) — 走 chat_memory, 依赖较重
# ---------------------------------------------------------------------------
class TestBuildProfileMemoryPrompt:
    """build_profile_memory_prompt: 返回 (sys, user) 或 None"""

    def test_import(self):
        from daily_diary import build_profile_memory_prompt
        assert callable(build_profile_memory_prompt)

    def test_returns_none_when_no_chat_memory(self):
        """当 chat_memory 不存在或 chat_digest 为空时, 应返回 None 不崩溃"""
        from daily_diary import build_profile_memory_prompt
        # 给个明显不存在 / 空数据的日期, 应走 None 分支
        result = build_profile_memory_prompt(datetime(1999, 1, 1))
        # 可能 None (无 chat) 或 (sys, user) tuple — 都应不抛异常
        assert result is None or (isinstance(result, tuple) and len(result) == 2)

    def test_accepts_none_date(self):
        from daily_diary import build_profile_memory_prompt
        result = build_profile_memory_prompt(None)
        assert result is None or (isinstance(result, tuple) and len(result) == 2)

    def test_template_str_present(self):
        """PROFILE_MEMORY_PROMPT_TEMPLATE 关键短语"""
        from daily_diary import PROFILE_MEMORY_PROMPT_TEMPLATE
        assert "长期记忆整理器" in PROFILE_MEMORY_PROMPT_TEMPLATE
        assert "JSON" in PROFILE_MEMORY_PROMPT_TEMPLATE
        assert "confidence" in PROFILE_MEMORY_PROMPT_TEMPLATE


# ---------------------------------------------------------------------------
# 7. _format_duration (5 项) — 时间格式 helper
# ---------------------------------------------------------------------------
class TestFormatDuration:
    """_format_duration(seconds) → 'Xh Ym' / 'Ym' / '0m'"""

    def test_import(self):
        from daily_diary import _format_duration
        assert callable(_format_duration)

    def test_zero_seconds(self):
        from daily_diary import _format_duration
        assert _format_duration(0) == "0m"

    def test_under_one_minute(self):
        from daily_diary import _format_duration
        assert _format_duration(30) == "0m"

    def test_minutes_only(self):
        from daily_diary import _format_duration
        assert _format_duration(150) == "2m"  # 2min30s

    def test_hours_and_minutes(self):
        from daily_diary import _format_duration
        assert _format_duration(3661) == "1h 1m"  # 1h1m1s

    def test_negative_clamps_to_zero(self):
        from daily_diary import _format_duration
        # 设计上 `max(0, ...)` 兜底
        assert _format_duration(-100) == "0m"


# ---------------------------------------------------------------------------
# 8. daily_diary.py 源不变量 (4 项) — 防重构无意中破坏关键路径
# ---------------------------------------------------------------------------
class TestDailyDiarySourceInvariants:
    """源代码不变量: 防抽模块 / 重命名 / 删除时回归"""

    def _load_source(self):
        p = Path(__file__).parent.parent / "daily_diary.py"
        return p.read_text(encoding="utf-8")

    def test_top_level_imports_intact(self):
        src = self._load_source()
        assert "import sqlite3" in src
        assert "from datetime import datetime" in src
        assert "from pathlib import Path" in src
        assert "from PySide6.QtCore import QObject, QTimer, Signal" in src
        assert "from log_bus import log_bus" in src
        assert "from activity_log import ActivityLogDB" in src

    def test_no_import_desktop_auto(self):
        """daily_diary.py 不应反向依赖 desktop_auto, 否则形成循环 import"""
        src = self._load_source()
        assert "import desktop_auto" not in src
        assert "from desktop_auto" not in src

    def test_prompt_templates_present(self):
        src = self._load_source()
        assert "DIARY_PROMPT_TEMPLATE" in src
        assert "CHUNK_PROMPT_TEMPLATE" in src
        assert "PROFILE_MEMORY_PROMPT_TEMPLATE" in src

    def test_max_prompts_logic_in_source(self):
        """DiaryScheduler._check_trigger 核心逻辑: 跨日重置 + max_prompts 截断"""
        src = self._load_source()
        assert "_prompts_today" in src
        assert "_last_date_str" in src
        assert "max_prompts" in src


# ---------------------------------------------------------------------------
# 9. desktop_auto.py 引用面不变量 (5 项) — 防修改时断引用
# ---------------------------------------------------------------------------
class TestDesktopAutoDailyDiaryInvariants:
    """desktop_auto.py 引用 daily_diary 的 5 个点必须保持"""

    def _load_desktop_auto(self):
        p = Path(__file__).parent.parent / "desktop_auto.py"
        return p.read_text(encoding="utf-8")

    def test_imports_diary_scheduler(self):
        src = self._load_desktop_auto()
        assert "from daily_diary import DiaryScheduler" in src

    def test_imports_build_chunk_prompt(self):
        src = self._load_desktop_auto()
        assert "from daily_diary import build_chunk_prompt" in src

    def test_imports_build_diary_prompt(self):
        src = self._load_desktop_auto()
        assert "from daily_diary import build_diary_prompt" in src

    def test_imports_build_profile_memory_prompt(self):
        src = self._load_desktop_auto()
        assert "from daily_diary import build_profile_memory_prompt" in src

    def test_diary_scheduler_constructed_via_bridges(self):
        """DiaryScheduler 必须挂在 bridges 上, 沿用 Step 1B-3 模板"""
        src = self._load_desktop_auto()
        assert "self.bridges._diary_scheduler = DiaryScheduler" in src
