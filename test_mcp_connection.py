"""用 mcp SDK 测试 MCP 通信"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import asyncio
import glob
from pathlib import Path

# 找到最新的 EXE (按修改时间)
import os
exe_files = glob.glob(r"C:\Users\Administrator\Desktop\控制电脑\dist\*.exe")
exe_files = sorted(exe_files, key=lambda f: os.path.getmtime(f), reverse=True)
print(f"找到 EXE: {len(exe_files)} 个")
for f in exe_files:
    print(f"  - {f} (修改: {os.path.getmtime(f)})")

exe_path = exe_files[0]
print(f"\n使用最新 EXE: {exe_path}")

async def test_mcp():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    
    server_params = StdioServerParameters(
        command=exe_path,
        args=["--mcp"],
    )
    
    print("\n[1/4] 启动 stdio 连接...")
    async with stdio_client(server_params) as (read, write):
        print("✅ stdio 连接成功")
        
        async with ClientSession(read, write) as session:
            print("\n[2/4] 初始化 MCP session...")
            await session.initialize()
            print("✅ 初始化成功")
            
            print("\n[3/4] 列出工具...")
            tools = await session.list_tools()
            print(f"✅ 工具数: {len(tools.tools)}")
            for tool in tools.tools:
                print(f"  - {tool.name}: {tool.description[:80] if tool.description else '(无描述)'}")
            
            print("\n[4/4] 调用 list_shortcuts...")
            try:
                result = await session.call_tool("list_shortcuts", {})
                print(f"✅ 调用成功")
                for content in result.content:
                    if hasattr(content, 'text'):
                        print(f"  返回: {content.text[:200]}")
            except Exception as e:
                print(f"❌ 调用失败: {e}")
            
            print("\n调用 list_workflows...")
            try:
                result = await session.call_tool("list_workflows", {})
                print(f"✅ 调用成功")
                for content in result.content:
                    if hasattr(content, 'text'):
                        print(f"  返回: {content.text[:200]}")
            except Exception as e:
                print(f"❌ 调用失败: {e}")
            
            print("\n查找 4月明细 文件...")
            try:
                result = await session.call_tool("search_local_files", {"query": "4月明细"})
                print(f"✅ 搜索成功")
                for content in result.content:
                    if hasattr(content, 'text'):
                        print(f"  结果: {content.text[:800]}")
            except Exception as e:
                print(f"❌ 搜索失败: {e}")

try:
    asyncio.run(test_mcp())
    print("\n🎉 MCP 测试通过！")
except Exception as e:
    print(f"\n❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()
