# VTUBER 适配版接入指南

> 本项目将 **[Open-LLM-VTuber](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber)** 接入桌面自动化助手,实现**语音 + 文字**双通道操控电脑。本指南说明:为什么接入、怎么接入、常见问题。

---

## 🙏 致谢 Open-LLM-VTuber

**[Open-LLM-VTuber](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber)** 是一个开源的桌面 AI 伴侣项目,支持 Live2D 模型、语音输入、长期记忆等功能。

原项目作者出于**安全考虑**,**没有内置任何能操控本地电脑的工具调用能力** —— 它的 LLM 只能聊天、不能开应用、不能跑工作流。这是一个非常合理的设计取舍:对大多数用户来说,把"能聊天"和"能控制电脑"放在同一个进程里,会带来不可控的安全风险。

> **本项目看到了这个机会:**
> Open-LLM-VTuber 已经解决了最难的部分 —— 语音识别、ASR、TTS、Live2D、WebSocket 长连接、流式输出。剩下的就是给它加一个**安全可控的"工具大脑"**,让 LLM 能在对话中调用本地工具,但**严格通过关键词路由**触发,不让每次聊天都"动"电脑。

我做了三件事:
1. **精简并重写核心 agent 代码** —— 移除与电脑操控无关的复杂模块,加上"双脑路由"架构
2. **本地化 LLM 后端** —— 默认接入 OpenAI 兼容协议,任何 Ollama / vLLM / 一键 API 都行,**完全本地搭建也可以**
3. **适配桌面自动化助手** —— 通过 HTTP Bridge 把工具调用转给桌面自动化助手 MCP,**不污染原 VTUBER 进程**

---

## 🎯 两种 Release 版本对应关系

本项目在 **GitHub Releases** 发布两个版本,**请按需选择**:

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

> **AI VTUBER 版架构**:`VTUBER 适配版` ⇄ HTTP Bridge(127.0.0.1:16299)⇄ `桌面自动化助手` ⇄ MCP 工具调用电脑。
> LLM 完全本地搭建 Ollama 即可,云端 API 也行,详见下文"第二步:配置 LLM 后端"。

> 选哪个版本看你需求,两个版本互不干扰,可以同时安装。

---

## 📦 第一步:下载并安装桌面自动化助手

