# 桌面自动化助手 (Desktop Auto Assistant)

<div align="center">
  <img src="app_icon_512_v2.png" width="128" height="128" alt="Logo"/>
</div>

> 基于 PySide6 的 Windows 桌面自动化工具,支持**直接启动**、**后台点击**、**图像识别**、**坐标点击**和**自定义工作流**。内置 **MCP (Model Context Protocol) Server**,可被任何 AI 客户端调用。

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey.svg)](https://www.microsoft.com/windows)
[![MCP](https://img.shields.io/badge/MCP-Compatible-green.svg)](https://modelcontextprotocol.io/)
[![PySide6](https://img.shields.io/badge/GUI-PySide6-orange.svg)](https://www.qt.io/qt-for-python)

## ✨ 核心特性

- 🚀 **多种启动模式**: 直接启动 (Popen) / 后台双击 / Shell / 图像识别 / 坐标点击
- 🔄 **工作流系统**: 多步骤任务编排,支持截图模板匹配、按键、坐标点击、等待
- 🤖 **MCP 集成**: 标准 Model Context Protocol Server,AI 客户端可调用
- 🎯 **智能坐标捕捉**: 自动隐藏 GUI、Win+D 显示桌面、3秒倒计时、坐标回填
- 🖼️ **纯 PIL 模板匹配**: 不依赖 OpenCV(某些环境缺 DLL 也能跑)
- 📦 **零侵入**: 解析 .lnk 快捷方式,无需预先配置

## 📸 界面预览

```
┌─────────────────────────────────────────────────────────────┐
│  [🚀 快速启动]  [🔄 工作流]                                │
│  ┌─────────────┐  ┌────────────────────────────────────┐  │
│  │ 快捷方式列表 │  │ 目标信息: MiniMax Code             │  │
│  │ • AiPyPro    │  │ 启动方式: [🚀] [🖱️] [⚙️] [📸]    │  │
│  │ • MobaXterm  │  │ 模板: 无                          │  │
│  │ • MiniMax    │  │ 🎯 坐标点击组:                    │  │
│  │             │  │   X:[1754] Y:[ 287] [双击 ▼]     │  │
│  │             │  │   [🎯 捕捉坐标]                   │  │
│  │             │  │   [▶ 执行] [⏹ 停止]              │  │
│  └─────────────┘  └────────────────────────────────────┘  │
│  操作日志:                                                  │
│  [14:30] 🚀 直接启动: MiniMax Code                          │
│  [14:30] ✅ 进程已运行 1.5s+                                │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install PySide6 pyautogui pillow pyperclip pywinauto psutil pywin32 mcp
```

### 2. 启动 GUI

双击 `start.bat` 或 `start.ps1`,或在终端运行:

```bash
python desktop_auto.py
```

### 3. 启动 MCP Server (给 AI 用)

**方式 A: GUI 内启动 (推荐)**
在 GUI 中点击「启动 MCP Server」按钮,后台会启动一个嵌入式 MCP server。

**方式 B: 作为独立进程启动**
```bash
python desktop_auto.py --mcp
```

**方式 C: 使用打包后的 EXE**
```bash
"桌面自动化助手.exe" --mcp
```

## 🤖 MCP 客户端接入

### Claude Desktop / Cursor / Cline 配置

编辑 MCP 配置文件 (例 `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "desktop-auto": {
      "command": "C:\\path\\to\\.venv\\Scripts\\python.exe",
      "args": ["C:\\path\\to\\dist\\桌面自动化助手.exe", "--mcp"]
    }
  }
}
```

详见 `mcp_config_example.json`。

### MCP 工具列表

| 工具 | 描述 |
|------|------|
| `list_workflows` | 列出所有工作流(可指定 name 返回详情) |
| `list_shortcuts` | 列出桌面所有 .lnk 快捷方式 |
| `run_workflow` | 执行指定工作流(返回步骤日志) |
| `launch_shortcut` | 直接启动桌面快捷方式(类似双击) |

### AI 对话示例

> 用户: "列出我的工作流"
> AI: 调用 `list_workflows()`,返回 `{"zzz日常": {...}}`

> 用户: "运行 zzz日常"
> AI: 调用 `run_workflow(name="zzz日常")`,返回 3/3 步骤成功

> 用户: "打开 MiniMax"
> AI: 调用 `launch_shortcut(name="MiniMax")`,启动 MiniMax

## 📁 项目结构

```
控制电脑/
├── desktop_auto.py          # 主 GUI 程序
├── workflow_panel.py        # 工作流编辑面板
├── mcp_embedded.py          # 嵌入式 MCP server 模块
├── image_match.py           # 纯 PIL 模板匹配
├── workflows.json           # 工作流配置 (自动生成)
├── samples/                 # 模板图片目录
├── mcp_config_example.json  # MCP 客户端配置示例
├── start.bat / start.ps1    # 启动脚本
├── README.md
├── LICENSE                  # MIT
└── .gitignore
```

## 🎯 4 种启动模式详解

### 1. 🚀 直接启动 (Popen) — 最稳定

解析 `.lnk` 快捷方式 → 拿到 `TargetPath` → `subprocess.Popen` 启动目标 exe。

### 2. 🖱️ 鼠标双击桌面图标 — 最通用

IShellFolder 枚举桌面 → 定位 ListView 控件 → `SendMessage` 发送 `WM_LBUTTONDBLCLK` 消息(完全后台点击)。

### 3. ⚙️ Shell 启动 — 特殊场景

`cmd /c start "" "target.exe"` 启动,适合需要 cmd 环境的应用。

### 4. 📸 图像识别点击 / 坐标点击 — 兜底

- **图像识别**: 用户截图保存到 `samples/`,匹配后点击
- **坐标点击**: 用户在 GUI 中「捕捉坐标」,执行时按 `Win+D` 显示桌面后在指定坐标点击

## 🔄 工作流步骤类型

| 步骤 | 功能 | 关键参数 |
|------|------|---------|
| `launch_app` | 启动软件 | path |
| `wait` | 等待 N 秒 | seconds |
| `click_image` | 截图匹配后点击 | template, confidence, click_type |
| `key_press` | 按键输入 | keys (支持组合键如 `ctrl+c`) |
| `click_coords` | 坐标点击 | x, y, click_type (left_single/left_double/right_single) |

## 🔧 技术亮点

### 1. 纯 PIL 模板匹配

不依赖 OpenCV (某些 venv 环境的 OpenCV wheel 缺 `opencv_imgcodecs` DLL),使用 NCC (归一化互相关) 算法。

### 2. 后台 SendMessage 点击

直接给 `SysListView32` 窗口发送 Windows 消息,完全不影响前台焦点。

### 3. 智能窗口激活

```python
self.show()              # 显示
self.showNormal()        # 恢复(防最小化)
self.raise_()            # 提到 Z 序最前
self.activateWindow()    # 获取焦点 (Windows 上关键)
```

## 📦 打包为 exe

项目支持一键打包，打包后**不会覆盖历史版本**，而是以 tag 化命名保存：

```bash
# 默认: 用当天日期作为 tag
build.bat           # 或: .\build.ps1

# 指定日期
build.bat 2026.07.15

# 指定日期+时间 (同日多次打包避免冲突)
build.bat 2026.07.15 14:30

# 仅重命名现有产物 (跳过 PyInstaller)
.\build.ps1 -Date 2026.07.15 -NoBuild
```

输出文件名格式：
```
dist/
├── 桌面自动化助手-v2026.06.14.exe        # 首次
├── 桌面自动化助手-v2026.06.14-2051.exe   # 同日第 2 次
└── 桌面自动化助手-v2026.06.15.exe        # 次日
```

打包脚本会自动：
- 清理 `build/` 临时目录
- 保留 `dist/` 全部历史版本（不覆盖）
- 询问是否同步最新版本到桌面

## 🐛 修复记录

| # | 问题 | 修复 |
|---|------|------|
| 1 | ListView 永远找不到 | 嵌套函数 `global` 作用域 bug → 改用 dict 容器 |
| 2 | `ShortcutInfo.path` 字段名错 | 改为 `lnk_path` |
| 3 | 进程名查找失败 | 解析 .lnk 拿真实 exe 名 |
| 4 | A 段成功后重复调用 C 段 | 直接 return |
| 5 | GUI 窗口挡住图标 | 改 SendMessage 后台点击 + Win+D |
| 6 | OpenCV 读不到 PNG | 模板匹配改用纯 PIL + NCC |
| 7 | NCC 分数低(0.4) | 阈值降至 5% |
| 8 | 步骤无法保存/删除 | 用 `self._current_workflow` 记住当前工作流 |
| 9 | 中文路径 OpenCV 报错 | 截图文件名改纯英文 |
| 10 | 坐标点击参数没传到 worker | LaunchWorker 接受 `coord` 参数 |
| 11 | 捕捉坐标后 GUI 不在前台 | showNormal + setWindowState + raise_ + activateWindow |
| 12 | OpenCV 缺 imgcodecs DLL | 整个模板匹配模块改纯 PIL |

## 📦 依赖

```
PySide6>=6.0
pyautogui>=0.9
Pillow>=9.0
pyperclip>=1.8
pywinauto>=0.6
psutil>=5.9
pywin32>=300
mcp>=1.0  # 可选,仅 MCP server 需要
```

## 🤝 贡献

欢迎 PR 和 Issue!

## 📄 许可证

[MIT](LICENSE)
