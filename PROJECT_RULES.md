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

## 数据目录

所有运行时数据统一存放在 **用户根目录/桌面自动化助手/** 下，通过 `USER_DATA_DIR` 引用：

```python
from pathlib import Path
USER_DATA_DIR = Path.home() / "桌面自动化助手"
USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
```

| 文件 | 说明 |
|------|------|
| `shortcut_meta.json` | 快捷方式绑定元数据（启动模式+坐标）|
| `workflows.json` | 工作流配置 |
| `samples/` | 截图模板图片 |
| `custom_apps.json` | 自定义应用列表 |
| `window_state.json` | GUI 窗口状态 |

## 截图工具规则

- 截图时**先 Win+D** 最小化所有窗口，露出干净桌面
- `SnippingWindow` 在 `showEvent` 中延迟截屏（不在 `__init__`），确保桌面已渲染
- 截图文件命名：`{快捷方式名}_{索引}.png`，**覆盖同名文件，不加时间戳**

## 桌面点击流程（鼠标双击桌面图标模式）

**三级降级策略**（B → B' → A/C）：
1. **B 段**：多尺度图像匹配（0.5x~2.0x，含 0.8x/125% DPI），阈值 0.35
2. **B' 段**：UI/sc 绑定坐标兜底，X>0 或 Y>0 时直接用
3. **A/C 段**：IShellFolder API + 网格估算，作为最后兜底

点击前 Win+D，点击后恢复前台窗口（`ShowWindow + SetForegroundWindow`）。

## 进程管理规则

**杀 GUI 时绝不能用 `taskkill /IM pythonw.exe`**（会误杀所有 Python）。

正确做法：按窗口标题精确匹配，只杀桌面自动化助手进程：
```python
# PowerShell
Get-Process | Where-Object {$_.ProcessName -match 'python' -and $_.MainWindowTitle -match '\u81ea\u52a8|Desktop'} | Stop-Process -Force
```

## 快捷方式绑定元数据

`ShortcutInfo` 有三个额外字段用于绑定：
- `launch_mode: str` — 绑定的启动模式（desktop/direct/shell/image/coord）
- `_coord_x: int` — 绑定坐标 X
- `_coord_y: int` — 绑定坐标 Y
- `_click_type: str` — 绑定点击类型（left_double/left_single/right_single）

绑定键：快捷方式用 `lnk_path`，自定义应用用 `target::target_path`。
持久化文件：`~/桌面自动化助手/shortcut_meta.json`
