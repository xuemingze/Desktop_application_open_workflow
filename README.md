# 桌面自动化助手 (Desktop Auto Assistant)

<div align="center">
  <img src="app_icon_512_v2.png" width="128" height="128" alt="Logo"/>
</div>

> 基于 PySide6 的 Windows 桌面自动化工具，支持**直接启动**、**后台点击**、**图像识别**、**捕捉坐标点击**和**自定义工作流**。内置 **MCP (Model Context Protocol) Server**，可被 AI 客户端调用。支持后台任务栏运行，开机自启。

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey.svg)](https://www.microsoft.com/windows)
[![PySide6](https://img.shields.io/badge/GUI-PySide6-orange.svg)](https://www.qt.io/qt-for-python)

---

## ✨ 核心特性

- 🚀 **多种启动模式**：直接启动 / 后台双击 / Shell / 捕捉坐标点击 / 图像匹配
- 🔗 **启动方式绑定**：每个快捷方式可绑定专属启动方式 + 坐标，持久化到 `shortcut_meta.json`
- 📍 **捕捉坐标点击**：Win+D 显示干净桌面 → 多尺度图像匹配 → 模拟鼠标双击 → 恢复前台窗口
- 🔄 **工作流系统**：多步骤任务编排，支持截图模板匹配、按键、坐标点击、等待
- 🤖 **MCP 集成**：标准 Model Context Protocol Server，AI 客户端可调用
- 🗂️ **数据目录**：工作流、配置、模板统一存在 `用户根目录/桌面自动化助手/` 下
- ⚙️ **工具 → 系统设置**：开机启动 / 快捷方式管理 / 显示隐藏日志 / MCP 开关
- 🧩 **系统托盘**：可最小化到后台任务栏运行

---

## 📸 界面预览

```
┌─────────────────────────────────────────────────────────────┐
│  [🚀 快速启动]  [🔄 工作流]  [🛠 工具]  [🔄 上下文]      │
│  ┌─────────────┐  ┌────────────────────────────────────┐  │
│  │ 快捷方式列表 │  │ 目标信息: MiniMax Code             │  │
│  │ • AiPyPro    │  │ 启动方式: [🚀] [🖱️] [⚙️] [📸]    │  │
│  │ • MobaXterm  │  │ 🔗 启动方式绑定: [绑定] [清除]     │  │
│  │ • MiniMax    │  │ 模板: AiPyPro_1.png               │  │
│  │             │  │ 📍 坐标: X:[ 805] Y:[ 160]        │  │
│  │             │  │   [捕捉坐标] [🎯 执行] [⏹ 停止]    │  │
│  └─────────────┘  └────────────────────────────────────┘  │
│  操作日志:                                                  │
│  [14:30] 🖱️ 鼠标双击桌面图标: AiPyPro                      │
│  [14:30] 📸 找桌面截图模板...                              │
│  [14:30] 📊 最佳匹配: CCORR 缩放=0.8 置信度=0.840        │
│  [14:30] ✅ 模板匹配双击完成                               │
│  [14:30] 🔄 已恢复前台窗口 HWND=...                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install PySide6 pyautogui pillow pyperclip pywinauto psutil pywin32 mcp
```

### 2. 启动 GUI

双击 `start.bat` 或在终端运行：

```bash
python desktop_auto.py
```

### 3. 开机自启（可选）

在「工具 → 系统设置 → 开机启动模块」勾选，即可将程序注册为 Windows 开机自启。

---

## 🎯 启动模式详解

### 1. 🚀 直接启动（Popen）

解析 `.lnk` 快捷方式 → 拿到 `TargetPath` → `subprocess.Popen` 启动目标 exe。最稳定。

### 2. 🖱️ 鼠标双击桌面图标（默认）

**三级降级策略**：
- **B 段**：截图模板多尺度匹配（0.5x~2.0x，含 125%/150% DPI 缩放），匹配到则模拟鼠标双击
- **B' 段**：UI 或快捷方式绑定的坐标优先，精确点击
- **A/C 段**：IShellFolder API + 网格估算，作为最后兜底

点击前 Win+D 显示干净桌面，点击后自动恢复前台窗口。

### 3. ⚙️ Shell 启动

`cmd /c start "" "target.exe"`，适合需要 cmd 环境的应用。

### 4. 📸 捕捉坐标点击

直接使用捕捉的坐标模拟鼠标双击，适用于图标位置固定的场景。更改分辨率后需要重新记录坐标。

---

## 🔗 启动方式绑定

每个快捷方式可以绑定专属启动方式，持久化到 `~/桌面自动化助手/shortcut_meta.json`，重启后依然有效。

**绑定内容**：
- 启动模式（desktop / direct / shell / image / coord）
- 坐标（X, Y, click_type）

**使用流程**：
1. 在快速启动标签选中目标快捷方式
2. 设置坐标或选择启动模式
3. 点击"🔗 启动方式绑定 → 💾 绑定当前启动方式"
4. 后续双击或工作流调用自动使用绑定参数

---

## 📁 数据存储

所有运行时数据统一存放在 **用户根目录/桌面自动化助手/** 下：

```
~/桌面自动化助手/
├── shortcut_meta.json   # 快捷方式绑定元数据（启动模式+坐标）
├── workflows.json       # 工作流配置
├── samples/             # 截图模板图片
├── custom_apps.json      # 自定义应用列表
└── window_state.json    # GUI 窗口状态（位置、大小）
```

---

## 🛠 工具 → 系统设置

| 功能 | 说明 |
|------|------|
| **开机启动模块** | 勾选后注册/取消 Windows 自启 |
| **创建/删除快捷方式** | 管理自定义应用列表 |
| **显示/隐藏操作日志** | 切换底部操作日志面板显示 |
| **启动/停止 MCP** | 开启/关闭 MCP Server |

---

## 🤖 MCP 集成

### 启动 MCP Server

**方式 A：GUI 内启动（推荐）**
在「工具 → 系统设置 → 启动/停止 MCP」点击启动。

**方式 B：命令行启动**
```bash
python desktop_auto.py --mcp
```

### 客户端配置

```json
{
  "mcpServers": {
    "desktop-auto": {
      "command": "C:\\path\\to\\.venv\\Scripts\\python.exe",
      "args": ["C:\\path\\to\\desktop_auto.py", "--mcp"]
    }
  }
}
```

详见 `mcp_config_example.json`。

### MCP 工具列表

| 工具 | 描述 |
|------|------|
| `list_workflows` | 列出所有工作流 |
| `list_shortcuts` | 列出桌面所有 .lnk 快捷方式 |
| `run_workflow` | 执行指定工作流（返回步骤日志） |
| `launch_shortcut` | 直接启动桌面快捷方式 |

---

## 🔄 工作流步骤类型

| 步骤 | 功能 | 关键参数 |
|------|------|---------|
| `launch_app` | 启动软件 | path |
| `wait` | 等待 N 秒 | seconds |
| `click_image` | 截图匹配后点击 | template, confidence, click_type |
| `key_press` | 按键输入 | keys（支持组合键如 `ctrl+c`） |
| `click_coords` | 坐标点击 | x, y, click_type |

---

## 🧩 系统托盘

程序支持最小化到后台任务栏运行：
- 双击托盘图标 → 恢复窗口
- 右键托盘 → 菜单（显示/隐藏、启动 MCP、退出）
- 关闭按钮 → 默认最小化到托盘（可配置）

---

## 📦 打包

```bash
# 默认用当天日期作为 tag
.\build.ps1

# 指定日期+时间
.\build.ps1 -Date "2026.07.15" -Time "14:30"
```

输出文件名格式：
```
dist/
├── 桌面自动化助手-v2026.06.14.exe        # 首次
├── 桌面自动化助手-v2026.06.14-2051.exe   # 同日第 2 次
└── 桌面自动化助手-v2026.06.15.exe        # 次日
```

**历史版本永不覆盖**，便于回滚。

---

## 🐛 近期修复

| # | 问题 | 修复 |
|---|------|------|
| 1 | 桌面图标点击坐标不准 | 多尺度模板匹配（0.5x~2.0x）|
| 2 | 125% DPI 缩放匹配失败 | 加入 0.8x 缩放比例 |
| 3 | 点击后桌面不恢复前台 | 记录 HWND → ShowWindow + SetForegroundWindow |
| 4 | 匹配失败无兜底 | B' 段使用 UI/sc 绑定坐标兜底 |
| 5 | 图像识别模式名称歧义 | 改为"捕捉坐标点击" |
| 6 | 截图被 GUI 遮挡 | Win+D 最小化窗口后再截屏 |
| 7 | 误关其他 Python 脚本 | 改为按窗口标题精确杀进程 |
| 8 | 启动方式无法持久化 | 绑定到 shortcut_meta.json，重启有效 |
| 9 | 工具 tab 散乱 | 整合为系统设置分组 |
| 10 | 无法后台托盘运行 | 新增系统托盘图标支持 |

---

## 📦 依赖

```
PySide6>=6.0
pyautogui>=0.9
Pillow>=9.0
pyperclip>=1.8
pywinauto>=0.6
psutil>=5.9
pywin32>=300
opencv-python>=4.0
mcp>=1.0
```

---

## 📄 许可证

[MIT](LICENSE)
