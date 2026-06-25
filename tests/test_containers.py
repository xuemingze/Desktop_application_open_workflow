"""Step 1C: 锁定 4 个目标字段当前行为的回归测试

覆盖字段:
- self.state (本期重构: UIState 容器)
- self.worker / self.ipc_server / self.shortcuts (基准锁定, 不重构)
"""
import json
import pytest
import tempfile
from pathlib import Path

from app_containers import UIState


# ---------- A. UIState 单测 (Phase 1 重构目标) ----------

class TestUIState:
    """锁定 UIState 行为, 与原 desktop_auto.py 的 _load_state/_save_state 对账"""

    def test_default_empty_state(self):
        """未加载时, 默认 {'pids':[], 'names':[], 'ts':0}"""
        s = UIState()
        assert s.pids == []
        assert s.names == []
        assert s.ts == 0

    def test_set_pids_names_ts(self):
        """可设置 3 个字段"""
        s = UIState()
        s.pids = [123, 456]
        s.names = ["app1", "app2"]
        s.ts = 1700000000
        assert s.pids == [123, 456]
        assert s.names == ["app1", "app2"]
        assert s.ts == 1700000000

    def test_to_dict_roundtrip(self):
        """to_dict 字段名与原 desktop_auto 字典键完全一致 (兼容性)"""
        s = UIState()
        s.pids = [1, 2]
        s.names = ["a"]
        s.ts = 100
        d = s.to_dict()
        assert d == {"pids": [1, 2], "names": ["a"], "ts": 100}

    def test_from_dict(self):
        """from_dict 接受外部 dict, 容错缺失字段"""
        s = UIState.from_dict({"pids": [5], "names": ["x"], "ts": 99})
        assert s.pids == [5]
        assert s.names == ["x"]
        assert s.ts == 99

    def test_from_dict_partial(self):
        """from_dict 缺失字段不崩, 用默认值"""
        s = UIState.from_dict({"pids": [1]})
        assert s.pids == [1]
        assert s.names == []
        assert s.ts == 0

    def test_clear(self):
        """clear() 把状态重置为空"""
        s = UIState()
        s.pids = [1, 2, 3]
        s.names = ["a", "b", "c"]
        s.ts = 100
        s.clear()
        assert s.pids == []
        assert s.names == []
        assert s.ts == 0

    def test_load_from_file_not_exist(self, tmp_path):
        """load() 文件不存在时, 状态保持默认值"""
        path = tmp_path / "nope.json"
        s = UIState.load(path)
        assert s.pids == []
        assert s.names == []
        assert s.ts == 0

    def test_load_from_file_valid(self, tmp_path):
        """load() 读取已有文件"""
        path = tmp_path / "state.json"
        path.write_text(json.dumps({"pids": [7, 8], "names": ["x"], "ts": 1234}),
                        encoding="utf-8")
        s = UIState.load(path)
        assert s.pids == [7, 8]
        assert s.names == ["x"]
        assert s.ts == 1234

    def test_load_from_file_corrupt(self, tmp_path):
        """load() 文件损坏时, 返回默认状态 (不抛)"""
        path = tmp_path / "bad.json"
        path.write_text("{not valid json", encoding="utf-8")
        s = UIState.load(path)
        assert s.pids == []
        assert s.names == []
        assert s.ts == 0

    def test_save_and_load_roundtrip(self, tmp_path):
        """save() 写出的文件 load() 能读回"""
        path = tmp_path / "state.json"
        s1 = UIState()
        s1.pids = [10, 20]
        s1.names = ["a", "b"]
        s1.ts = 9999
        s1.save(path)
        s2 = UIState.load(path)
        assert s2.pids == [10, 20]
        assert s2.names == ["a", "b"]
        assert s2.ts == 9999


# ---------- B. desktop_auto.py 真实源码不变量 ----------

class TestDesktopAutoStateInvariants:
    """重构后, 4 处 self.state 用法应改为 self.containers.state.x"""

    @classmethod
    @pytest.fixture(scope='class')
    def source(cls):
        import pathlib
        return pathlib.Path(r'D:\项目\控制电脑\desktop_auto.py').read_text(encoding='utf-8')

    def test_app_containers_import_present(self, source):
        """应 from app_containers import AppContainers, UIState"""
        assert 'from app_containers import' in source

    def test_containers_init_present(self, source):
        """__init__ 中应 self.containers = AppContainers(self)"""
        assert 'self.containers = AppContainers(self)' in source

    def test_no_direct_self_state_assignment(self, source):
        """不应再有 self.state = {...} 赋值 (3 处都改用 self.containers.state.xxx)"""
        import re
        # 匹配 self.state = { 或 self.state = xxx (排除 self.containers.state)
        pat = re.compile(r'^\s*self\.state\s*=\s*[^.]', re.MULTILINE)
        hits = pat.findall(source)
        assert hits == [], f'仍有 self.state = ... 残留: {hits}'

    def test_no_self_state_dot_access_in_business_logic(self, source):
        """4 处业务用法应改为 self.containers.state.pids / .names / .ts"""
        # L3156/3157 原本是 self.state.get("pids", []) / self.state.get("names", [])
        # 重构后应是 self.containers.state.pids / .names
        n_containers_state = source.count('self.containers.state.')
        # 至少 3 处 (pids/names 读 + to_dict 调用)
        assert n_containers_state >= 3, f'self.containers.state. 引用过少: {n_containers_state}'

    def test_load_state_save_state_methods_kept_or_inlined(self, source):
        """_load_state 和 _save_state 可以保留 (委托给 UIState) 或内联"""
        # 不强制要求, 兼容两种实现
        pass


# ---------- C. AppContainers 容器 ----------

class TestAppContainers:
    """锁定 AppContainers 容器结构, 为后续 3 字段 (worker/ipc/shortcuts) 准备模板"""

    def test_qobject_subclass(self):
        from PySide6.QtCore import QObject
        from app_containers import AppContainers
        assert issubclass(AppContainers, QObject)

    def test_state_field_present(self):
        """AppContainers 应有 state 字段, 默认 UIState 实例"""
        from app_containers import AppContainers
        from PySide6.QtCore import QObject
        parent = QObject()
        c = AppContainers(parent)
        assert isinstance(c.state, UIState)

    def test_other_three_fields_default_none(self):
        """worker / ipc 默认 None, shortcuts 默认 ShortcutsStore() 空实例 (Step 1C-4)"""
        from app_containers import AppContainers
        from PySide6.QtCore import QObject
        c = AppContainers(QObject())
        assert c.worker is None
        assert c.ipc is None
        assert len(c.shortcuts) == 0   # Phase 4: ShortcutsStore 空实例, 长度 0