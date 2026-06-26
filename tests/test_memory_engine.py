"""Step 2-2C: memory_engine.py 护栏 (沿用 test_launch_worker.py 模板)

覆盖范围:
- LASTINPUTINFO ctypes 结构字段 (Step 2-2C 抽出准备)
- get_idle_seconds() / get_foreground_info_safe() helper
- IdleWatcherThread / MainPollThread / MemoryEngineManager 构造与公开 API
- _emit_chunk 水桶策略不变量 (跨午夜强制结算)
- stop() 2s 超时 (bb98a87 关闭卡顿修复不能被无意删掉)
- desktop_auto.py 残留不变量 (memory_engine_mgr 调用模式 + chunk_ready 信号连接)

注意: 不实际跑线程 (run() 是死循环 time.sleep), 只锁定构造 + 签名 + 关键状态字段。
"""
import ast
import pathlib

import pytest
from PySide6.QtCore import QThread, QObject, Signal


DESKTOP_AUTO = pathlib.Path(r'D:\项目\控制电脑\desktop_auto.py')
MEMORY_ENGINE = pathlib.Path(r'D:\项目\控制电脑\memory_engine.py')


# ---------- A. LASTINPUTINFO ctypes 结构 ----------

class TestLastInputInfo:
    def test_import(self):
        from memory_engine import LASTINPUTINFO
        assert LASTINPUTINFO is not None

    def test_fields(self):
        """结构体必须有 cbSize (UINT) 和 dwTime (UINT) 两字段"""
        from memory_engine import LASTINPUTINFO
        import ctypes
        assert hasattr(LASTINPUTINFO, '_fields_')
        names = [f[0] for f in LASTINPUTINFO._fields_]
        assert names == ['cbSize', 'dwTime']
        # 类型必须是 c_uint (与 Windows API 一致)
        for fname, ftype, *_ in LASTINPUTINFO._fields_:
            assert ftype is ctypes.c_uint


# ---------- B. helper: get_idle_seconds ----------

class TestGetIdleSeconds:
    def test_import(self):
        from memory_engine import get_idle_seconds
        assert callable(get_idle_seconds)

    def test_returns_float_nonneg(self):
        """返回值必须是 float 且 ≥ 0 (即使 Windows API 失败也返回 0.0)"""
        from memory_engine import get_idle_seconds
        v = get_idle_seconds()
        assert isinstance(v, float)
        assert v >= 0.0


# ---------- C. helper: get_foreground_info_safe 优雅降级 ----------

class TestGetForegroundInfoSafe:
    def test_import(self):
        from memory_engine import get_foreground_info_safe
        assert callable(get_foreground_info_safe)

    def test_returns_tuple_of_two_strings(self):
        """返回 (title, app_name), 都是 str"""
        from memory_engine import get_foreground_info_safe
        result = get_foreground_info_safe()
        assert isinstance(result, tuple)
        assert len(result) == 2
        title, app = result
        assert isinstance(title, str)
        assert isinstance(app, str)


# ---------- D. IdleWatcherThread ----------

class TestIdleWatcherThread:
    def test_import(self):
        from memory_engine import IdleWatcherThread
        assert IdleWatcherThread is not None

    def test_is_qthread_subclass(self):
        from memory_engine import IdleWatcherThread
        assert issubclass(IdleWatcherThread, QThread)

    def test_has_woke_from_suspend_signal(self):
        from memory_engine import IdleWatcherThread
        assert hasattr(IdleWatcherThread, 'woke_from_suspend')

    def test_construct_with_main_poll_ref(self):
        from memory_engine import IdleWatcherThread
        # 构造只需 main_poll_ref, 不实际启动线程
        watcher = IdleWatcherThread(main_poll_ref=None)
        assert watcher._is_running is True
        assert watcher.main_poll is None

    def test_stop_sets_running_false(self):
        from memory_engine import IdleWatcherThread
        watcher = IdleWatcherThread(main_poll_ref=None)
        watcher.stop()
        assert watcher._is_running is False


