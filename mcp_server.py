"""
mcp_server.py - MCP (Model Context Protocol) Server for Open-LLM-VTuber

以 stdio 模式运行，供 Open-LLM-VTuber 作为 MCP Client 连接。

注册工具:
  - list_workflows   : 列出所有工作流
  - run_workflow     : 按名称运行工作流
  - list_shortcuts   : 列出所有快捷键
  - launch_shortcut  : 启动快捷方式
  - search_files     : 搜索文件
  - read_file        : 读取文件内容
  - execute_command  : 执行系统命令
  - get_system_info  : 获取系统信息
"""
import json
import sys
import os
import subprocess
from pathlib import Path

PROTOCOL_VERSION = "2024-11-05"


def jsonrpc_success(req_id, result):
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": result,
    }


def jsonrpc_error(req_id, code, message):
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": code, "message": message},
    }


def list_workflows():
    try:
        wf_path = Path(__file__).parent / "workflows.json"
        if wf_path.exists():
            with open(wf_path, encoding="utf-8") as f:
                data = json.load(f)
            return [{"name": k, **v} for k, v in data.items()]
    except Exception:
        pass
    return []


def run_workflow(name: str):
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from desktop_auto import DesktopAuto
        app = DesktopAuto()
        app.load_workflows()
        for wf_name, wf_data in app.workflows.items():
            if name in (wf_name, wf_data.get("name", "")):
                result = app.run_workflow(name)
                return {"ok": True, "result": str(result)}
        return {"ok": False, "error": f"Workflow '{name}' not found"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def list_shortcuts():
    try:
        from shortcuts import load_shortcuts
        shortcuts = load_shortcuts()
        return [{"name": s.get("name", ""), "key": s.get("key", ""), "description": s.get("description", "")} for s in shortcuts]
    except Exception:
        return []


def launch_shortcut(name: str):
    try:
        from shortcuts import load_shortcuts
        shortcuts = load_shortcuts()
        for sc in shortcuts:
            if sc.get("name") == name or sc.get("key") == name:
                cmd = sc.get("command") or sc.get("script")
                if cmd:
                    subprocess.Popen(cmd, shell=True)
                    return {"ok": True}
        return {"ok": False, "error": f"Shortcut '{name}' not found"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def search_files(query: str, path: str = None):
    import fnmatch
    root = Path(path) if path else Path.home()
    results = []
    try:
        for p in root.rglob("*"):
            if query.lower() in p.name.lower():
                results.append(str(p))
                if len(results) >= 20:
                    break
    except Exception:
        pass
    return results


def read_file(path: str, max_lines: int = 100):
    try:
        p = Path(path)
        if not p.exists():
            return {"ok": False, "error": "File not found"}
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()[:max_lines]
        return {"ok": True, "content": "\n".join(lines), "lines": len(lines)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def execute_command(command: str):
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        return {
            "ok": True,
            "returncode": result.returncode,
            "stdout": result.stdout[:2000],
            "stderr": result.stderr[:1000],
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_system_info():
    import platform
    import datetime
    return {
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "hostname": platform.node(),
        "datetime": datetime.datetime.now().isoformat(),
    }


TOOL_HANDLERS = {
    "list_workflows": list_workflows,
    "run_workflow": lambda name="": run_workflow(name),
    "list_shortcuts": list_shortcuts,
    "launch_shortcut": lambda name="": launch_shortcut(name),
    "search_files": lambda query="", path=None: search_files(query, path),
    "read_file": lambda path="", max_lines=100: read_file(path, max_lines),
    "execute_command": lambda command="": execute_command(command),
    "get_system_info": get_system_info,
}

TOOL_DEFINITIONS = [
    {
        "name": "list_workflows",
        "description": "列出桌面自动化助手所有已配置的工作流名称和描述。返回工作流列表，包含每个工作流的名称、描述和触发条件。",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "run_workflow",
        "description": "按名称运行一个已配置的工作流。工作流会按其定义自动执行一系列桌面操作。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "工作流的完整名称"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "list_shortcuts",
        "description": "列出桌面自动化助手所有快捷键的名称、按键绑定和功能描述。",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "launch_shortcut",
        "description": "通过名称或按键绑定启动一个快捷方式，执行其关联的命令或脚本。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "快捷键的名称或按键绑定（如 'ctrl+shift+a'）"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "search_files",
        "description": "在指定目录（默认用户主目录）下按文件名关键字搜索文件，返回匹配文件的完整路径列表。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键字（文件名包含此字符串，不区分大小写）"},
                "path": {"type": "string", "description": "搜索根目录路径，默认为用户主目录。如：C:\\Users\\Administrator"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "read_file",
        "description": "读取指定文件的文本内容（默认前100行），支持指定最大行数。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件的完整路径，如：C:\\Users\\Administrator\\Desktop\\test.txt"},
                "max_lines": {"type": "integer", "description": "最多读取的行数，默认100行，设为0则读取全部"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "execute_command",
        "description": "在 Windows 系统上执行一条命令行指令（CMD），返回命令的输出内容、返回码和错误信息。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "要执行的 Windows 命令，如：ipconfig、dir C:\\、tasklist"},
            },
            "required": ["command"],
        },
    },
    {
        "name": "get_system_info",
        "description": "获取本地计算机的系统信息，包括操作系统版本、Python版本、主机名和当前日期时间。",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def handle_initialize(params):
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "serverInfo": {"name": "desktop-auto", "version": "1.0"},
        "capabilities": {"tools": {}},
        "tools": [
            {
                "name": "list_workflows",
                "description": "列出桌面自动化助手所有工作流",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "run_workflow",
                "description": "按名称运行工作流",
                "inputSchema": {
                    "type": "object",
                    "properties": {"name": {"type": "string", "description": "工作流名称"}},
                    "required": ["name"],
                },
            },
            {
                "name": "list_shortcuts",
                "description": "列出所有快捷键",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "launch_shortcut",
                "description": "启动快捷方式",
                "inputSchema": {
                    "type": "object",
                    "properties": {"name": {"type": "string", "description": "快捷键名称"}},
                    "required": ["name"],
                },
            },
            {
                "name": "search_files",
                "description": "搜索文件",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "path": {"type": "string"},
                    },
                },
            },
            {
                "name": "read_file",
                "description": "读取文件内容",
                "inputSchema": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}, "max_lines": {"type": "integer"}},
                    "required": ["path"],
                },
            },
            {
                "name": "execute_command",
                "description": "执行系统命令",
                "inputSchema": {
                    "type": "object",
                    "properties": {"command": {"type": "string"}},
                    "required": ["command"],
                },
            },
            {
                "name": "get_system_info",
                "description": "获取系统信息",
                "inputSchema": {"type": "object", "properties": {}},
            },
        ],
    }


