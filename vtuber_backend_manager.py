"""
Open-LLM-VTuber 后端进程管理
============================
- 启动 run_server.py 作为子进程
- 跟踪 PID，存到 data_dir/vtuber_backend_state.json
- 提供 start/stop/is_running/status 查询
- 跨进程安全（GUI 关闭重开也能找到上次没杀掉的 VTuber 进程）

设计原则:
- 不依赖 Qt（manager 给 Qt 调用，自身保持纯逻辑）
- PID 状态持久化到 data_dir，方便诊断
- 启动用 CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS，VTuber 独立于 GUI
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, Tuple

# 复用 desktop_auto 的 data_dir 定位
try:
    from data_paths import USER_DATA_DIR
except Exception:
    USER_DATA_DIR = Path.home() / "桌面自动化助手"

STATE_FILE = Path(USER_DATA_DIR) / "vtuber_backend_state.json"


def _load_state() -> dict:
    """读取持久化的 VTuber 后端状态"""
    if not STATE_FILE.exists():
        return {"pid": None, "path": None, "started_at": None}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"pid": None, "path": None, "started_at": None}


def _save_state(state: dict) -> None:
    """保存 VTuber 后端状态到 data_dir"""
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as e:
        print(f"[VTuberBackend] 保存状态失败: {e}", file=sys.stderr)


def _is_pid_alive(pid: Optional[int]) -> bool:
    """检查 PID 是否还在运行（Windows 用 tasklist）"""
    if not pid:
        return False
    try:
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, encoding="gbk", errors="ignore"
        )
        # tasklist 在进程存在时返回 "..." 开头的一行；不存在时返回 "INFO: ..."
        return str(pid) in out.stdout
    except Exception:
        return False


class VTuberBackendManager:
    """管理 Open-LLM-VTuber 后端进程"""

    def __init__(self) -> None:
        self.state = _load_state()
        # 如果记录的 PID 已经死了，清掉
        if self.state.get("pid") and not _is_pid_alive(self.state["pid"]):
            self.state = {"pid": None, "path": None, "started_at": None}
            _save_state(self.state)

    @staticmethod
    def validate_path(path: str) -> Tuple[bool, str]:
        """
        校验 VTuber 后端路径
        返回 (是否有效, 错误信息或 run_server.py 完整路径)
        """
        if not path:
            return False, "路径为空"
        p = Path(path)
        if not p.exists():
            return False, f"路径不存在: {path}"
        if not p.is_dir():
            return False, f"不是目录: {path}"
        run_server = p / "run_server.py"
        if not run_server.exists():
            return False, f"未找到 run_server.py: {run_server}"
        return True, str(run_server)

    def is_running(self) -> bool:
        """检查后端是否在运行"""
        return _is_pid_alive(self.state.get("pid"))

    def get_status(self) -> dict:
        """获取当前状态快照（用于 UI 显示）"""
        pid = self.state.get("pid")
        running = self.is_running()
        return {
            "running": running,
            "pid": pid if running else None,
            "path": self.state.get("path"),
            "started_at": self.state.get("started_at"),
        }

    def start(self, path: str) -> Tuple[bool, str]:
        """
        启动 VTuber 后端
        返回 (成功, 消息)
        """
        if self.is_running():
            return False, f"已在运行 (PID={self.state.get('pid')})"

        valid, info = self.validate_path(path)
        if not valid:
            return False, info
        run_server = info

        # 准备一个临时文件接收 stdout/stderr, 便于出错时诊断
        log_path = Path(USER_DATA_DIR) / "vtuber_backend_stderr.log"
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_f = open(log_path, "w", encoding="utf-8", errors="ignore")
        except Exception:
            log_f = None

        try:
            # 启动子进程，独立进程组
            # 问题: 某些 Python 发行版 (如 embedded / 某些 pyInstaller frozen) 使用 python._pth
            #   会忽略 PYTHONPATH 和脚本所在目录。
            # 解决方案: 生成一个临时 wrapper 脚本, 里面先 sys.path.insert, 再调 runpy.run_path。
            import tempfile
            wrapper_dir = Path(USER_DATA_DIR) / "vtuber_wrapper"
            wrapper_dir.mkdir(parents=True, exist_ok=True)
            wrapper_path = wrapper_dir / "_run_vtuber_server.py"
            # 用 UTF-8 写避免中文路径编码问题
            wrapper_content = (
                "# -*- coding: utf-8 -*-\n"
                "import sys, runpy\n"
                "from pathlib import Path\n"
                f"sys.path.insert(0, r'{Path(path).resolve()}')\n"
                f"runpy.run_path(r'{run_server}', run_name='__main__')\n"
            )
            wrapper_path.write_text(wrapper_content, encoding="utf-8")

            proc = subprocess.Popen(
                [sys.executable, str(wrapper_path)],
                cwd=str(Path(path)),
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                | subprocess.DETACHED_PROCESS,
                stdout=log_f if log_f else subprocess.DEVNULL,
                stderr=subprocess.STDOUT if log_f else subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                close_fds=True,
            )
        except Exception as e:
            if log_f: log_f.close()
            return False, f"启动失败: {e}"

        # 等 2 秒确认进程真的拉起来了（避免立刻崩了但 PID 已记录）
        time.sleep(2.0)
        alive = _is_pid_alive(proc.pid)
        if not alive:
            # 读取日志尾部作为诊断信息
            tail = ""
            if log_f:
                log_f.flush()
                log_f.close()
            try:
                if log_path.exists():
                    content = log_path.read_text(encoding="utf-8", errors="ignore")
                    tail = content[-600:] if content else ""
            except Exception:
                tail = ""
            msg = f"进程启动后立即退出 (PID={proc.pid})"
            if tail.strip():
                msg += f"\n\n输出尾部:\n{tail}"
            else:
                msg += "\n\n常见原因: run_server.py 依赖未安装 (需运行 uv sync)"
            msg += f"\n\n日志文件: {log_path}"
            return False, msg

        self.state = {
            "pid": proc.pid,
            "path": str(Path(path).resolve()),
            "started_at": int(time.time()),
        }
        _save_state(self.state)
        # 不要在父进程关闭 log_f, 保持打开以便子进程后续日志也能写入
        return True, f"已启动 (PID={proc.pid})"

    def stop(self) -> Tuple[bool, str]:
        """停止 VTuber 后端"""
        pid = self.state.get("pid")
        if not pid:
            return False, "未运行"
        if not _is_pid_alive(pid):
            self.state = {"pid": None, "path": None, "started_at": None}
            _save_state(self.state)
            return True, "进程已不存在（清理状态）"
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True, text=True, encoding="gbk", errors="ignore"
            )
        except Exception as e:
            return False, f"taskkill 失败: {e}"
        # 等一下再确认
        time.sleep(0.8)
        if _is_pid_alive(pid):
            return False, f"taskkill 失败，进程仍存活 (PID={pid})"
        self.state = {"pid": None, "path": None, "started_at": None}
        _save_state(self.state)
        return True, "已停止"

    def cleanup_stale(self) -> None:
        """清理已死进程的残留状态"""
        if self.state.get("pid") and not _is_pid_alive(self.state["pid"]):
            self.state = {"pid": None, "path": None, "started_at": None}
            _save_state(self.state)


# 单例
_instance: Optional[VTuberBackendManager] = None


def get_manager() -> VTuberBackendManager:
    """获取全局单例"""
    global _instance
    if _instance is None:
        _instance = VTuberBackendManager()
    return _instance
