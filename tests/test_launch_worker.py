"""Step 2 准备: LaunchWorker 行为锁定测试

为 Step 2-2A (LaunchWorker 抽到独立 launch_worker.py) 铺路,先锁定当前行为。

覆盖范围:
- ShortcutInfo 数据类字段
- LaunchWorker 构造与 _parse_args 静态方法
- 信号签名
- cancel() 状态
- _DiaryWorker / _ChunkWorker 内部类存在性
- desktop_auto.py 不变量 (helper 函数/方法存在)

注意: 测试不实际启动子进程 (LaunchWorker.run() 调用 Popen),
只测试构造和签名层级。
"""
import pytest
from PySide6.QtCore import QThread, Signal


# ---------- A. ShortcutInfo 数据类 ----------

class TestShortcutInfo:
    def test_import(self):
        from desktop_auto import ShortcutInfo
        assert ShortcutInfo is not None

    def test_minimal_construction(self):
        """3 个必填字段 + 默认值"""
        from desktop_auto import ShortcutInfo
        sc = ShortcutInfo(name='app', target='C:\\app.exe', lnk_path='C:\\app.lnk')
        assert sc.name == 'app'
        assert sc.target == 'C:\\app.exe'
        assert sc.lnk_path == 'C:\\app.lnk'
        assert sc.work_dir == ''
        assert sc.icon_samples == []
        assert sc.launch_mode == ''
        assert sc._coord_x == 0
        assert sc._coord_y == 0
        assert sc._click_type == 'left_double'

    def test_full_construction(self):
        """所有字段可设"""
        from desktop_auto import ShortcutInfo
        sc = ShortcutInfo(
            name='app', target='C:\\app.exe', lnk_path='C:\\app.lnk',
            work_dir='C:\\app',
            icon_samples=['s1.png', 's2.png'],
            launch_mode='direct',
            _coord_x=100, _coord_y=200, _click_type='right_single',
        )
        assert sc.work_dir == 'C:\\app'
        assert sc.icon_samples == ['s1.png', 's2.png']
        assert sc.launch_mode == 'direct'
        assert sc._coord_x == 100
        assert sc._coord_y == 200
        assert sc._click_type == 'right_single'

    def test_is_dataclass(self):
        from dataclasses import is_dataclass
        from desktop_auto import ShortcutInfo
        assert is_dataclass(ShortcutInfo)


# ---------- B. LaunchWorker 构造 ----------

class TestLaunchWorkerConstruction:
    def test_import(self):
        from desktop_auto import LaunchWorker
        assert LaunchWorker is not None

    def test_is_qthread_subclass(self):
        from desktop_auto import LaunchWorker
        assert issubclass(LaunchWorker, QThread)

    def test_has_required_signals(self):
        """log_signal 和 finished_signal 必须存在且是 Qt Signal"""
        from desktop_auto import LaunchWorker
        assert hasattr(LaunchWorker, 'log_signal')
        assert hasattr(LaunchWorker, 'finished_signal')

    def test_construct_direct_mode(self):
        """4 个必填参数 + 默认 extra_args + coord"""
        from desktop_auto import LaunchWorker, ShortcutInfo
        sc = ShortcutInfo('app', 'C:\\app.exe', 'C:\\app.lnk')
        w = LaunchWorker(sc, mode='direct', do_notepad=False)
        assert w.info is sc
        assert w.mode == 'direct'
        assert w.do_notepad is False
        assert w.extra_args == []
        assert w.coord == {}

    def test_construct_with_extra_args(self):
        """extra_args 字符串被 _parse_args 解析"""
        from desktop_auto import LaunchWorker, ShortcutInfo
        sc = ShortcutInfo('app', 'C:\\app.exe', 'C:\\app.lnk')
        w = LaunchWorker(sc, mode='direct', do_notepad=False,
                         extra_args='--foo "C:\\Program Files\\bar.exe"')
        assert w.extra_args == ['--foo', 'C:\\Program Files\\bar.exe']

    def test_construct_with_coord(self):
        """coord dict 参数被保留"""
        from desktop_auto import LaunchWorker, ShortcutInfo
        sc = ShortcutInfo('app', 'C:\\app.exe', 'C:\\app.lnk')
        coord = {'x': 100, 'y': 200, 'click_type': 'left_double'}
        w = LaunchWorker(sc, mode='coord', do_notepad=False, coord=coord)
        assert w.coord == coord

    def test_cancel_flag_initial_false(self):
        """_cancel 默认 False"""
        from desktop_auto import LaunchWorker, ShortcutInfo
        sc = ShortcutInfo('app', 'C:\\app.exe', 'C:\\app.lnk')
        w = LaunchWorker(sc, mode='direct', do_notepad=False)
        assert w._cancel is False


# ---------- C. _parse_args 静态方法 ----------

