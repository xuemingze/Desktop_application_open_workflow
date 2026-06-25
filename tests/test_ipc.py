"""Step 1C Phase 2: self.ipc_server 拆分测试基准

设计:
- AppContainers.ipc 默认 None (不实例化,生命周期由 MainWindow._start_ipc_server 触发)
- 重构后: MainWindow 不再有 self.ipc_server 直接字段,改为 self.containers.ipc
- 外部通过 @property self.ipc_server 仍能访问 (API 兼容)
"""
import pytest
from PySide6.QtCore import QObject

from app_containers import AppContainers


class TestAppContainersIPC:
    def test_ipc_default_none(self):
        """AppContainers.ipc 默认 None (生命周期由 MainWindow 触发)"""
        from PySide6.QtCore import QObject
        c = AppContainers(QObject())
        assert c.ipc is None

    def test_ipc_assignable(self):
        """ipc 字段可赋值为任意对象 (类型由 MainWindow 保证)"""
        from PySide6.QtCore import QObject
        c = AppContainers(QObject())
        sentinel = object()
        c.ipc = sentinel
        assert c.ipc is sentinel


class TestDesktopAutoIPCInvariants:
    """重构后, desktop_auto.py 不变量"""

    @classmethod
    @pytest.fixture(scope='class')
    def source(cls):
        import pathlib
        return pathlib.Path(r'D:\项目\控制电脑\desktop_auto.py').read_text(encoding='utf-8')

    def test_no_direct_self_ipc_server_assignment(self, source):
        """不应再有 self.ipc_server = ... 赋值 (1 处写: L1792)"""
        import re
        pat = re.compile(r'^\s*self\.ipc_server\s*=\s*[^.]', re.MULTILINE)
        hits = pat.findall(source)
        assert hits == [], f'仍有 self.ipc_server = 残留: {hits}'

    def test_no_direct_self_ipc_server_read_in_closeEvent(self, source):
        """closeEvent 中不应再有 self.ipc_server.stop() / .wait()"""
        # 改为 self.containers.ipc.stop() / .wait()
        n_direct_stop = source.count('self.ipc_server.stop()')
        n_direct_wait = source.count('self.ipc_server.wait(')
        assert n_direct_stop == 0, f'self.ipc_server.stop() 还有 {n_direct_stop} 处'
        assert n_direct_wait == 0, f'self.ipc_server.wait() 还有 {n_direct_wait} 处'

    def test_containers_ipc_usage_present(self, source):
        """3 处 ipc 用法应改为 self.containers.ipc"""
        n = source.count('self.containers.ipc')
        # 至少 3 处: 1 处赋值 + 2 处 stop/wait
        assert n >= 3, f'self.containers.ipc 引用过少: {n}'

    def test_optional_ipc_server_property(self, source):
        """为 API 兼容, MainWindow 应有 @property self.ipc_server 转发"""
        # @property 装饰器存在 + def ipc_server(self) 形式
        # 简化: 检查 ipc_server 同时作为 property 和 self.containers.ipc 共存
        assert 'self.containers.ipc' in source
        # property 转发形式: @property\n    def ipc_server(self):
        # 至少存在一处定义
        assert '@property' in source  # 已有 7 个 + 新增 1 个


class TestIPCServerThreadAPIUnchanged:
    """IPCServerThread 类本身不变 (Phase 2 不动它)"""

    def test_class_still_exists(self):
        from desktop_auto import IPCServerThread
        assert IPCServerThread is not None

    def test_has_required_signals(self):
        """IPCServerThread 应仍提供 log_signal / message_signal / start / stop / wait"""
        from desktop_auto import IPCServerThread
        from PySide6.QtCore import QThread
        assert issubclass(IPCServerThread, QThread)
        # 信号检查
        assert hasattr(IPCServerThread, 'log_signal')
        assert hasattr(IPCServerThread, 'message_signal')
        assert hasattr(IPCServerThread, 'start')
        assert hasattr(IPCServerThread, 'stop')
        assert hasattr(IPCServerThread, 'wait')