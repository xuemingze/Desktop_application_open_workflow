"""
MCP 连接测试脚本
测试桌面自动化助手 EXE 的 MCP server 是否能正常工作

用法:
    .venv\\Scripts\\python.exe test_mcp_connection.py
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import asyncio
import glob
import os
from pathlib import Path

# 找到最新的 EXE (按修改时间)
exe_files = glob.glob(r"C:\Users\Administrator\Desktop\控制电脑\dist\*.exe")
if not exe_files:
    print("❌ 没有找到 EXE,请先打包: python -m PyInstaller --clean build.spec")
    sys.exit(1)
exe_files = sorted(exe_files, key=lambda f: os.path.getmtime(f), reverse=True)
exe_path = exe_files[0]
print(f"使用最新 EXE: {exe_path}")
print(f"修改时间: {Path(exe_path).stat().st_mtime}")
print("=" * 60)


async def test_mcp():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    server_params = StdioServerParameters(
        command=exe_path,
        args=["--mcp"],
    )

    print("\n[1/5] 启动 stdio 连接...")
    async with stdio_client(server_params) as (read, write):
        print("✅ stdio 连接成功")

        async with ClientSession(read, write) as session:
            print("\n[2/5] 初始化 MCP session...")
            await session.initialize()
            print("✅ 初始化成功")

            print("\n[3/5] 列出工具...")
            tools = await session.list_tools()
            print(f"✅ 工具数: {len(tools.tools)}")
            for tool in tools.tools:
                desc = tool.description or "(无描述)"
                print(f"  - {tool.name}: {desc[:60]}")

            # 测试 list_shortcuts
            print("\n[4/5] 调用 list_shortcuts...")
            try:
                result = await session.call_tool("list_shortcuts", {})
                text = result.content[0].text if result.content else ""
                # 解析 count
                import json
                data = json.loads(text) if text.strip().startswith("{") else {}
                count = data.get("count", "?")
                print(f"✅ 返回 {count} 个快捷方式")
            except Exception as e:
                print(f"❌ 失败: {e}")

            # 测试 list_workflows
            print("\n[5/5] 调用 list_workflows...")
            try:
                result = await session.call_tool("list_workflows", {})
                text = result.content[0].text if result.content else ""
                import json
                data = json.loads(text) if text.strip().startswith("{") else {}
                workflows = data.get("workflows", {})
                print(f"✅ 返回 {len(workflows)} 个工作流: {list(workflows.keys())}")
            except Exception as e:
                print(f"❌ 失败: {e}")

            # 测试 search_local_files
            print("\n[BONUS] 调用 search_local_files (搜 4月货款)...")
            try:
                result = await session.call_tool("search_local_files", {"query": "4月货款 png|jpg|jpeg|bmp"})
                text = result.content[0].text if result.content else ""
                import json
                data = json.loads(text) if text.strip().startswith("{") else {}
                count = data.get("count", 0)
                print(f"✅ 搜到 {count} 个结果")
                for r in data.get("results", [])[:5]:
                    print(f"  - {r.get('name', '?')} (路径: {r.get('path', '?')})")
            except Exception as e:
                print(f"❌ 失败: {e}")

            # 测试 search_local_files 查找 dist 文件夹
            print("\n[BONUS] 调用 search_local_files (查找 dist 文件夹)...")
            try:
                result = await session.call_tool("search_local_files", {
                    "query": "*.exe",
                    "path": r"C:\Users\Administrator\Desktop\控制电脑\dist",
                    "limit": 20
                })
                text = result.content[0].text if result.content else ""
                import json
                data = json.loads(text) if text.strip().startswith("{") else {}
                count = data.get("count", 0)
                print(f"✅ 搜到 {count} 个结果")
                for r in data.get("results", [])[:10]:
                    print(f"  - {r.get('name', '?')} (路径: {r.get('path', '?')})")
            except Exception as e:
                print(f"❌ 失败: {e}")


try:
    asyncio.run(test_mcp())
    print("\n🎉 MCP 测试通过!")
except Exception as e:
    print(f"\n❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()
