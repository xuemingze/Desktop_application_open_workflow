"""
Open-LLM-VTuber 后端进程管理（优化版）
============================

改进点：
- 更稳健的 PID 存活检查：POSIX 使用 os.kill(0,...), Windows 优先使用 tasklist（回退到 psutil 如可用）。
- 更安全的状态保存：原子写入（临时文件 + os.replace），并使用 typing 定义状态结构。
- 更合理的日志文件管理：把打开的日志句柄保存在 manager 实例，stop/cleanup 时关闭，避免文件句柄泄漏。
- 更灵活的 venv 查找：支持 .venv、venv、env 等常见目录，并优先选择 pythonw.exe（Windows）/python（POSIX）。
- 更明确的 Windows 常量处理：从 subprocess 取常量（如存在）或回退到硬编码值。
- 改用 logging 模块记录内部错误，而不是直接 print 到 stderr。
- 使用 os.kill 在 POSIX 上终止进程，Windows 上仍使用 taskkill，以保证子进程树被终结。

保持了原有行为和向后兼容性（仍会在 Windows 上使用 CREATE_NO_WINDOW 避免控制台闪烁）。
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

# 复用 desktop_auto 的 data_dir 定位
try:
    from data_paths import USER_DATA_DIR
except Exception:
    USER_DATA_DIR = Path.home() / "桌面自动化助手"

STATE_FILE = Path(USER_DATA_DIR) / "vtuber_backend_state.json"
LOG_FILE = Path(USER_DATA_DIR) / "vtuber_backend_stderr.log"

logger = logging.getLogger("vtuber_backend_manager")
if not logger.handlers:
    # 默认不配置根 logger，避免重复配置；UI 进程可按需配置 logging
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("[VTuberBackend] %(levelname)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


VTuberState = Dict[str, Optional[object]]


def _load_state() -> VTuberState:
    """读取持久化的 VTuber 后端状态，失败时返回空状态。"""
    default = {"pid": None, "path": None, "started_at": None}
    try:
        if not STATE_FILE.exists():
            return default
        text = STATE_FILE.read_text(encoding="utf-8")
        data = json.loads(text)
        # 保证字段存在
        return {"pid": data.get("pid"), "path": data.get("path"), "started_at": data.get("started_at")}
    except Exception as e:
        logger.warning("加载状态失败: %s", e)
        return default


def _atomic_write(path: Path, content: str) -> None:
    """用临时文件+os.replace 原子地写入文本文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name, dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, str(path))
    except Exception:
        # 确保临时文件被清理
        try:
            os.unlink(tmp)
        except Exception:
            pass
        raise


def _save_state(state: VTuberState) -> None:
    """保存 VTuber 后端状态到 data_dir（原子写入）。"""
    try:
        _atomic_write(STATE_FILE, json.dumps(state, ensure_ascii=False, indent=2))
    except Exception as e:
        logger.error("保存状态失败: %s", e)


