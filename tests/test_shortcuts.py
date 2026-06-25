"""Step 1C Phase 4: self.shortcuts 拆分测试基准"""
import pytest
from PySide6.QtCore import QObject

from app_containers import AppContainers, ShortcutsStore


# ---------- A. ShortcutsStore 单测 ----------

class FakeShortcut:
    """模拟 ShortcutInfo: 只需 .target 字段"""
    def __init__(self, name='app', target='C:\\app.exe'):
        self.name = name
        self.target = target


class TestShortcutsStore:
    def test_default_empty(self):
        """默认空"""
        s = ShortcutsStore()
        assert len(s) == 0
        assert bool(s) is False
        assert s.items() == []
        list(s)  # 不应崩

    def test_replace_then_iterate(self):
        """replace 后可迭代 + 长度"""
        s = ShortcutsStore()
        items = [FakeShortcut('a', 'C:\\a.exe'), FakeShortcut('b', 'C:\\b.exe')]
        s.replace(items)
        assert len(s) == 2
        assert bool(s) is True
        assert [sc.name for sc in s] == ['a', 'b']

    def test_replace_with_none(self):
        """replace(None) 应清空, 不崩"""
        s = ShortcutsStore()
        s.replace([FakeShortcut()])
        s.replace(None)
        assert len(s) == 0

    def test_items_returns_copy(self):
        """items() 返回副本 (避免外部 mutate 内部状态)"""
        s = ShortcutsStore()
        s.replace([FakeShortcut()])
        items = s.items()
        items.append(FakeShortcut('extra'))
        assert len(s) == 1  # 内部未变

    def test_at_within_bounds(self):
        """at(0) / at(N-1) 返回对象"""
        s = ShortcutsStore()
        sc = FakeShortcut('only')
        s.replace([sc])
        assert s.at(0) is sc

    def test_at_out_of_bounds(self):
        """at(-1) / at(N) 返回 None"""
        s = ShortcutsStore()
        s.replace([FakeShortcut()])
        assert s.at(-1) is None
        assert s.at(99) is None

    def test_at_empty_store(self):
        """空 store 时 at(0) 返回 None"""
        s = ShortcutsStore()
        assert s.at(0) is None

    def test_find_by_path_exact_match(self):
        """find_by_path 精确匹配"""
        s = ShortcutsStore()
        sc1 = FakeShortcut('a', 'C:\\a.exe')
        sc2 = FakeShortcut('b', 'C:\\b.exe')
        s.replace([sc1, sc2])
        assert s.find_by_path('C:\\a.exe') is sc1
        assert s.find_by_path('C:\\b.exe') is sc2

    def test_find_by_path_with_norm(self):
        """find_by_path 匹配 path_norm fallback"""
        s = ShortcutsStore()
        sc = FakeShortcut('app', 'C:\\Program Files\\app.exe')
        s.replace([sc])
        # 路径不存在, path_norm 提供归一化形式
        assert s.find_by_path('C:/some/path', path_norm='C:\\Program Files\\app.exe') is sc

    def test_find_by_path_not_found(self):
        """未找到返回 None"""
        s = ShortcutsStore()
        s.replace([FakeShortcut('a', 'C:\\a.exe')])
        assert s.find_by_path('C:\\nonexistent.exe') is None


# ---------- B. AppContainers.shortcuts 默认值 ----------

class TestAppContainersShortcuts:
    def test_shortcuts_default_empty_store(self):
        """AppContainers.shortcuts 默认 ShortcutsStore() 实例"""
        c = AppContainers(QObject())
        assert isinstance(c.shortcuts, ShortcutsStore)
        assert len(c.shortcuts) == 0


# ---------- C. desktop_auto.py 真实源码不变量 ----------

class TestDesktopAutoShortcutsInvariants:
    @classmethod
    @pytest.fixture(scope='class')
    def source(cls):
        import pathlib
        return pathlib.Path(r'D:\项目\控制电脑\desktop_auto.py').read_text(encoding='utf-8')

    def test_no_direct_self_shortcuts_declaration(self, source):
        """不应再有 self.shortcuts: list[ShortcutInfo] = [] 声明"""
        assert 'self.shortcuts: list[ShortcutInfo] = []' not in source

    def test_no_direct_self_shortcuts_assignment(self, source):
        """refresh_shortcuts 中 self.shortcuts = scan_desktop_shortcuts() 应改为 self.containers.shortcuts.replace(...)"""
        assert 'self.shortcuts = scan_desktop_shortcuts()' not in source

    def test_no_direct_self_shortcuts_iteration(self, source):
        """3 处 for sc in self.shortcuts: 应改为 for sc in self.containers.shortcuts:"""
        n = source.count('for sc in self.shortcuts:')
        assert n == 0, f'for sc in self.shortcuts: 残留 {n} 处'

    def test_no_direct_len_self_shortcuts(self, source):
        """3 处 len(self.shortcuts) 应改为 len(self.containers.shortcuts)"""
        n = source.count('len(self.shortcuts)')
        assert n == 0, f'len(self.shortcuts) 残留 {n} 处'

    def test_no_direct_self_shortcuts_truthiness(self, source):
        """if self.shortcuts: 应改为 if self.containers.shortcuts:"""
        assert 'if self.shortcuts:' not in source

    def test_no_direct_self_shortcuts_indexing(self, source):
        """self.shortcuts[row] 应改为 self.containers.shortcuts.at(row)"""
        assert 'self.shortcuts[' not in source, 'self.shortcuts[...] 残留'

    def test_no_direct_list_self_shortcuts(self, source):
        """list(self.shortcuts) 应改为 self.containers.shortcuts.items()"""
        assert 'list(self.shortcuts)' not in source

    def test_containers_shortcuts_usage_present(self, source):
        """10 处 self.shortcuts 应改为 self.containers.shortcuts.xxx"""
        n = source.count('self.containers.shortcuts')
        # 至少 8 处: replace + 3 迭代 + 3 len + 1 真值 + 1 at + 1 find_by_path = 9
        assert n >= 8, f'self.containers.shortcuts 引用过少: {n}'

    def test_shortcuts_property_forwarding(self, source):
        """MainWindow 应有 @property shortcuts 转发 (API 兼容)"""
        assert 'def shortcuts(self):' in source