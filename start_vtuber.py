"""
start_vtuber.py - 以 Python 启动 Open-LLM-VTuber 后端（避免 cmd 中文乱码）

用法:
  python start_vtuber.py              # 启动（输出重定向到 vtuber_stdout.log）
  python start_vtuber.py --console    # 启动并在控制台实时显示输出
  python start_vtuber.py --stop       # 停止已启动的 VTuber 后端
"""
import os
import sys
import subprocess
import time
import signal
import json
import tempfile
from pathlib import Path

# 路径配置
REPO_DIR = Path(__file__).resolve().parent
VTUBER_DIR = REPO_DIR / "Open-LLM-VTuber-v1.2.1-zh"
VENV_PYTHON = REPO_DIR / ".venv" / "Scripts" / "python.exe"
PID_FILE = REPO_DIR / ".vtuber_pid"


def start(console: bool = False):
    if not VTUBER_DIR.exists():
        print(f"[ERR] VTuber 目录不存在: {VTUBER_DIR}")
        sys.exit(1)
    if not VENV_PYTHON.exists():
        print(f"[ERR] Python 未找到: {VENV_PYTHON}")
        sys.exit(1)

    run_server = VTUBER_DIR / "run_server.py"
    if not run_server.exists():
        print(f"[ERR] 未找到 run_server.py: {run_server}")
        sys.exit(1)

    # 检查是否已在运行
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            # 检查进程是否存在
            import psutil
            if psutil.pid_exists(pid):
                print(f"[WARN] VTuber 后端已在运行 (PID={pid})")
                print("       如需重启，请先运行: python start_vtuber.py --stop")
                return
        except Exception:
            pass
        PID_FILE.unlink(missing_ok=True)

    print(f"[INFO] 启动 VTuber 后端...")
    print(f"  Python:  {VENV_PYTHON}")
    print(f"  Script:  {run_server}")
    print(f"  CWD:     {VTUBER_DIR}")

    stdout_log = REPO_DIR / "vtuber_stdout.log"
    stderr_log = REPO_DIR / "vtuber_stderr.log"

    if console:
        # 前台运行，输出实时显示（中文 Windows 控制台通常用 GBK）
        import io
        proc = subprocess.Popen(
            [str(VENV_PYTHON), str(run_server)],
            cwd=str(VTUBER_DIR),
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
        )
        # 用 GBK 解码，fallback 到 utf-8
        reader = io.TextIOWrapper(proc.stdout, encoding="gbk", errors="replace")
        print(f"[OK] 已启动 (PID={proc.pid})，实时输出如下（Ctrl+C 停止）：")
        print("-" * 60)
        try:
            for line in reader:
                print(line, end="", flush=True)
        except KeyboardInterrupt:
            print("\n" + "-" * 60)
            print("[INFO] 正在停止...")
            proc.send_signal(signal.CTRL_BREAK_EVENT)
            proc.wait(timeout=5)
            print("[OK] 已停止")
    else:
        # 后台运行，输出重定向到日志文件
        with open(stdout_log, "w", encoding="utf-8") as out, \
             open(stderr_log, "w", encoding="utf-8") as err:
            proc = subprocess.Popen(
                [str(VENV_PYTHON), str(run_server)],
                cwd=str(VTUBER_DIR),
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                stdout=out,
                stderr=err,
            )

        # 保存 PID
        PID_FILE.write_text(str(proc.pid))

        print(f"[OK] 已启动 (PID={proc.pid})")
        print(f"  stdout -> {stdout_log}")
        print(f"  stderr -> {stderr_log}")
        print(f"\n查看日志:  type {stdout_log.name}")
        print(f"停止后端:  python start_vtuber.py --stop")


def stop():
    if not PID_FILE.exists():
        print("[WARN] 未找到 PID 文件，VTuber 后端可能未在运行")
        return

    try:
        pid = int(PID_FILE.read_text().strip())
    except Exception:
        print("[ERR] PID 文件损坏")
        PID_FILE.unlink(missing_ok=True)
        return

    try:
        import psutil
        if not psutil.pid_exists(pid):
            print(f"[INFO] 进程 (PID={pid}) 已不存在")
            PID_FILE.unlink(missing_ok=True)
            return

        proc = psutil.Process(pid)
        children = proc.children(recursive=True)

        # 先停止子进程
        for child in children:
            try:
                child.terminate()
            except Exception:
                pass

        # 停止主进程
        proc.terminate()
        gone, alive = psutil.wait_procs([proc] + children, timeout=5)
        if alive:
            for p in alive:
                try:
                    p.kill()
                except Exception:
                    pass

        PID_FILE.unlink(missing_ok=True)
        print(f"[OK] 已停止 VTuber 后端 (PID={pid})")
    except ImportError:
        # 没有 psutil，用 os.kill
        try:
            os.kill(pid, signal.SIGTERM)
            PID_FILE.unlink(missing_ok=True)
            print(f"[OK] 已停止 VTuber 后端 (PID={pid})")
        except Exception as e:
            print(f"[ERR] 停止失败: {e}")


if __name__ == "__main__":
    if "--stop" in sys.argv:
        stop()
    elif "--console" in sys.argv:
        start(console=True)
    else:
        start(console=False)