def _is_pid_alive(pid: Optional[int]) -> bool:
    """检查 PID 是否还在运行。

    POSIX: 使用 os.kill(pid, 0)。
    Windows: 尝试使用 tasklist（避免依赖第三方）。
    如可用 psutil，会优先使用它。
    """
    if not pid:
        return False

    # 尝试 psutil（优先）
    try:
        import psutil

        return psutil.pid_exists(int(pid))
    except Exception:
        pass

    if sys.platform == "win32":
        # 使用 tasklist 查询（有时在中文 Windows 上输出为 gbk/gb2312）
        tasklist = shutil_which("tasklist")
        if not tasklist:
            return False
        # 尝试使用本地默认编码（mbcs 在 Windows 中通常可用），回退到 gbk
        enc = None
        try:
            enc = sys.getfilesystemencoding() or "mbcs"
        except Exception:
            enc = "gbk"
        try:
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            completed = subprocess.run(
                [tasklist, "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                encoding=enc,
                errors="ignore",
                creationflags=creationflags,
            )
            return str(pid) in (completed.stdout or "")
        except Exception:
            return False
    else:
        # POSIX
        try:
            os.kill(int(pid), 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            # 进程存在但无权限
            return True
        except Exception:
            return False


def shutil_which(cmd: str) -> Optional[str]:
    """包装 shutil.which，避免在上层导入冲突。"""
    try:
        import shutil

        return shutil.which(cmd)
    except Exception:
        return None


class VTuberBackendManager:
    """管理 Open-LLM-VTuber 后端进程（单例由模块级 get_manager 提供）。"""

    def __init__(self) -> None:
        self.state = _load_state()
        self._log_file = None  # type: Optional["TextIO"]
        # 如果记录的 PID 已经死了，清掉
        if self.state.get("pid") and not _is_pid_alive(self.state["pid"]):
            self.state = {"pid": None, "path": None, "started_at": None}
            _save_state(self.state)

    @staticmethod
    def validate_path(path: str) -> Tuple[bool, str]:
        """校验 VTuber 后端路径，返回 (是否有效, 错误信息或 run_server.py 路径)。"""
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

    @staticmethod
    def find_venv_python(path: str) -> Optional[str]:
        """查找 VTuber 目录里的 venv Python.

        支持常见虚拟环境目录：.venv, venv, env, .env。
        在 Windows 优先寻找 pythonw.exe -> python.exe；POSIX 查找 bin/python。
        """
        p = Path(path)
        candidates = []
        for v in (".venv", "venv", "env", ".env"):
            candidates.append(p / v)
        for vdir in candidates:
            if sys.platform == "win32":
                pyw = vdir / "Scripts" / "pythonw.exe"
                if pyw.exists():
                    return str(pyw)
                py = vdir / "Scripts" / "python.exe"
                if py.exists():
                    return str(py)
            else:
                py = vdir / "bin" / "python"
                if py.exists():
                    return str(py)
        return None

    def is_running(self) -> bool:
        """检查后端是否在运行。"""
        pid = self.state.get("pid")
        try:
            return _is_pid_alive(pid)
        except Exception:
            return False

    def get_status(self) -> Dict[str, Optional[object]]:
        """获取当前状态快照（用于 UI 显示）。"""
        pid = self.state.get("pid")
        running = self.is_running()
        return {
            "running": running,
            "pid": pid if running else None,
            "path": self.state.get("path"),
            "started_at": self.state.get("started_at"),
            "log": str(LOG_FILE) if LOG_FILE.exists() else None,
        }

    def start(self, path: str) -> Tuple[bool, str]:
        """启动 VTuber 后端，返回 (成功, 消息)。"""
        if self.is_running():
            return False, f"已在运行 (PID={self.state.get('pid')})"

        valid, info = self.validate_path(path)
        if not valid:
            return False, info
        run_server = info

        # 打开/准备日志文件（保持句柄以便子进程写入）
        try:
            LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            self._log_file = open(LOG_FILE, "a", encoding="utf-8", errors="ignore", buffering=1)
        except Exception as e:
            logger.warning("无法打开日志文件 %s: %s", LOG_FILE, e)
            self._log_file = None

        try:
            python_exe = self.find_venv_python(path) or sys.executable

            if sys.platform == "win32":
                create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
                create_new_pgroup = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                creationflags = create_new_pgroup | create_no_window
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0  # SW_HIDE
            else:
                creationflags = 0
                startupinfo = None

            proc = subprocess.Popen(
                [python_exe, run_server],
                cwd=str(Path(path)),
                creationflags=creationflags,
                startupinfo=startupinfo,
                stdout=self._log_file if self._log_file else subprocess.DEVNULL,
                stderr=subprocess.STDOUT if self._log_file else subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                close_fds=(sys.platform != "win32"),
            )
        except Exception as e:
            if self._log_file:
                try:
                    self._log_file.close()
                except Exception:
                    pass
                self._log_file = None
            logger.exception("启动子进程失败")
            return False, f"启动失败: {e}"

        # 等 2 秒确认进程真的拉起来了
        time.sleep(2.0)
        alive = _is_pid_alive(proc.pid)
        if not alive:
            # 读取日志尾部作为诊断信息
            tail = ""
            if self._log_file:
                try:
                    self._log_file.flush()
                    self._log_file.close()
                except Exception:
                    pass
                self._log_file = None
            try:
                if LOG_FILE.exists():
                    content = LOG_FILE.read_text(encoding="utf-8", errors="ignore")
                    tail = content[-800:] if content else ""
            except Exception:
                tail = ""
            msg = f"进程启动后立即退出 (PID={proc.pid})"
            if tail.strip():
                msg += f"\n\n输出尾部:\n{tail}"
            else:
                msg += "\n\n常见原因: run_server.py 依赖未安装 (需运行 uv sync)"
            msg += f"\n\n日志文件: {LOG_FILE}"
            return False, msg

        self.state = {
            "pid": proc.pid,
            "path": str(Path(path).resolve()),
            "started_at": int(time.time()),
        }
        _save_state(self.state)
        py_info = "venv" if self.find_venv_python(path) else "sys"
        logger.info("已启动 VTuber 后端 PID=%s python=%s", proc.pid, py_info)
        return True, f"已启动 (PID={proc.pid}, python={py_info})"

    def stop(self) -> Tuple[bool, str]:
        """停止 VTuber 后端。"""
        pid = self.state.get("pid")
        if not pid:
            return False, "未运行"
        if not _is_pid_alive(pid):
            self._cleanup_state_and_logs()
            return True, "进程已不存在（清理状态）"

        try:
            if sys.platform == "win32":
                # 使用 taskkill 以结束整个进程树
                taskkill = shutil_which("taskkill")
                if not taskkill:
                    return False, "taskkill 不可用"
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
                subprocess.run([
                    taskkill, "/F", "/T", "/PID", str(pid)
                ], capture_output=True, text=True, encoding="gbk", errors="ignore", creationflags=creationflags)
            else:
                # POSIX: 先尝试温和终止，然后强制
                try:
                    os.kill(int(pid), subprocess.signal.SIGTERM)
                except AttributeError:
                    os.kill(int(pid), 15)
                except ProcessLookupError:
                    pass
        except Exception as e:
            logger.exception("停止进程时出错")
            return False, f"停止失败: {e}"

        # 等一会儿再确认
        time.sleep(0.8)
        if _is_pid_alive(pid):
            # POSIX 下尝试强制 SIGKILL
            if sys.platform != "win32":
                try:
                    os.kill(int(pid), subprocess.signal.SIGKILL)
                except Exception:
                    pass
                time.sleep(0.4)
            if _is_pid_alive(pid):
                return False, f"无法终止进程 (PID={pid})"

        self._cleanup_state_and_logs()
        return True, "已停止"

    def _cleanup_state_and_logs(self) -> None:
        """内部：清理状态与关闭日志句柄。"""
        self.state = {"pid": None, "path": None, "started_at": None}
        _save_state(self.state)
        if self._log_file:
            try:
                self._log_file.flush()
                self._log_file.close()
            except Exception:
                pass
            self._log_file = None

    def cleanup_stale(self) -> None:
        """清理已死进程的残留状态（供外部周期调用）。"""
        if self.state.get("pid") and not _is_pid_alive(self.state["pid"]):
            self._cleanup_state_and_logs()


# 单例
_instance: Optional[VTuberBackendManager] = None


def get_manager() -> VTuberBackendManager:
    """获取全局单例。"""
    global _instance
    if _instance is None:
        _instance = VTuberBackendManager()
    return _instance
