"""app_containers.py - 持久化容器组 (Step 1C)

Phase 1: UIState - 一键启动 PID 状态
Phase 2: IPCService / self.ipc_server 已在 AppContainers.ipc 占位
Phase 3: WorkerRegistry / self.worker 已在 AppContainers.worker 占位
Phase 4: ShortcutsStore - 抽离 self.shortcuts (10 处用法)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Iterator

from PySide6.QtCore import QObject


# ---------------------------------------------------------------------------
# Phase 1: UIState - 一键启动 PID 状态
# ---------------------------------------------------------------------------
class UIState:
    """等价于原 desktop_auto.py 的 self.state dict.

    字段名与原 dict 完全一致 (pids/names/ts), 保证与 launch_state.json 文件兼容.
    """

    __slots__ = ("pids", "names", "ts")

    def __init__(self) -> None:
        self.pids: list[int] = []
        self.names: list[str] = []
        self.ts: int = 0

    def to_dict(self) -> dict:
        return {"pids": list(self.pids), "names": list(self.names), "ts": int(self.ts)}

    @classmethod
    def from_dict(cls, data: dict) -> "UIState":
        s = cls()
        if isinstance(data, dict):
            pids = data.get("pids", [])
            if isinstance(pids, list):
                s.pids = [int(x) for x in pids]
            names = data.get("names", [])
            if isinstance(names, list):
                s.names = [str(x) for x in names]
            ts = data.get("ts", 0)
            try:
                s.ts = int(ts)
            except (TypeError, ValueError):
                s.ts = 0
        return s

    @classmethod
    def load(cls, path: Path) -> "UIState":
        try:
            if path.exists():
                data = json.loads(path.read_text("utf-8"))
                return cls.from_dict(data)
        except Exception:
            pass
        return cls()

    def save(self, path: Path) -> bool:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
                "utf-8",
            )
            return True
        except Exception:
            return False

    def clear(self) -> None:
        self.pids = []
        self.names = []
        self.ts = 0


# ---------------------------------------------------------------------------
# Phase 4: ShortcutsStore - 桌面快捷方式列表封装
# ---------------------------------------------------------------------------
class ShortcutsStore:
    """封装 self.shortcuts: list[ShortcutInfo] 的所有用法.

    替代原 desktop_auto.py 的 10 处 self.shortcuts 引用:
    - 1 处赋值 (refresh_shortcuts)
    - 3 处迭代 (refresh / find_by_path / expand_running)
    - 3 处 length 判断 (count / 真值 / row 边界)
    - 2 处索引访问 (_current / list())
    """

    __slots__ = ("_items",)

    def __init__(self) -> None:
        self._items: list = []

    # --- 列表操作 ---
    def replace(self, items: list) -> None:
        """整体替换 (供 refresh_shortcuts 调用, 对应原 self.shortcuts = scan_desktop_shortcuts())"""
        self._items = list(items) if items else []

    def items(self) -> list:
        """返回底层列表副本 (供 list(self.shortcuts) 用)"""
        return list(self._items)

    # --- 迭代 ---
    def __iter__(self) -> Iterator:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __bool__(self) -> bool:
        return bool(self._items)

    # --- 索引访问 ---
    def at(self, index: int) -> Optional[object]:
        """按索引访问 (供 _current 边界检查用)"""
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    # --- 业务查询 ---
    def find_by_path(self, path: str, path_norm: str = "") -> Optional[object]:
        """按 target 路径查找 (供 _match_shortcut_for_path 用)

        path_norm 是可选的归一化路径,匹配任一即可
        """
        for sc in self._items:
            if sc.target == path or (path_norm and sc.target == path_norm):
                return sc
        return None


# ---------------------------------------------------------------------------
# AppContainers - 4 个持久化字段的集中容器 (沿用 AppBridges 模板)
# ---------------------------------------------------------------------------
class AppContainers(QObject):
    """MainWindow 上的非运行时桥接状态容器.

    - state: UIState (Phase 1)
    - ipc: Optional[IPCServerThread] (Phase 2)
    - worker: Optional[LaunchWorker] (Phase 3)
    - shortcuts: ShortcutsStore (Phase 4)
    """

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.state: UIState = UIState()
        self.shortcuts: ShortcutsStore = ShortcutsStore()   # Phase 4
        self.worker = None           # Phase 3
        self.ipc = None              # Phase 2

    def __repr__(self) -> str:
        return (
            f"AppContainers(state.pids={len(self.state.pids)}, "
            f"shortcuts={len(self.shortcuts)}, "
            f"worker={'set' if self.worker else 'None'}, "
            f"ipc={'set' if self.ipc else 'None'})"
        )