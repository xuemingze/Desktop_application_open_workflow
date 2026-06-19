"""
嵌入式 MCP Server - 集成到主程序,不阻塞 GUI
基于 workflow_mcp_server.py 的逻辑,但用 QThread 包装
"""
import asyncio
import json
import subprocess
import time
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QThread, Signal

# MCP SDK - 顶层 import 让 PyInstaller 一定能打包
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
HAS_MCP = True

# 导入工作流执行器
import sys
sys.path.insert(0, str(Path(__file__).parent))
from workflow_panel import StepExecutor
from mcp_file_tools import FILE_TOOL_NAMES, FILE_TOOL_SCHEMAS, handle_file_tool

# 工作流文件路径: 优先使用主程序解析后的 USER_DATA_DIR；项目目录作为冷备。
def _resolve_workflows_file() -> Path:
    try:
        from data_paths import USER_DATA_DIR
        user_path = USER_DATA_DIR / "workflows.json"
    except Exception:
        user_path = Path.home() / "桌面自动化助手" / "workflows.json"
    # MCP 必须与 GUI 使用同一个数据目录；不要再回退到 exe/源码同级 workflows.json。
    return user_path

WORKFLOWS_FILE = _resolve_workflows_file()


def scan_desktop_shortcuts() -> list[dict]:
    """扫描桌面所有 .lnk 快捷方式"""
    try:
        from winreg import HKEY_CURRENT_USER, OpenKey, QueryValueEx
        with OpenKey(
            HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
        ) as k:
            desktop = Path(QueryValueEx(k, "Desktop")[0])
    except Exception:
        desktop = Path.home() / "Desktop"

    results = []
    if not desktop.exists():
        return results
    for lnk in desktop.glob("*.lnk"):
        try:
            import win32com.client
            shell = win32com.client.Dispatch('WScript.Shell')
            shortcut = shell.CreateShortCut(str(lnk))
            target = shortcut.TargetPath
            work_dir = shortcut.WorkingDirectory
            results.append({
                "name": lnk.stem,
                "lnk_path": str(lnk),
                "target": target,
                "work_dir": work_dir,
                "exists": Path(target).exists() if target else False,
            })
        except Exception as e:
            results.append({
                "name": lnk.stem,
                "lnk_path": str(lnk),
                "target": "",
                "work_dir": "",
                "exists": False,
                "error": str(e),
            })
    return results


def load_workflows() -> dict[str, dict]:
    # 每次调用重新解析，避免 启动时 GUI 还未迁移完成的竞Race
    workflows_file = _resolve_workflows_file()
    if not workflows_file.exists():
        return {}
    try:
        return json.loads(workflows_file.read_text(encoding="utf-8"))
    except Exception as e:
        return {"_error": str(e)}


def run_workflow_sync(name: str, log_func=None) -> dict:
    """同步执行工作流"""
    def default_log(msg):
        if log_func:
            log_func(msg)
    wfs = load_workflows()
    wf = wfs.get(name)
    if not wf:
        return {"ok": False, "error": f"工作流不存在: {name}"}
    steps = wf.get("steps", [])
    success = 0
    total = len([s for s in steps if s.get("enabled", True)])
    for i, step in enumerate(steps):
        if not step.get("enabled", True):
            continue
        default_log(f"[{i+1}/{total}] {step.get('name', step.get('type', ''))}")
        if StepExecutor.execute(step, default_log):
            success += 1
    return {
        "ok": success == total,
        "success": success,
        "total": total,
        "workflow": name,
    }


def launch_shortcut_sync(name: str) -> dict:
    """启动指定快捷方式"""
    shortcuts = scan_desktop_shortcuts()
    sc = next((s for s in shortcuts if s["name"].lower() == name.lower()), None)
    if not sc:
        return {"ok": False, "error": f"未找到快捷方式: {name}"}
    if not sc.get("target") or not Path(sc["target"]).exists():
        return {"ok": False, "error": f"目标不存在: {sc.get('target', '')}"}
    try:
        proc = subprocess.Popen(
            [sc["target"]],
            cwd=sc.get("work_dir") or str(Path(sc["target"]).parent),
            creationflags=0x08000000,
        )
        return {"ok": True, "name": sc["name"], "target": sc["target"], "pid": proc.pid}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ============================================================