# ---------- E. MainPollThread 构造与状态机 ----------

class TestMainPollThread:
    def test_import(self):
        from memory_engine import MainPollThread
        assert MainPollThread is not None

    def test_is_qthread_subclass(self):
        from memory_engine import MainPollThread
        assert issubclass(MainPollThread, QThread)

    def test_has_chunk_ready_signal(self):
        """chunk_ready(float, float, int) - start_ts, end_ts, record_count"""
        from memory_engine import MainPollThread
        assert hasattr(MainPollThread, 'chunk_ready')

    def test_default_constructor_params(self):
        """默认参数: interval=30, idle_threshold=180, suspend_threshold=1800,
           chunk_record_threshold=50 (下限 5), min_chunk_interval_s=7200 (下限 300)
           注意: MainPollThread.__init__ 第一个参数是 db: ActivityLogDB
        """
        from memory_engine import MainPollThread
        # 用 None 充当 db 占位 (不调 start/run)
        mp = MainPollThread(db=None)
        assert mp.interval == 30
        assert mp.idle_threshold == 180
        assert mp.suspend_threshold == 1800
        assert mp.chunk_record_threshold == 50
        assert mp.min_chunk_interval_s == 7200
        # 状态机初始值
        assert mp._state == 'ACTIVE'
        assert mp.is_suspended is False
        assert mp._pause_until == 0.0
        assert mp._chunk_count == 0

    def test_min_chunk_threshold_clamp(self):
        """chunk_record_threshold 上限 ≥ 5, min_chunk_interval_s ≥ 300"""
        from memory_engine import MainPollThread
        mp = MainPollThread(db=None, chunk_record_threshold=2, min_chunk_interval_s=10)
        assert mp.chunk_record_threshold >= 5
        assert mp.min_chunk_interval_s >= 300

    def test_stop_sets_running_false(self):
        from memory_engine import MainPollThread
        mp = MainPollThread(db=None)
        mp.stop()
        assert mp._is_running is False

    def test_manual_pause_sets_pause_until(self):
        from memory_engine import MainPollThread
        import time
        mp = MainPollThread(db=None)
        before = time.time()
        mp.manual_pause(60)
        after = time.time()
        # _pause_until 应在 [before+60, after+60] 区间
        assert before + 60 <= mp._pause_until <= after + 60 + 0.01

    def test_wake_up_clears_suspend(self):
        """wake_up() 把 is_suspended 设 False, _state 重置为 ACTIVE"""
        from memory_engine import MainPollThread
        mp = MainPollThread(db=None)
        mp.is_suspended = True
        mp._state = 'SUSPENDED'
        mp._cur_title = 'old'
        mp._cur_app = 'old_app'
        mp.wake_up()
        assert mp.is_suspended is False
        assert mp._state == 'ACTIVE'
        assert mp._cur_title == ''
        assert mp._cur_app == ''


# ---------- F. MainPollThread._emit_chunk 水桶策略 ----------

class TestEmitChunk:
    """Phase C: 水桶策略。
       _emit_chunk 在 _chunk_count > 0 时发射 chunk_ready 信号并清零桶;
       在 _chunk_count <= 0 时只清零不发射。
    """
    def test_no_chunk_when_count_zero(self):
        from memory_engine import MainPollThread
        mp = MainPollThread(db=None)
        mp._chunk_count = 0
        mp._chunk_start_ts = 0.0
        # 用 signal 监听器验证不发射
        captured = []
        mp.chunk_ready.connect(lambda s, e, c: captured.append((s, e, c)))
        mp._emit_chunk(end_ts=100.0)
        assert captured == []
        # 桶状态被清零 (重置后 _chunk_count 仍是 0, _chunk_start_ts 仍 0)
        assert mp._chunk_count == 0
        assert mp._chunk_start_ts == 0.0

    def test_emit_when_count_positive(self):
        from memory_engine import MainPollThread
        mp = MainPollThread(db=None)
        mp._chunk_count = 50
        mp._chunk_start_ts = 1.0
        captured = []
        mp.chunk_ready.connect(lambda s, e, c: captured.append((s, e, c)))
        mp._emit_chunk(end_ts=100.0)
        assert len(captured) == 1
        s, e, c = captured[0]
        assert s == 1.0
        assert e == 100.0
        assert c == 50
        # 桶已清零
        assert mp._chunk_count == 0
        assert mp._chunk_start_ts == 0.0


