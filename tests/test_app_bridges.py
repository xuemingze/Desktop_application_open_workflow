"""Step 3: app_bridges 模块回归测试 (覆盖 Step 1B 重构)"""
import pytest
from PySide6.QtCore import QObject

from app_bridges import AppBridges


class FakeWindow(QObject):
    """模拟 MainWindow: 必须是 QObject 才能做 AppBridges parent"""
    def __init__(self):
        super().__init__()
        self.bridges = AppBridges(self)

    # 复制 MainWindow 上 7 个 @property 转发 (Step 1B-4)
    @property
    def memory_engine_mgr(self): return self.bridges.memory_engine_mgr

    @property
    def assistant_core(self): return self.bridges.assistant_core

    @property
    def _companion_bridge(self): return self.bridges._companion_bridge

    @property
    def _vtuber_bridge(self): return self.bridges._vtuber_bridge

    @property
    def _assistant_bridge(self): return self.bridges._assistant_bridge

    @property
    def _reminder_timer(self): return self.bridges._reminder_timer

    @property
    def _diary_scheduler(self): return self.bridges._diary_scheduler


@pytest.fixture
def win():
    return FakeWindow()


# 7 字段名 (Step 1B-2 迁移的字段)
SEVEN_FIELDS = [
    'memory_engine_mgr',
    'assistant_core',
    '_companion_bridge',
    '_vtuber_bridge',
    '_assistant_bridge',
    '_reminder_timer',
    '_diary_scheduler',
]


# ---------- A. AppBridges 容器本身 ----------

class TestAppBridgesContainer:
    def test_seven_fields_default_none(self, win):
        """7 字段初始值全 None (避免 MainWindow 上 self.xxx = None 7 行)"""
        for f in SEVEN_FIELDS:
            assert getattr(win.bridges, f) is None, f'{f} should default None'

    def test_seven_fields_assignable(self, win):
        """7 字段都可 setattr"""
        for f in SEVEN_FIELDS:
            setattr(win.bridges, f, f'fake_{f}')
            assert getattr(win.bridges, f) == f'fake_{f}'

    def test_parent_chain(self, win):
        """AppBridges parent=MainWindow, 跟随 Qt 生命周期"""
        assert win.bridges.parent() is win

    def test_qobject_subclass(self):
        """AppBridges 必须是 QObject 子类 (Qt parent 关系需要)"""
        from PySide6.QtCore import QObject
        assert issubclass(AppBridges, QObject)

    def test_repr_doesnt_crash(self, win):
        """repr 不应崩 (允许 None 字段)"""
        r = repr(win.bridges)
        assert 'AppBridges' in r


# ---------- B. @property 转发 (Step 1B-4) ----------

class TestPropertyForwarding:
    """验证 7 个 @property 把 MainWindow.xxx 转发到 self.bridges.xxx"""

    @pytest.mark.parametrize('attr', SEVEN_FIELDS)
    def test_property_returns_none_when_unset(self, win, attr):
        """未设置时返回 None"""
        assert getattr(win, attr) is None

    @pytest.mark.parametrize('attr', SEVEN_FIELDS)
    def test_property_forwards_set_value(self, win, attr):
        """在 bridges 上设值后, MainWindow.xxx 转发读到"""
        sentinel = object()
        setattr(win.bridges, attr, sentinel)
        assert getattr(win, attr) is sentinel

    @pytest.mark.parametrize('attr', SEVEN_FIELDS)
    def test_property_returns_property_object(self, attr):
        """属性是 property 类型 (不是普通 attribute)"""
        # 在 FakeWindow 类上找这个 property
        for klass in FakeWindow.__mro__:
            if attr in klass.__dict__ and isinstance(klass.__dict__[attr], property):
                assert klass.__dict__[attr].fget is not None
                break
        else:
            pytest.fail(f'{attr} 不是 property')


# ---------- C. MainWindow 真实源码不变量 (不导入 desktop_auto, 静态校验) ----------

class TestDesktopAutoInvariants:
    """对 desktop_auto.py 真实源码做不变量校验 (不实际启动 GUI)"""

    @classmethod
    @pytest.fixture(scope='class')
    def source(cls):
        import pathlib
        return pathlib.Path(r'D:\项目\控制电脑\desktop_auto.py').read_text(encoding='utf-8')

    def test_app_bridges_import_present(self, source):
        assert 'from app_bridges import AppBridges' in source

    def test_self_bridges_init_in_init(self, source):
        """__init__ 中应 self.bridges = AppBridges(self)"""
        assert 'self.bridges = AppBridges(self)' in source

    def test_no_self_xxx_assignment_for_7_fields(self, source):
        """7 个字段不应再有 self.xxx = (None/...) 赋值残留"""
        import re
        bad = []
        for f in SEVEN_FIELDS:
            # 匹配 self.<field> = 任意值 (排除 self.bridges.<field> = ...)
            pat = re.compile(rf'^\s*self\.{re.escape(f)}\s*=\s*[^.]', re.MULTILINE)
            if pat.search(source):
                # 但要排除 self.bridges.x = ... 的部分
                # pat 已经用 [^.] 防止匹配到 self.bridges.xxx
                bad.append(f)
        assert not bad, f'字段还有 self.xxx = 残留: {bad}'

    def test_init_companion_bridge_called_once(self, source):
        """_init_companion_bridge() 应只被调用 1 次 (Step 1B bug fix 保留)"""
        n = source.count('self._init_companion_bridge()')
        assert n == 1, f'应为 1 次, 实际 {n} 次'

    def test_mainwindow_has_seven_properties(self, source):
        """MainWindow 上应有 7 个 @property 转发 (Step 1B-4)"""
        # 简单行数检查: 7 个 @property 应在 MainWindow class 体内
        import re
        # 找所有 @property 行 (忽略 class 内其他装饰器)
        prop_count = len(re.findall(r'^\s*@property\s*$', source, re.MULTILINE))
        assert prop_count >= 7, f'@property 至少 7 个, 实际 {prop_count}'