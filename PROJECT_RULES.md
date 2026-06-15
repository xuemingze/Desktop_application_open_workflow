# 项目规则 (Project Rules)

> 这些规则在 OpenClaw 不可改文件 (SOUL.md / AGENTS.md) **之外**,作为项目级约定

## 编码规则

### Windows 平台强制 UTF-8
**所有 Python 脚本 (含 PySide6 GUI、launcher、CLI) 在 Windows 上必须强制 UTF-8 输出**,否则 GBK 编码会导致 Unicode 字符(emoji、中文标点等) 崩溃。

```python
import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
```

**位置:** 任何打印 Unicode 字符的脚本**最开头**就加这段。

## PyInstaller 规则

### EXE 路径不要假设
PyInstaller EXE 运行时 `__file__` 指向临时解压目录,不是 EXE 所在目录。

```python
import sys
from pathlib import Path
if getattr(sys, 'frozen', False):
    RUNTIME_DIR = Path(sys.executable).parent
else:
    RUNTIME_DIR = Path(__file__).parent
```

### mcp 包打包需要 typer
mcp SDK 需要 `typer` 才能 import。如果 `typer` 缺失,PyInstaller 会跳过整个 mcp 包,导致运行时 `ModuleNotFoundError: No module named 'mcp'`。

**解决:** `.venv/Scripts/python.exe -m pip install typer`

## Git 规则

### 备份优先
代码改动前先 `python backup.py` 创建快照。
- `python backup.py --restore snapshot_xxx` 回滚
- `python backup.py --clean` 整理(只在用户说"整理"时)

### 工作流
- **每改一次** → 备份 → 测试 → 提交
- **大改动** → 先备份 → 小步迭代 → 每个功能独立提交
- **失败回滚** → 恢复上一个 snapshot → 重新尝试

## Launcher 规则

- `launcher.py` 是命令行启动器 (start / stop / status)
- `launcher_menu.py` 是 GUI 启动菜单 (弹对话框)
- 桌面快捷方式**只创建一个**(`桌面助手.lnk`)→ 指向 `launcher_menu.py`
- 多个快捷方式会让用户混淆

## MCP 规则

- EXE 启动参数: `桌面自动化助手.exe --mcp` 启动 MCP stdio server
- 5 个工具: `list_workflows` / `list_shortcuts` / `run_workflow` / `launch_shortcut` / `search_local_files`
- `search_local_files` 需要本机安装并运行 Everything (HTTP server 关闭鉴权或提供凭据)

## GUI 架构

- 主窗口: `desktop_auto.py` (含快速启动、工作流、设置等 tab)
- 工作流面板: `workflow_panel.py` (独立模块,通过 import 加载)
- 文件搜索: `search_panel.py` (独立模块,只用到 Everything HTTP)
- MCP: 启动子进程 `--mcp` 模式,GUI 和 stdio 分离