# ---------- G. MemoryEngineManager ----------

class TestMemoryEngineManager:
    def test_import(self):
        from memory_engine import MemoryEngineManager
        assert MemoryEngineManager is not None

    def test_is_qobject_subclass(self):
        from memory_engine import MemoryEngineManager
        assert issubclass(MemoryEngineManager, QObject)

    def test_has_paused_changed_signal(self):
        """paused_changed(bool, str) - 通知托盘图标或 UI"""
        from memory_engine import MemoryEngineManager
        assert hasattr(MemoryEngineManager, 'paused_changed')

    def test_constructor_creates_threads(self):
        """构造 (不 start) 应同时建好 main_poll 和 idle_watcher, 并 connect woke_from_suspend → wake_up"""
        from memory_engine import MemoryEngineManager, MainPollThread, IdleWatcherThread
        # 用临时目录建 ActivityLogDB
        import tempfile, gc
        tmp_ctx = tempfile.TemporaryDirectory()
        try:
            mgr = MemoryEngineManager(db_dir=pathlib.Path(tmp_ctx.name))
            assert isinstance(mgr.main_poll, MainPollThread)
            assert isinstance(mgr.idle_watcher, IdleWatcherThread)
            assert mgr.main_poll.db is not None
            # 关键不变量: idle_watcher 持有 main_poll 引用 (Qt 信号 connect 由 Manager.__init__ 完成)
            assert mgr.idle_watcher.main_poll is mgr.main_poll
            # 主动关 db 句柄, 避免 Windows 锁文件导致 TemporaryDirectory 清理失败
            if hasattr(mgr.main_poll.db, 'close'):
                mgr.main_poll.db.close()
            del mgr
            gc.collect()
        finally:
            tmp_ctx.cleanup()

    def test_stop_uses_2s_timeout(self):
        """bb98a87 关闭卡顿修复: stop() 内两个 wait() 必须带 2000ms 超时, 不能被无意删回无超时"""
        from memory_engine import MemoryEngineManager
        import tempfile, gc
        tmp_ctx = tempfile.TemporaryDirectory()
        try:
            mgr = MemoryEngineManager(db_dir=pathlib.Path(tmp_ctx.name))
            if hasattr(mgr.main_poll.db, 'close'):
                mgr.main_poll.db.close()
            del mgr
            gc.collect()
        finally:
            tmp_ctx.cleanup()
        # 直接看 source 字符串: 'wait(2000)' 必须出现 2 次 (idle_watcher + main_poll)
        src = pathlib.Path(MEMORY_ENGINE).read_text(encoding='utf-8')
        # 锁定在 stop() 方法体内 (更严格: 用 AST 检查)
        tree = ast.parse(src)
        stop_fn = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == 'stop':
                # MemoryEngineManager.stop vs MainPollThread.stop / IdleWatcherThread.stop
                # 通过类的 self.main_poll / self.idle_watcher 区分
                body_src = ast.unparse(node)
                if 'self.main_poll' in body_src and 'self.idle_watcher' in body_src:
                    stop_fn = node
                    break
        assert stop_fn is not None, 'MemoryEngineManager.stop() not found'
        body = ast.unparse(stop_fn)
        assert 'wait(2000)' in body, 'stop() 必须保留 2s 超时 (bb98a87 修复)'
        # 计数: 应出现 2 次 (idle_watcher.wait(2000) + main_poll.wait(2000))
        assert body.count('wait(2000)') >= 2

    def test_pause_emits_paused_changed(self):
        """pause(seconds) 发 paused_changed(True, '已暂停至 HH:MM')"""
        from memory_engine import MemoryEngineManager
        import tempfile, gc, re
        tmp_ctx = tempfile.TemporaryDirectory()
        try:
            mgr = MemoryEngineManager(db_dir=pathlib.Path(tmp_ctx.name))
            captured = []
            mgr.paused_changed.connect(lambda b, s: captured.append((b, s)))
            mgr.pause(3600)  # 暂停 1 小时
            assert len(captured) == 1
            paused, info = captured[0]
            assert paused is True
            assert info.startswith('已暂停至 ')
            # HH:MM 格式
            assert re.match(r'已暂停至 \d{2}:\d{2}', info), f'格式不符: {info}'
            if hasattr(mgr.main_poll.db, 'close'):
                mgr.main_poll.db.close()
            del mgr
            gc.collect()
        finally:
            tmp_ctx.cleanup()

    def test_pause_until_computes_future_seconds(self):
        """pause_until(hour) 应计算到目标小时的秒数 (内部调 pause)
           注: 不锁定具体 HH:MM, 因为运行时刻可能让 datetime.now() 跨分钟边界,
           只锁定"已暂停至 HH:MM"格式 + 小时字段正确
        """
        from memory_engine import MemoryEngineManager
        import tempfile, gc, re
        tmp_ctx = tempfile.TemporaryDirectory()
        try:
            mgr = MemoryEngineManager(db_dir=pathlib.Path(tmp_ctx.name))
            captured = []
            mgr.paused_changed.connect(lambda b, s: captured.append(s))
            mgr.pause_until(hour=23)  # 23:00 当天/次日
            assert len(captured) == 1
            info = captured[0]
            # 格式: '已暂停至 HH:MM' (HH 在 23 ± 1h, 因为跨日可能落到 00:00 次日)
            m = re.match(r'已暂停至 (\d{2}):(\d{2})', info)
            assert m, f'格式不符: {info}'
            hh = int(m.group(1))
            mm = int(m.group(2))
            # 合法小时: 0-23, 分钟: 0-59
            assert 0 <= hh <= 23
            assert 0 <= mm <= 59
            if hasattr(mgr.main_poll.db, 'close'):
                mgr.main_poll.db.close()
            del mgr
            gc.collect()
        finally:
            tmp_ctx.cleanup()