class TestParseArgs:
    def test_empty_string(self):
        from desktop_auto import LaunchWorker
        assert LaunchWorker._parse_args('') == []
        assert LaunchWorker._parse_args('   ') == []

    def test_simple_split(self):
        from desktop_auto import LaunchWorker
        assert LaunchWorker._parse_args('--foo --bar') == ['--foo', '--bar']

    def test_quoted_string_kept_together(self):
        from desktop_auto import LaunchWorker
        assert LaunchWorker._parse_args('--path "C:\\Program Files\\app.exe"') == \
            ['--path', 'C:\\Program Files\\app.exe']

    def test_mixed_quoted_and_unquoted(self):
        from desktop_auto import LaunchWorker
        assert LaunchWorker._parse_args('-a 1 -b "two words" -c 3') == \
            ['-a', '1', '-b', 'two words', '-c', '3']


# ---------- D. cancel() 方法 ----------

class TestCancel:
    def test_cancel_sets_flag(self):
        from desktop_auto import LaunchWorker, ShortcutInfo
        sc = ShortcutInfo('app', 'C:\\app.exe', 'C:\\app.lnk')
        w = LaunchWorker(sc, mode='direct', do_notepad=False)
        w.cancel()
        assert w._cancel is True


# ---------- E. 内部 worker 类 (_DiaryWorker / _ChunkWorker) ----------

class TestInternalWorkers:
    def test_diary_worker_exists(self):
        """MainWindow._generate_diary_async 内的 _DiaryWorker 内部类"""
        # 用 AST 检测, 因为内部类需要 MainWindow 实例才能访问
        import ast, pathlib
        tree = ast.parse(pathlib.Path(r'D:\项目\控制电脑\desktop_auto.py').read_text(encoding='utf-8'))
        # 找类名 _DiaryWorker 的所有定义
        diary_found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == '_DiaryWorker':
                diary_found = True
                # 必须继承 QThread
                for base in node.bases:
                    if isinstance(base, ast.Name) and base.id == 'QThread':
                        break
                else:
                    pytest.fail('_DiaryWorker must inherit QThread')
                break
        assert diary_found, '_DiaryWorker not found'

    def test_chunk_worker_exists(self):
        import ast, pathlib
        tree = ast.parse(pathlib.Path(r'D:\项目\控制电脑\desktop_auto.py').read_text(encoding='utf-8'))
        chunk_found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == '_ChunkWorker':
                chunk_found = True
                for base in node.bases:
                    if isinstance(base, ast.Name) and base.id == 'QThread':
                        break
                else:
                    pytest.fail('_ChunkWorker must inherit QThread')
                break
        assert chunk_found, '_ChunkWorker not found'


# ---------- F. desktop_auto.py 不变量 ----------

class TestDesktopAutoInvariants:
    @classmethod
    @pytest.fixture(scope='class')
    def source(cls):
        import pathlib
        return pathlib.Path(r'D:\项目\控制电脑\desktop_auto.py').read_text(encoding='utf-8')

    def test_launch_worker_class_present(self, source):
        assert 'class LaunchWorker(QThread):' in source

    def test_shortcut_info_class_present(self, source):
        assert 'class ShortcutInfo:' in source

    def test_required_methods_present(self, source):
        """LaunchWorker 必须有 5 种启动模式方法 + 等待窗口方法 + 保存坐标方法"""
        needed = [
            'def _launch_direct(',
            'def _launch_shell(',
            'def _launch_by_image(',
            'def _launch_desktop_click(',
            'def _wait_window_ready(',
            'def _save_match_coord(',
            'def cancel(',
        ]
        for n in needed:
            assert n in source, f'缺失方法: {n}'

    def test_helper_functions_present(self, source):
        """LaunchWorker 依赖的 2 个 helper"""
        assert 'def _get_pyautogui():' in source
        assert 'def _resolve_sample_path(' in source

    def test_supported_modes(self, source):
        """run() 中应支持 4 种启动模式 (direct/shell/image/desktop)"""
        # 注: coord 不是独立 mode, 由 image 模式通过 self.coord 参数处理
        # 检查 mode == "direct" / "shell" / "image" / "desktop" 都被识别
        for mode in ['"direct"', '"shell"', '"image"', '"desktop"']:
            assert f'self.mode == {mode}' in source, f'缺失模式识别: {mode}'

    def test_unknown_mode_raises(self, source):
        """未识别的 mode 应抛 ValueError (在 run() 的 else 分支)"""
        # else 分支 raise ValueError(f"未知模式: {self.mode}")
        assert '未知模式' in source

    def test_coord_not_separate_mode(self, source):
        """coord 不是独立 mode (由 image 模式 + self.coord 处理)"""
        # 不应有 self.mode == "coord" 这种判断
        assert 'self.mode == "coord"' not in source