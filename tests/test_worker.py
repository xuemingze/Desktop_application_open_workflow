"""Step 1C Phase 3: self.worker 拆分测试基准"""
import pytest
from PySide6.QtCore import QObject

from app_containers import AppContainers


class TestAppContainersWorker:
    def test_worker_default_none(self):
        """AppContainers.worker 默认 None (生命周期由 MainWindow 触发)"""
        c = AppContainers(QObject())
        assert c.worker is None

    def test_worker_assignable(self):
        """worker 字段可赋值"""
        c = AppContainers(QObject())
        sentinel = object()
        c.worker = sentinel
        assert c.worker is sentinel


class TestDesktopAutoWorkerInvariants:
    @classmethod
    @pytest.fixture(scope='class')
    def source(cls):
        import pathlib
        return pathlib.Path(r'D:\项目\控制电脑\desktop_auto.py').read_text(encoding='utf-8')

    def test_no_direct_self_worker_declaration(self, source):
        """不应再有 self.worker: Optional[LaunchWorker] = None 声明"""
        assert 'self.worker: Optional[LaunchWorker] = None' not in source

    def test_no_direct_self_worker_assignment_in_run(self, source):
        """run_action 中 self.worker = LaunchWorker(...) 应改为 self.containers.worker = LaunchWorker(...)"""
        # 检查不应再有 self.worker = LaunchWorker(
        assert 'self.worker = LaunchWorker(' not in source

    def test_no_direct_self_worker_in_stop_action(self, source):
        """stop_action 中不应再有 self.worker.cancel/quit/wait"""
        # 改为 self.containers.worker.xxx
        n_cancel = source.count('self.worker.cancel()')
        n_quit = source.count('self.worker.quit()')
        n_wait = source.count('self.worker.wait(')
        assert n_cancel == 0, f'self.worker.cancel() 残留 {n_cancel} 处'
        assert n_quit == 0, f'self.worker.quit() 残留 {n_quit} 处'
        assert n_wait == 0, f'self.worker.wait() 残留 {n_wait} 处'

    def test_no_direct_self_worker_isRunning_check(self, source):
        """2 处 isRunning 检查应改为 self.containers.worker.isRunning()"""
        n = source.count('self.worker and self.worker.isRunning()')
        assert n == 0, f'self.worker.isRunning() 还有 {n} 处'

    def test_containers_worker_usage_present(self, source):
        """5 处 self.worker 应改为 self.containers.worker (含 1 处 None 清空)"""
        n = source.count('self.containers.worker')
        # 至少 5 处: 1 创建 + 2 isRunning + cancel/quit/wait + 1 None 清空
        assert n >= 5, f'self.containers.worker 引用过少: {n}'

    def test_worker_property_forwarding(self, source):
        """MainWindow 应有 @property worker 转发 (API 兼容)"""
        # @property\n    def worker(self):\n        return self.containers.worker
        assert '@property' in source
        assert 'def worker(self):' in source


class TestLaunchWorkerAPIUnchanged:
    """LaunchWorker 类本身不变 (Phase 3 不动它)"""

    def test_class_still_exists(self):
        from desktop_auto import LaunchWorker
        assert LaunchWorker is not None

    def test_has_required_signals_and_methods(self):
        from desktop_auto import LaunchWorker
        from PySide6.QtCore import QThread
        assert issubclass(LaunchWorker, QThread)
        assert hasattr(LaunchWorker, 'log_signal')
        assert hasattr(LaunchWorker, 'finished_signal')
        assert hasattr(LaunchWorker, 'start')
        assert hasattr(LaunchWorker, 'cancel')
        assert hasattr(LaunchWorker, 'quit')
        assert hasattr(LaunchWorker, 'wait')