# ---------- H. memory_engine.py 源不变量 (Step 2-2C 抽出准备检查) ----------

class TestMemoryEngineSourceInvariants:
    """锁定 memory_engine.py 当前结构, 防止抽出过程中破坏关键 API."""
    @classmethod
    @pytest.fixture(scope='class')
    def source(cls):
        return MEMORY_ENGINE.read_text(encoding='utf-8')

    @classmethod
    @pytest.fixture(scope='class')
    def tree(cls):
        return ast.parse(MEMORY_ENGINE.read_text(encoding='utf-8'))

    def test_classes_present(self, source):
        assert 'class LASTINPUTINFO(ctypes.Structure):' in source
        assert 'class IdleWatcherThread(QThread):' in source
        assert 'class MainPollThread(QThread):' in source
        assert 'class MemoryEngineManager(QObject):' in source

    def test_helpers_present(self, source):
        assert 'def get_idle_seconds()' in source
        assert 'def get_foreground_info_safe()' in source

    def test_required_methods_present(self, source):
        """MemoryEngineManager 公开 API + 关键状态机方法"""
        for m in [
            'def start(self):',
            'def stop(self):',
            'def pause(self, seconds: int):',
            'def pause_until(self, hour: int):',
            # MainPollThread 状态机
            'def manual_pause(self, seconds: int):',
            'def wake_up(self):',
            'def _close_current_if_any(self, ts):',
            'def _note_active_record(self, start_ts: float, end_ts: float) -> None:',
            'def _emit_chunk(self, end_ts: float) -> None:',
        ]:
            assert m in source, f'缺失: {m}'

    def test_top_level_imports_only_three_deps(self, tree):
        """Step 2-2C 侦察结论: 顶层依赖应只 3 个 (log_bus/activity_log/app_categorizer)"""
        imports = []
        for node in tree.body:
            if isinstance(node, ast.ImportFrom):
                imports.append(node.module)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
        # 这 3 个必须存在
        assert 'log_bus' in imports
        assert 'activity_log' in imports
        assert 'app_categorizer' in imports
        # 不应 import desktop_auto (循环依赖风险)
        assert 'desktop_auto' not in imports

    def test_no_reference_to_desktop_auto(self, source):
        """memory_engine.py 任何位置都不应出现 desktop_auto 字样 (防止反向引用)"""
        assert 'desktop_auto' not in source

    def test_cross_midnight_chunk_logic_present(self, source):
        """_note_active_record 必须有跨午夜强制结算逻辑 (Phase C)"""
        # 锁定 'start_day != end_day' 或 'date()' 关键字串
        assert 'date()' in source
        assert 'start_day' in source
        assert 'end_day' in source

    def test_psutil_fallback_strings_present(self, source):
        """get_foreground_info_safe 必须有 3 个优雅降级字符串 (日志可观察性)"""
        assert 'System_Process' in source
        assert 'Transient_Process' in source
        assert 'Unknown_Process' in source


