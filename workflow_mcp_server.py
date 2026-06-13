"""
工作流 MCP Server
为 AI 提供标准化的工具接口,让 AI 可以:
- 列出所有工作流
- 列出桌面快捷方式
- 启动工作流
- 启动快捷方式
"""
import asyncio
import json
import subprocess
import time
from pathlib import Path
from typing import Any

# MCP SDK
try:
    from mcp.server import Server
    from mcp.types import Tool, TextContent
    from mcp.server.stdio import stdio_server
except ImportError:
    print("请先安装 MCP SDK: pip install mcp")
    raise

# 导入工作流执行器
import sys
sys.path.insert(0, str(Path(__file__).parent))
from workflow_panel import StepExecutor

WORKFLOWS_FILE = Path(__file__).parent / "workflows.json"

# 扫描桌面快捷方式
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
    """加载所有工作流"""
    if not WORKFLOWS_FILE.exists():
        return {}
    try:
        return json.loads(WORKFLOWS_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        return {"_error": str(e)}


def get_workflow_steps(name: str) -> list[dict]:
    """获取指定工作流的步骤"""
    wfs = load_workflows()
    wf = wfs.get(name)
    if not wf:
        return []
    return wf.get("steps", [])


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
    """启动指定快捷方式(直接 Popen 方式)"""
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
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )
        return {
            "ok": True,
            "name": sc["name"],
            "target": sc["target"],
            "pid": proc.pid,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ============================================================
# MCP Server
# ============================================================
server = Server("desktop-auto-workflow")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """注册所有工具"""
    return [
        Tool(
            name="list_workflows",
            description="列出所有可用的工作流及其步骤",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "可选,指定工作流名返回详细步骤;不传则列出所有工作流名",
                    }
                },
            },
        ),
        Tool(
            name="list_shortcuts",
            description="列出桌面所有 .lnk 快捷方式,包含名称、目标路径、是否可启动",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="run_workflow",
            description="执行指定名称的工作流(所有步骤按顺序执行)",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "工作流名称(必须先用 list_workflows 查到)",
                    }
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="launch_shortcut",
            description="直接启动桌面上的一个快捷方式(类似双击图标)",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "快捷方式名称(不含 .lnk 后缀)",
                    }
                },
                "required": ["name"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """处理工具调用"""
    try:
        if name == "list_workflows":
            wfs = load_workflows()
            target_name = arguments.get("name", "")
            if target_name:
                wf = wfs.get(target_name)
                if not wf:
                    return [TextContent(type="text", text=json.dumps(
                        {"ok": False, "error": f"工作流不存在: {target_name}"},
                        ensure_ascii=False
                    ))]
                return [TextContent(type="text", text=json.dumps(
                    {"ok": True, "workflow": wf}, ensure_ascii=False, indent=2
                ))]
            else:
                # 列出所有
                summary = {n: {"description": wf.get("description", ""), "step_count": len(wf.get("steps", []))} for n, wf in wfs.items()}
                return [TextContent(type="text", text=json.dumps(
                    {"ok": True, "workflows": summary}, ensure_ascii=False, indent=2
                ))]

        elif name == "list_shortcuts":
            scs = scan_desktop_shortcuts()
            return [TextContent(type="text", text=json.dumps(
                {"ok": True, "count": len(scs), "shortcuts": scs}, ensure_ascii=False, indent=2
            ))]

        elif name == "run_workflow":
            wf_name = arguments.get("name", "")
            if not wf_name:
                return [TextContent(type="text", text=json.dumps(
                    {"ok": False, "error": "缺少 name 参数"}, ensure_ascii=False
                ))]
            logs = []
            def log_collector(msg):
                logs.append(str(msg))
            result = run_workflow_sync(wf_name, log_collector)
            result["logs"] = logs
            return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

        elif name == "launch_shortcut":
            sc_name = arguments.get("name", "")
            if not sc_name:
                return [TextContent(type="text", text=json.dumps(
                    {"ok": False, "error": "缺少 name 参数"}, ensure_ascii=False
                ))]
            result = launch_shortcut_sync(sc_name)
            return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

        else:
            return [TextContent(type="text", text=json.dumps(
                {"ok": False, "error": f"未知工具: {name}"}, ensure_ascii=False
            ))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps(
            {"ok": False, "error": str(e)}, ensure_ascii=False
        ))]


async def main():
    """启动 MCP server"""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
