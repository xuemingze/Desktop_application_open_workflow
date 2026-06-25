# 桌面自动化助手 (Desktop Auto Assistant)

<div align="center">
  <img src="app_icon_512_v2.png" width="128" height="128" alt="Logo"/>
</div>

> 基于 PySide6 的 Windows 桌面自动化工具，支持**直接启动**、**后台点击**、**图像识别**、**捕捉坐标点击**和**自定义工作流**。内置 **MCP (Model Context Protocol) Server**，可被 AI 客户端调用。支持后台任务栏运行，开机自启。

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey.svg)](https://www.microsoft.com/windows)
[![PySide6](https://img.shields.io/badge/GUI-PySide6-orange.svg)](https://www.qt.io/qt-for-python)

中文 · [English](README_EN.md)

---

## 📥 两种 Release 版本(请按需选择)

前往 [Releases](../../releases) 页面下载。

### 🛠️ 无 VTUBER 版(单一 exe,最简)

只需要下载 **1 个文件**:

| 文件名 | 适用人群 | 体积 |
|--------|---------|------|
| `desktop-auto-v2026.06.20-engine-v2.2.7-gb794888.exe` | 只想用 GUI + MCP + 工作流,不需要语音伴侣 | 约 110 MB |

### 🦊 AI VTUBER 版 ⭐(需下载 2 个,可选 1 个)

体验语音/文字双通道操控电脑,需要**必选 2 个文件**,外加**可选 1 个**:

| 类型 | 文件名 | 说明 |
|------|--------|------|
| **必选 1** 🧠 | `Open-LLM-VTuber-v1.2.1-zh-适配版.zip` | 本项目精简适配版 VTUBER(已含 Bridge 集成) |
| **必选 2** ⚙️ | `desktop-auto-v2026.06.20-AIvtuber-v2.2.13-g238644d.exe` | 桌面自动化助手后端,负责实际工具调用 |
| **可选** 🐾 | `open-llm-vtuber-1.2.1-setup.exe` | VTUBER 官方桌宠客户端,可前台陪伴 |

> **AI VTUBER 版工作原理**:`VTUBER 适配版` ⇄ HTTP Bridge(127.0.0.1:16299) ⇄ `桌面自动化助手` ⇄ MCP 工具调用电脑。
> LLM 完全本地搭建 Ollama 即可,云端 API 也行,详见下面的"🧠 LLM 后端"小节。

> 想要 VTUBER 体验?**先看** 👉 [VTUBER 适配指南](VTUBER_GUIDE.md)(含感谢、致谢、下载、配置、常见问题)

## ✨ 核心特性

- 🚀 **多种启动模式**：直接启动 / 后台双击 / Shell / 捕捉坐标点击 / 图像匹配
- 🔗 **启动方式绑定**：每个快捷方式可绑定专属启动方式 + 坐标，持久化到 `shortcut_meta.json`
- 📍 **捕捉坐标点击**：Win+D 显示干净桌面 → 多尺度图像匹配 → 模拟鼠标双击 → 恢复前台窗口
- 🔄 **工作流系统**：多步骤任务编排，支持截图模板匹配、按键、坐标点击、等待
- 🧠 **AI 感知**：本地 Ollama/minimax 模型直连，划词翻译/学术解释/主动交互，无需 MCP 和 token
- 🤖 **MCP 集成**：标准 Model Context Protocol Server，AI 客户端可调用
- 🗂️ **数据目录**：工作流、配置、模板统一存在 `用户根目录/桌面自动化助手/` 下
- ⚙️ **工具 → 系统设置**：开机启动 / 快捷方式管理 / 显示隐藏日志 / MCP 开关
- 🧩 **系统托盘**：可最小化到后台任务栏运行
- 🔒 **隐私安全**：进程黑名单（密码管理器/SSH 私钥等）在传感器层物理拦截
- 🕐 **时间序列记忆引擎 (Phase A)**：后台每 30 秒采样前台窗口 → SQLite WAL 持久化 → 按月分表 → 3 分钟空闲自动切 [IDLE] 段 → 30 分钟深度休眠节能 → 每日复盘气泡提醒 → AI 生成 Markdown 日记
  - 分类标签：开发编程 / 系统运维 / 沟通协作 / 浏览器 / 办公文档 / 设计创意 / 娱乐 / 其他（用户可自定义 JSON）
  - 双线程架构：MainPoll（30s 采样 + 状态合并）+ IdleWatcher（5s 极低开销键鼠嗅探，唤醒主线程）
  - 托盘菜单：启动/暂停 1 小时/暂停到明天 9:00/立即生成复盘

---

## 📸 界面预览

```
┌─────────────────────────────────────────────────────────────┐
│  [🚀 快速启动]  [🔄 工作流]  [🛠 工具]  [🔄 上下文]      │
│  ┌─────────────┐  ┌────────────────────────────────────┐  │
│  │ 快捷方式列表 │  │ 目标信息: xxx             │  │
│  │ • xxxx    │  │ 启动方式: [🚀] [🖱️] [⚙️] [📸]    │  │
│  │ • xxxxx  │  │ 🔗 启动方式绑定: [绑定] [清除]     │  │
│  │ • xxx    │  │ 模板: xxx.png               │  │
│  │             │  │ 📍 坐标: X:[ 805] Y:[ 160]        │  │
│  │             │  │   [捕捉坐标] [🎯 执行] [⏹ 停止]    │  │
│  └─────────────┘  └────────────────────────────────────┘  │
│  操作日志:                                                  │
│  [14:30] 🖱️ 鼠标双击桌面图标: xxx                      │
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

## 🧠 AI 感知（本地模型）

### 工作原理

**感知 → 过滤 → 推理 → 气泡触达**，四步闭环，全程本地运行。

```
用户复制内容
    ↓
[context_sensor] 剪贴板变化 + 前台窗口检测
    ↓
[context_gatekeeper] 进程黑名单 + 正则规则过滤
    ↓（命中规则）
[context_agent] 调用本地 Ollama 推理
    ↓
[context_toast] 呼吸态气泡展示，堆叠队列
```

### 快速启用

**1. 安装 Ollama（免费开源）**
```bash
# 下载 https://ollama.com，按提示安装
# 拉取小模型（qwen2.5:7b 约 4.7GB，足够日常使用）
ollama pull qwen2.5:7b
```

**2. 启动 Ollama 服务**
```bash
ollama serve
# 默认监听 http://127.0.0.1:11434
```

**3. 在程序中启用**
「工具 → 系统设置 → AI 感知」：
- 填入 API 地址：`http://127.0.0.1:11434/v1`
- 填入模型名：`qwen2.5:7b`
- 打开启用开关

### 安全隐私

| 防护层 | 说明 |
|--------|------|
| 进程黑名单 | 密码管理器/Bitwarden/KeePass 等在传感器层物理截断，剪贴板内容绝不外泄 |
| 本地推理 | 所有 AI 推理在本地 Ollama 完成，无网络传输 |
| 规则过滤 | 未命中正则规则的内容不触发任何调用 |

### 感知场景示例

| 复制内容 | 判断结果 | 推荐动作 |
|----------|----------|---------|
| `192.168.1.100` | IP 地址 | 搜索本地相关配置/日志 |
| `Traceback Error...` | 报错信息 | 搜索相关日志 |
| `https://github.com/...` | URL | 浏览器打开 |
| `pip install pyautogui` | 命令行 | 打开终端执行 |
| `C:\Users\Admin\...` | Windows 路径 | 资源管理器打开 |

### 上下文气泡

- 屏幕右下角堆叠显示，不抢焦点
- 5 秒自动淡出，hover 暂停计时
- 最多 3 条并发，超出则最早的立即淡出
- 点击气泡直接触发推荐动作

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
| 11 | VTUBER 原版只能聊天,不能操控电脑 | **双脑路由**:VTUBER 适配版 + HTTP Bridge + 关键词触发 |

---

## 🦊 VTUBER 适配版(可选模块)

**为什么做这个?**

[Open-LLM-VTuber](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber) 是优秀开源桌面 AI 伴侣,支持 Live2D + 语音 + 长期记忆。原作者出于安全考虑**没有内置任何操控本地电脑的工具调用能力** —— 它的 LLM 只能聊天,不能开应用、跑工作流。

我看到了这个机会:VTUBER 已经解决了最难的部分(ASR/TTS/Live2D/WebSocket),剩下就是给它加一个**安全可控的工具大脑**。本项目做了三件事:

1. **精简核心 agent** —— 移除无关模块,加上"双脑路由"架构
2. **本地化 LLM 后端** —— 默认接入 OpenAI 兼容协议,**完全本地 Ollama 也可以**
3. **通过 HTTP Bridge 适配** —— 工具调用转给桌面自动化助手,**不污染原 VTUBER 进程**

**核心特性**:
- 🛡️ **关键词路由**:日常闲聊走 VTUBER 默认 LLM,需要操控电脑时**显式触发**(`@助手` / 动作词如"打开/跑一下"),**绝不默认每次都动电脑**
- 🧠 **完全本地**:支持本地 Ollama,零成本,无隐私泄露
- 🔌 **9 个工具**:打开应用 / 跑工作流 / 搜索文件 / 读文件 / 创建提醒 / 联网搜索 / ...
- 🌐 **中英双 UI**:VTUBER 前端支持中英文切换

**👉 完整文档**:[VTUBER_GUIDE.md](VTUBER_GUIDE.md) · [English](VTUBER_GUIDE_EN.md)

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

---

## 🙏 致谢

- **[Open-LLM-VTuber](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber)** — 提供 Live2D/ASR/TTS 基础。本项目不是其官方分支,只是独立的适配工具。
- **Ollama** — 让本地 LLM 推理零成本、易部署。
- 所有为开源 LLM/VTuber/桌面自动化做出贡献的开发者。