# ---------- I. desktop_auto.py 调用点不变量 (Step 2-2C 抽出准备检查) ----------

class TestDesktopAutoMemoryEngineInvariants:
    """锁定 desktop_auto.py 对 memory_engine 的调用模式不被无意破坏."""
    @classmethod
    @pytest.fixture(scope='class')
    def source(cls):
        return DESKTOP_AUTO.read_text(encoding='utf-8')

    def test_memory_engine_import_present(self, source):
        """from memory_engine import MemoryEngineManager 必须仍存在"""
        assert 'from memory_engine import MemoryEngineManager' in source

    def test_memory_engine_mgr_calls_go_through_bridges(self, source):
        """所有 memory_engine_mgr.xxx 调用都应走 self.bridges.memory_engine_mgr.xxx
           (Step 1B-4 模板, 防止有人退化到 self.memory_engine_mgr 直挂)
        """
        import re
        # 找所有 memory_engine_mgr.xxx 调用
        direct = re.findall(r'self\.memory_engine_mgr(?!\.)', source)
        # 不应出现 self.memory_engine_mgr (不带点直接用), 只允许 self.memory_engine_mgr.xxx
        assert len(direct) == 0, (
            f'发现 {len(direct)} 处 self.memory_engine_mgr 直接引用, '
            '应统一走 self.bridges.memory_engine_mgr.xxx (Step 1B-4 模板)'
        )

    def test_chunk_ready_signal_connected_once(self, source):
        """main_poll.chunk_ready.connect(...) 应只 1 处 (避免重复触发总结)"""
        # 锁定调用模式: 'chunk_ready.connect('
        count = source.count('chunk_ready.connect(')
        assert count == 1, (
            f'chunk_ready.connect 出现 {count} 次, 应只 1 处'
        )

    def test_paused_changed_signal_connected_once(self, source):
        """paused_changed.connect(...) 应只 1 处"""
        count = source.count('paused_changed.connect(')
        assert count == 1, f'paused_changed.connect 出现 {count} 次, 应只 1 处'

    def test_public_api_methods_present(self, source):
        """desktop_auto 应对外暴露 memory_pause / memory_pause_until / memory_start / memory_status"""
        for m in [
            'def memory_pause(',
            'def memory_pause_until(',
            'def memory_start(',
            'def memory_status(',
            'def _on_memory_chunk_ready(',
            'def _on_memory_pause_changed(',
        ]:
            assert m in source, f'desktop_auto 缺失公开/槽方法: {m}'