1. 前往 [Releases 页面](../../releases) 下载对应版本 exe
2. 解压到任意目录(推荐 `D:\桌面自动化助手\` 或 `C:\Users\Administrator\Desktop\控制电脑\`)
3. 双击 exe 启动 —— 第一次启动会自动创建 `~/桌面自动化助手/` 数据目录
4. 关闭 exe

---

## 🧠 第二步:配置 LLM 后端(必须)

桌面自动化助手的"工具大脑"需要一个 LLM 端点。**完全本地搭建 Ollama 是最简单、零成本、无隐私风险的方案**。

### 方案 A:完全本地 Ollama(推荐)

**1. 下载安装 Ollama**
- 官网: https://ollama.com
- Windows 安装包直接装,装完会自动启动服务

**2. 拉取模型**
```bash
# 推荐 qwen2.5:7b (约 4.7 GB,中文友好,工具调用稳定)
ollama pull qwen2.5:7b
```

**3. 验证服务**
```bash
curl http://127.0.0.1:11434/v1/models
```
应返回 JSON 列表,包含 `qwen2.5:7b`。

**4. 在桌面自动化助手中填入配置**
- 启动 exe
- 进入「工具」标签 → 「AI 感知」
- API 地址: `http://127.0.0.1:11434/v1`
- 模型名: `qwen2.5:7b`
- 打开启用开关
- 保存

### 方案 B:OpenAI 兼容 API(任何云端 LLM)

桌面自动化助手也支持任何 **OpenAI Chat Completions 协议** 的端点(DeepSeek / 智谱 / Moonshot / OpenAI 官方 / 一键 API 中转):

- 启动 exe →「工具」标签 → 「AI 感知」
- API 地址: 你的端点 base URL(例如 `https://api.deepseek.com/v1`)
- API Key: 你的 key
- 模型名: 该平台支持的模型名(例如 `deepseek-chat`)
- 保存

> ⚠️ **隐私提醒**:云端 LLM 会上传你的对话内容(包括工具调用结果)。如果涉及密码、隐私文件,**请用本地 Ollama**。

---

## 🦊 第三步:下载 VTUBER 适配版

> ⚠️ **重要**:不要直接拉原版 Open-LLM-VTuber,原版是纯聊天项目,**没法接入工具**。本项目维护了一个**精简适配版**,专门为本助手做了调整。

**适配版下载方式**(AI VTUBER 版 release):

- 访问本项目 [Releases](../../releases) 页面
- 下载 `Open-LLM-VTuber-v1.2.1-zh-适配版.zip`
- 解压到任意目录(例如 `D:\Open-LLM-VTuber-adapter\`)

适配版 vs 原版的差异:

| 模块 | 原版 | 适配版 |
|------|------|--------|
| Agent 核心 | `AgentInterface` 抽象类 + 多套实现 | **精简为 `RouterAgent`**,只保留"关键词路由"模式 |
| LLM 后端 | 仅 OpenAI 兼容协议 | **完全本地 Ollama 一键接入**(默认配置) |
| Live2D | 默认不开启 | **默认开启 + 配置精简** |
| 工具调用 | ❌ 无 | ✅ 通过 HTTP Bridge 调用桌面自动化助手 |
| 配置复杂度 | 高(conf.yaml 几十项) | **极简**(只保留核心 5 项) |

---

## 🚀 第四步:启动并对接

### 4.1 启动桌面自动化助手(后端)

1. 双击 `desktop-auto-...exe`
2. **不要关闭**,让它在后台运行
3. 注意系统托盘会有图标,右键可以「显示/隐藏/退出」

### 4.2 启动 VTUBER 适配版(前端)

1. 进入适配版解压目录
2. 双击 `start.bat`(Windows)或在终端运行 `python run_server.py`
3. 终端会显示:
   ```
   [VTuber] HTTP 服务启动 http://127.0.0.1:12393
   [VTuber] WebSocket ready at /client-ws
   [Bridge] http://127.0.0.1:16299 listening
   ```
4. 浏览器自动打开 `http://127.0.0.1:12393` —— 这是 VTuber 前端界面
5. 也可以用桌面客户端(适配版附带了 `frontend/` 静态文件,某些版本会自动打开)

### 4.3 验证连通

在 VTuber 前端对话框里输入:
```
@助手 你好,你能做什么?
```
- **预期**:VTuber 角色回复一段文字介绍自己能做什么
- **如果失败**:检查终端日志,看是不是 Bridge 没启动

### 4.4 第一次工具调用

试试:
```
@助手 打开 ok-nte
```
或(用动作词"跑一下"也能触发工作流):
```
帮我跑一下 zzz日常 工作流
```

**预期流程**:
1. VTuber 角色"思考"表情(显示在 Live2D 动画上)
2. Bridge 转给桌面自动化助手
3. 桌面自动化助手执行工具(打开应用 / 跑工作流)
4. VTuber 角色说出结果(语音 + 文字)

---

## 🗣️ 关键词路由规则(双脑架构核心)

桌面自动化助手**不是**每次对话都"动"电脑 —— 只在**命中关键词**时才接管。这个机制叫**"双脑路由"**。

> ⚠️ **重要提示**:`/cmd` 前缀是已知 bug(会导致 软件 闪退),**不要使用**。触发工具调用用以下任意一种:
> - **前缀触发**:`@助手` / `助手 ` / `系统 `
> - **动作词触发**:`打开` / `跑一下` / `运行` / `执行` / `搜索` / `查找` / `关闭` / `新建` / `启动` / `触发`
> 
> 举例:说"跑一下 zzz工作流"和说"@助手 跑一下 zzz工作流"**效果完全一样**。

**触发关键词**(任一命中即接管):

**前缀类**:
- `@助手` / `助手 ` / `系统 `

**动作类**:
- 打开 / 关闭 / 查找 / 搜索 / 运行 / 执行 / 启动 / 新建 / 跑一下 / 触发

**对象类**(常见电脑操作目标):
- 文件 / 文件夹 / 桌面 / 路径 / 目录 / 窗口 / 应用 / 程序 / 软件 / 工作流 / 命令 / cmd / powershell / 系统 / 内存 / cpu / 磁盘 / 日记 / 复盘 / 提醒 / 闹钟 / 画像 / 记忆 / 剪贴板

**示例**:
| 输入 | 走哪条脑 | 行为 |
|------|---------|------|
| `今天天气怎么样?` | 🧠 VTuber LLM(默认) | 纯聊天,不调用工具 |
| `你好可爱` | 🧠 VTuber LLM(默认) | 纯聊天,可能有表情动作 |
| `@助手 打开 ok-nte` | 🛠 Bridge → 桌面助手 | 调用 `launch_shortcut` |
| `跑一下 zzz工作流` | 🛠 Bridge → 桌面助手 | 调用 `run_workflow` |
| `帮我搜索 4月货款` | 🛠 Bridge → 桌面助手 | 调用 `search_local_files` |
| `查一下系统内存` | 🛠 Bridge → 桌面助手 | 调用 `get_system_info` |

> **设计哲学**:日常闲聊用 VTuber 自己的角色 LLM(可以是便宜小模型),需要操作电脑时**显式触发**(关键词)才接管。**绝不默认每次都动电脑**。

---

## 🛠️ 工具列表(桌面自动化助手暴露给 VTUBER)

通过 Bridge,VTUBER 可以调用以下工具:

| 工具名 | 功能 | 示例提示词 |
|--------|------|-----------|
| `launch_shortcut` | 打开桌面快捷方式 | `@助手 打开 AiPyPro` |
| `run_workflow` | 执行已配置的工作流 | `帮我跑一下 zzz工作流` |
| `list_shortcuts` | 列出所有可启动的快捷方式 | `@助手 桌面有哪些应用` |
| `list_workflows` | 列出所有工作流 | `列出所有工作流` |
| `search_local_files` | 搜索本地文件(需要 Everything) | `帮我搜索 4月货款 png` |
| `read_file_content` | 读文件内容 | `打开 D:\note.txt` |
| `open_system_file` | 用系统默认应用打开文件 | `用浏览器打开这个 html` |
| `create_reminder` | 创建提醒 | `提醒我 30 分钟后喝水` |
| `web_search` | 联网搜索 | `搜索 最新 GPT-4o 消息` |

---

## ❓ 常见问题

### Q1:VTUBER 启动后浏览器打不开?

**A:** 检查 12393 端口是否被占用:
```bash
netstat -ano | findstr :12393
```
如有占用,杀掉对应 PID,或修改适配版 `conf.yaml` 里的 `server_port`。

### Q2:Bridge 连接失败?

**A:** 桌面自动化助手必须**先启动**(并保持后台运行),Bridge 才会起来。检查托盘图标在不在。

### Q3:工具调用超时?

**A:** 默认超时 30 秒。如果工具执行慢(比如 `search_local_files` 扫描大目录),可以在 `assistant_core.py` 里调大 `LLM_TIMEOUT`。

### Q4:VTUBER 角色"卡住"不说话?

**A:** 99% 是 LLM 端点配错。检查:
1. Ollama 服务在不在(`curl http://127.0.0.1:11434/v1/models`)
2. 适配版 `conf.yaml` 里的 `api_base` 和 `model` 填对没

### Q5:想用原版 VTUBER 不带工具?

**A:** 完全支持!原版仓库: https://github.com/Open-LLM-VTuber/Open-LLM-VTuber
- 原版是纯聊天项目,**没有任何工具调用**
- 如果你有一点代码基础,可以直接拉原版,把 `AgentInterface` 换成适配版的 `RouterAgent` 就行
- 或者干脆用"无 VTUBER 版" exe(不带语音伴侣)

### Q6:可以同时跑多个 VTUBER 角色吗?

**A:** 可以,改适配版 `conf.yaml` 里的 `character_config` 路径,每个角色一个配置。

---

## 🔧 高级:如何自己适配其他 VTUBER 项目

如果你用的是其他 VTUBER 衍生项目(比如 RVC 加声音克隆、Whisper 离线 ASR 等),想接入本助手的 Bridge:

**核心契约**:
- VTUBER 端只暴露一个 HTTP POST `/v1/chat/stream`,body 形如:
  ```json
  {
    "user_text": "用户说的话",
    "session_id": "可选的会话 ID"
  }
  ```
- 返回 `text/event-stream` 格式,每个 chunk 是:
  ```
  data: {"type": "text", "content": "正在处理..."}\n\n
  data: {"type": "tool_start", "tool": "launch_shortcut", "args": {...}}\n\n
  data: {"type": "tool_finish", "result": {...}}\n\n
  data: {"type": "text", "content": "已打开 ok-nte"}\n\n
  data: {"type": "done"}\n\n
  ```

**Bridge 配置**:
- 桌面助手启动后,Bridge 监听 `127.0.0.1:16299`
- 任何遵循上述契约的前端都能对接
- 详见 `assistant_bridge_server.py` 源码

---

## 📜 许可与致谢

- **本项目**: MIT License
- **Open-LLM-VTuber 原项目**: MIT License(感谢原作者 [yamatonabe](https://github.com/yamatonabe) 及所有贡献者)
- **本项目不是 Open-LLM-VTuber 官方分支**,只是独立的适配工具

如果原项目作者对适配版的发布有任何意见,**请联系我**,我会立即响应。

---

**回到** [README.md](README.md) · [English](README_EN.md)