# 嵌入式 MCP Server (后台 QThread)
# ============================================================
class MCPEmbeddedServer(QThread):
    """在后台运行 MCP server,不阻塞 GUI"""

    log_signal = Signal(str)
    status_signal = Signal(bool, str)  # (running, message)

    def __init__(self):
        super().__init__()
        self._server: Optional[Server] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._running = False

    def stop(self):
        self._running = False
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)

    def run(self):
        if not HAS_MCP:
            self.log_signal.emit("❌ MCP SDK 未安装: pip install mcp")
            self.status_signal.emit(False, "MCP SDK 未安装")
            return

        # 打包后 (frozen GUI 模式) 重新绑定 stdin/stdout,避免 sys.stdin 为 None
        # 从文件描述符 0/1 重建
        if getattr(__import__('sys'), 'frozen', False):
            import sys as _sys
            try:
                if _sys.stdin is None or not hasattr(_sys.stdin, 'buffer'):
                    try:
                        _sys.stdin = open(0, 'r', encoding='utf-8', buffering=1)
                    except Exception:
                        pass
                if _sys.stdout is None or not hasattr(_sys.stdout, 'buffer'):
                    try:
                        _sys.stdout = open(1, 'w', encoding='utf-8', buffering=1)
                    except Exception:
                        pass
            except Exception:
                pass

        try:
            self._running = True
            self.status_signal.emit(True, "MCP server 启动中...")
            self.log_signal.emit("🚀 MCP server 启动中...")

            # 在新事件循环中运行
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._serve())

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self.log_signal.emit(f"❌ MCP server 异常: {e}\n{tb}")
            self.status_signal.emit(False, str(e))
        finally:
            self.status_signal.emit(False, "已停止")
            self.log_signal.emit("⏹ MCP server 已停止")

    async def _serve(self):
        """启动 MCP stdio server"""
        server = Server("desktop-auto-embedded")
        self._server = server

        @server.list_tools()
        async def list_tools() -> list[Tool]:
            tools = [
                Tool(
                    name="list_workflows",
                    description="列出所有可用的工作流",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "可选,指定工作流名返回详情"}
                        },
                    },
                ),
                Tool(
                    name="list_shortcuts",
                    description="列出桌面所有 .lnk 快捷方式",
                    inputSchema={"type": "object", "properties": {}},
                ),
                Tool(
                    name="run_workflow",
                    description="执行指定名称的工作流",
                    inputSchema={
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                        "required": ["name"],
                    },
                ),
                Tool(
                    name="launch_shortcut",
                    description="直接启动桌面上的一个快捷方式",
                    inputSchema={
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                        "required": ["name"],
                    },
                ),
                Tool(
                    name="search_local_files",
                    description="极速本地文件搜索 (基于 Everything,毫秒级全盘扫描)。"
                                "支持语法: *.py / ext:md RAG / size:>10MB / dm:today / '完整名'",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Everything 搜索语法,例如: '*.py', 'ext:md RAG', 'size:>10MB'",
                            },
                            "limit": {
                                "type": "integer",
                                "description": "返回数量上限 (默认 50,最大 10000)",
                                "default": 50,
                            },
                            "path": {
                                "type": "string",
                                "description": "限定搜索目录 (可选),例如 'C:\\\\Users\\\\'",
                            },
                            "sort": {
                                "type": "string",
                                "description": "排序: date_modified_desc / date_modified_asc / "
                                                "name_asc / name_desc / size_desc / size_asc / "
                                                "path_asc / path_desc / extension_asc / extension_desc",
                                "default": "date_modified_desc",
                            },
                        },
                        "required": ["query"],
                    },
                ),
            ]
            for schema in FILE_TOOL_SCHEMAS:
                tools.append(Tool(
                    name=schema["name"],
                    description=schema["description"],
                    inputSchema=schema["inputSchema"],
                ))
            return tools

        @server.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[TextContent]:
            try:
                if name in FILE_TOOL_NAMES:
                    result = handle_file_tool(name, arguments, log_cb=self.log_signal.emit)
                    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

                if name == "list_workflows":
                    wfs = load_workflows()
                    target = arguments.get("name", "")
                    if target:
                        wf = wfs.get(target)
                        if not wf:
                            return [TextContent(type="text", text=json.dumps(
                                {"ok": False, "error": f"工作流不存在: {target}"},
                                ensure_ascii=False))]
                        return [TextContent(type="text", text=json.dumps(
                            {"ok": True, "workflow": wf}, ensure_ascii=False, indent=2))]
                    summary = {n: {"description": wf.get("description", ""), "step_count": len(wf.get("steps", []))} for n, wf in wfs.items()}
                    return [TextContent(type="text", text=json.dumps(
                        {"ok": True, "workflows": summary}, ensure_ascii=False, indent=2))]

                elif name == "list_shortcuts":
                    scs = scan_desktop_shortcuts()
                    return [TextContent(type="text", text=json.dumps(
                        {"ok": True, "count": len(scs), "shortcuts": scs}, ensure_ascii=False, indent=2))]

                elif name == "run_workflow":
                    n = arguments.get("name", "")
                    if not n:
                        return [TextContent(type="text", text=json.dumps(
                            {"ok": False, "error": "缺少 name"}, ensure_ascii=False))]
                    logs = []
                    result = run_workflow_sync(n, logs.append)
                    result["logs"] = logs
                    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

                elif name == "launch_shortcut":
                    n = arguments.get("name", "")
                    if not n:
                        return [TextContent(type="text", text=json.dumps(
                            {"ok": False, "error": "缺少 name"}, ensure_ascii=False))]
                    result = launch_shortcut_sync(n)
                    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

                elif name == "search_local_files":
                    q = arguments.get("query", "").strip()
                    if not q:
                        return [TextContent(type="text", text=json.dumps(
                            {"ok": False, "error": "缺少 query"}, ensure_ascii=False))]
                    limit = min(int(arguments.get("limit", 50)), 10000)
                    path = arguments.get("path", "").strip()
                    sort = arguments.get("sort", "date_modified_desc")

                    try:
                        from search_panel import SecureStore, EverythingConfig, EverythingHTTP
                        store = SecureStore("desktop_auto")
                        user = store.load("everything_http_user") or ""
                        pwd = store.load("everything_http_pass") or ""
                        cfg = EverythingConfig(port=16259, username=user, password=pwd)
                        backend = EverythingHTTP(cfg)
                        results = backend.search(q, limit=limit, path=path, sort=sort)
                        return [TextContent(type="text", text=json.dumps(
                            {"ok": True, "query": q, "count": len(results),
                             "results": [
                                {"name": r.name, "path": r.path, "full_path": r.full_path,
                                 "size": r.size, "type": r.type,
                                 "date_modified": r.date_modified, "extension": r.extension}
                                for r in results
                             ]},
                            ensure_ascii=False, indent=2))]
                    except Exception as e:
                        return [TextContent(type="text", text=json.dumps(
                            {"ok": False, "error": str(e),
                             "hint": "请先在桌面助手 -> 🔍文件搜索 -> 🔧设置 里配置 Everything HTTP"},
                            ensure_ascii=False))]

                else:
                    return [TextContent(type="text", text=json.dumps(
                        {"ok": False, "error": f"未知工具: {name}"}, ensure_ascii=False))]
            except Exception as e:
                return [TextContent(type="text", text=json.dumps(
                    {"ok": False, "error": str(e)}, ensure_ascii=False))]

        # 用 stdio 通信
        async with stdio_server() as (read_stream, write_stream):
            self.log_signal.emit("✅ MCP server 正在运行 (stdio)")
            self.status_signal.emit(True, "MCP server 正在运行")
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )


# 单例: 主 GUI 启动时也启动一个
_global_mcp_server: Optional[MCPEmbeddedServer] = None


def start_global_mcp_server() -> Optional[MCPEmbeddedServer]:
    """启动全局 MCP server (供 GUI 调用)"""
    global _global_mcp_server
    if _global_mcp_server is not None and _global_mcp_server.isRunning():
        return _global_mcp_server
    if not HAS_MCP:
        return None
    _global_mcp_server = MCPEmbeddedServer()
    _global_mcp_server.start()
    return _global_mcp_server


def stop_global_mcp_server():
    global _global_mcp_server
    if _global_mcp_server is not None:
        _global_mcp_server.stop()
        _global_mcp_server.wait(2000)
        _global_mcp_server = None