def handle_tools_list():
    return TOOL_DEFINITIONS


def handle_tool_call(name, arguments):
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        return jsonrpc_error(None, -32601, f"Unknown tool: {name}")
    try:
        result = handler(**arguments) if arguments else handler()
        return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}
    except TypeError as e:
        return jsonrpc_error(None, -32602, f"Invalid arguments for {name}: {e}")
    except Exception as e:
        return jsonrpc_error(None, -32603, f"Tool error: {e}")


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue

        method = msg.get("method", "")
        req_id = msg.get("id")
        params = msg.get("params", {})

        if method == "initialize":
            result = handle_initialize(params)
            print(json.dumps(jsonrpc_success(req_id, result)), flush=True)

        elif method == "notifications/initialized":
            pass

        elif method == "tools/list":
            tools = handle_tools_list()
            print(json.dumps(jsonrpc_success(req_id, {"tools": tools})), flush=True)

        elif method == "tools/call":
            name = params.get("name", "")
            arguments = params.get("arguments", {}) or {}
            result = handle_tool_call(name, arguments)
            if "error" in result:
                print(json.dumps(result), flush=True)
            else:
                print(json.dumps(jsonrpc_success(req_id, result)), flush=True)

        else:
            if req_id is not None:
                print(json.dumps(jsonrpc_error(req_id, -32601, f"Unknown method: {method}")), flush=True)


if __name__ == "__main__":
    main()
