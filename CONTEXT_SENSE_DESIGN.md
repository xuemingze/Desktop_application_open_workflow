# 上下文感知系统 - 方案设计（v2）

> ⚠️ **状态：AI 感知功能已取消**
> 综合考虑弊大于利（隐私风险、AI token 消耗、MCP 依赖复杂化），
> 当前版本**不包含 AI 感知推理**，仅保留基础的上下文感知能力（剪贴板监听、窗口追踪）。
> 上下文感知相关文件（`context_sensor.py`、`context_toast.py`、`context_chat.py` 等）
> 保留用于未来可能的简化版感知功能。

## 背景目标
在 PySide6 桌面客户端上实现"主动上下文感知"，构建**轻量级感知 → 规则拦截 → AI 推理 → 无感触达**四步闭环。

核心原则：用最低算力成本，换取最精准的意图捕获。

---

## 阶段一：传感器层（Sensors）
*预计工期：1-2 天*

**目标：** 建立两条数据流——剪贴板内容 + 当前前台窗口标题

**实现方式：**

1. **剪贴板监听**
   - 用 `QGuiApplication.clipboard().dataChanged` 信号，零轮询
   - 信号触发时读取 `clipboard().text()`
   - 加防抖：同一内容 2 秒内不重复上报

2. **前台窗口追踪**
   - 调用 `GetForegroundWindow` + `GetWindowTextW`（Windows API）
   - 仅在剪贴板变化时同步调用，零额外开销
   - 得到"当前窗口名 + 标题"，作为上下文胶囊的一部分

3. **进程黑名单（安全防线，高优）** 🛡️
   - **密码管理器**：`1Password.exe`, `Bitwarden.exe`, `KeePass.exe`, `LastPass.exe`, `Dashlane.exe`, `Enpass.exe`
   - **系统凭据**：`CredentialUIBroker.exe`, `lsass.exe`
   - **加密货币**：`MetaMask.exe`, `Exodus.exe`, `Electrum.exe`
   - **SSH 私钥管理**：`Pageant.exe` (PuTTY), `ssh-agent.exe`
   - **匹配规则**：在 Gatekeeper 的**最前面**用 `foreground_app.lower()` 做一次白名单检查
   - **效果**：黑名单中的进程 → 直接在物理层掐断，剪贴板内容**绝对不**进正则、不进 AI、不进任何链路
   - **代码位置**：`context_gatekeeper.py` 的入口函数 `is_safe_to_capture(app_name: str) -> bool`

4. **上下文胶囊数据结构**
   ```python
   @dataclass
   class ContextCapsule:
       clipboard_text: str
       foreground_window: str   # "MobaXterm - root@weecs"
       foreground_app: str       # "mobaxterm.exe"（用于黑名单匹配）
       timestamp: float
   ```

---

## 阶段二：规则拦截器（Gatekeeper）
*预计工期：0.5-1 天*

**目标：** 在本地过滤掉 95% 的无意义复制，只放行有价值的触发事件

**嗅探规则（正则）：**

| 规则 | 正则 | 例子 |
|------|------|------|
| IP 地址 | `^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$` | `192.168.1.100` |
| 报错信息 | `Traceback\|Exception\|Error:\|panic:` | `nginx: [emerg] bind() failed` |
| 配置片段 | `server\s*\{ \|location\s*/ ` | `server { listen 80; }` |
| 单据/表格 | `商品\|单价\|重量\|合计\|客户` | 进货单、报价单 |
| 命令行 | `^(?:pip\|npm\|cargo\|go\|git\|docker)` | `docker ps -a` |
| 文件路径 | `^[A-Z]:\\\|/home/\|~\/` | `C:\Users\admin\Desktop` |
| URL/域名 | `https?://\|[a-zA-Z0-9_-]+\.[a-zA-Z]{2,}` | `https://api.openai.com` |

**过滤逻辑：**
1. 黑名单检查（在最前面，物理级拦截）
2. 剪贴板内容过正则白名单
3. 命中任一规则 → 放行到 AI 推理
4. 未命中 → 静默丢弃，不产生任何 API 调用

---

## ~~阶段三：AI 意图推理（Intent Inference）~~ ⚠️ 已取消

~~*预计工期：1-2 天*~~

~~**目标：** 用结构化 Prompt 让模型输出可执行的 JSON 推断结果~~

~~**后端调度：**~~
~~- 推理调用交给后台的 **Hermes / Qianxia** 等 Agent 框架作为中枢大脑~~
~~- 桌面客户端只作为**轻量级端点**，负责发包 + 收 JSON~~
~~- 这样可以复用 Agent 框架已有的 prompt 管理、上下文管理、工具调度能力~~

~~**System Prompt 设计：**~~
~~```~~
~~你是一个桌面辅助 AI。用户刚刚在【{window_title}】中复制了一段内容。~~
~~【内容】：{clipboard_text}~~

~~请判断用户可能的意图，并决定是否需要主动推荐工具或动作。~~
~~只在你有较高把握时才返回 need_action: true。~~

~~必须输出以下 JSON 格式，禁止输出其他内容：~~
~~{{~~
~~  "need_action": true或false,~~
~~  "intent": "一句话描述用户意图",~~
~~  "suggested_action": "mcp工具名如 search_local_files / run_workflow / launch_shortcut",~~
~~  "action_param": "工具参数，如搜索关键词或工作流名",~~
~~  "message": "对用户的友好提示语，控制在20字以内"~~
~~}}~~
~~```~~

~~**JSON 容错与剥壳（重要）：**~~
~~- 大模型返回的结果**极大概率**会带 Markdown 代码块包装：~~
~~  ```json~~
~~  ```json~~
~~  {"need_action": true, ...}~~
~~  ```~~
~~  ```~~
~~- 必须做**多层剥壳**：~~
~~  - 先剥外层 ```...``` 标记（用正则 `r"`\`\`\`(?:json)?\s*\n?([\s\S]+?)\n?\`\`\`"`）~~
~~  - 再剥前后空白~~
~~  - 再 `json.loads()`~~
~~  - 包 try/except，失败则记日志并静默丢弃（绝不弹窗报错干扰用户）~~

~~**主线程隔离（关键）：**~~
~~- 远端 API 调用会有 1-3 秒等待期~~
~~- **必须**扔进独立的 `QThread`（继承自 QObject + moveToThread）~~
~~- **绝不**阻塞 PySide6 主事件循环~~
~~- 客户端只负责：~~
  ~~1. 主线程收到 ContextCapsule~~
  ~~2. emit 信号把任务推给 InferenceWorker~~
  ~~3. Worker 在子线程发 HTTP/SDK 调用~~
  ~~4. 返回结果通过信号 emit 回主线程~~
  ~~5. 主线程拿到结果再交给 Toast Manager~~

---

## ~~阶段四：呼吸态悬浮气泡（Toast Bubble）~~ ⚠️ AI 部分已取消

~~*预计工期：2-3 天*~~

~~**目标：** 无侵入、非打断式地呈现 AI 推断结果，支持堆叠~~
*预计工期：1-2 天*

**目标：** 用结构化 Prompt 让模型输出可执行的 JSON 推断结果

**后端调度：**
- 推理调用交给后台的 **Hermes / Qianxia** 等 Agent 框架作为中枢大脑
- 桌面客户端只作为**轻量级端点**，负责发包 + 收 JSON
- 这样可以复用 Agent 框架已有的 prompt 管理、上下文管理、工具调度能力

**System Prompt 设计：**
```
你是一个桌面辅助 AI。用户刚刚在【{window_title}】中复制了一段内容。
【内容】：{clipboard_text}

请判断用户可能的意图，并决定是否需要主动推荐工具或动作。
只在你有较高把握时才返回 need_action: true。

必须输出以下 JSON 格式，禁止输出其他内容：
{{
  "need_action": true或false,
  "intent": "一句话描述用户意图",
  "suggested_action": "mcp工具名如 search_local_files / run_workflow / launch_shortcut",
  "action_param": "工具参数，如搜索关键词或工作流名",
  "message": "对用户的友好提示语，控制在20字以内"
}}
```

**JSON 容错与剥壳（重要）：**
- 大模型返回的结果**极大概率**会带 Markdown 代码块包装：
  ```json
  ```json
  {"need_action": true, ...}
  ```
  ```
- 必须做**多层剥壳**：
  - 先剥外层 ```...``` 标记（用正则 `r"\`\`\`(?:json)?\s*\n?([\s\S]+?)\n?\`\`\`"`）
  - 再剥前后空白
  - 再 `json.loads()`
  - 包 try/except，失败则记日志并静默丢弃（绝不弹窗报错干扰用户）

**主线程隔离（关键）：**
- 远端 API 调用会有 1-3 秒等待期
- **必须**扔进独立的 `QThread`（继承自 QObject + moveToThread）
- **绝不**阻塞 PySide6 主事件循环
- 客户端只负责：
  1. 主线程收到 ContextCapsule
  2. emit 信号把任务推给 InferenceWorker
  3. Worker 在子线程发 HTTP/SDK 调用
  4. 返回结果通过信号 emit 回主线程
  5. 主线程拿到结果再交给 Toast Manager

---

## 阶段四：呼吸态悬浮气泡（Toast Bubble）
*预计工期：2-3 天*

**目标：** 无侵入、非打断式地呈现 AI 推断结果，支持堆叠

**Widget 设计：**
- 无边框、圆角、半透明背景（QGraphicsOpacityEffect）
- 固定显示在屏幕**右下角**（任务栏上方）
- 不抢占焦点（`Qt.WindowStaysOnTopHint | Qt.Tool`）
- 毛玻璃效果用 `QGraphicsBlurEffect` 或纯色半透明

**焦点陷阱规避（重要）：** ⚠️
- 初始化 Widget 时，**必须**设置 `setAttribute(Qt.WA_ShowWithoutActivating)`
- 这一行**至关重要**：没有它，气泡弹出瞬间会抢走当前焦点
- 用户在 VSCode/MobaXterm 中敲代码敲到一半，输入框突然失焦会让人抓狂
- 同时建议 `setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus)`

**单条气泡状态机：**
```
隐藏 → 滑入(显示) → 等待(5s) → 淡出(隐藏)
                ↑________点击________↓
                         ↓
                   触发工具 + 关闭气泡
```

**气泡 UI 元素：**
- 图标（根据 intent 类型：🔧/📁/🚀/⚠️）
- message 文字
- 进度条（5 秒倒计时）
- 关闭按钮（×，hover 显示）

### 堆叠队列（新需求）🆕

**触发场景：**
- 用户在排查问题时短时间内连续复制了 3 段不同 Exception 报错
- 希望它们像原生通知一样**堆叠排队**，而不是只显示最新的

**实现方案：**

1. **ToastManager 单例**
   - 全局只维护一个队列：`queue: deque[ToastWidget]`
   - 最大并发数 = 3（超过则最早的立即淡出）

2. **栈式布局**
   - 第 N 个气泡的 y 坐标 = `bottom_edge - N * (气泡高度 + 间距)`
   - 新气泡加入时，下方气泡依次下移（200ms 缓动动画 `QPropertyAnimation`）
   - 关闭时，上方气泡依次上移

3. **用户操作**
   - 鼠标 hover 单个气泡 → 暂停该气泡的倒计时（其他不受影响）
   - hover 离开 → 倒计时继续
   - 队列中存在超过 3 个 → 第 1 个立即淡出（不等待 5 秒）

4. **代码骨架：**
   ```python
   class ToastManager(QObject):
       def __init__(self):
           super().__init__()
           self.queue = deque(maxlen=3)
           self.spacing = 12
           self.margin = 24

       def show(self, message: str, icon: str = "💡"):
           # 移除最早的气泡（如果队列已满）
           while len(self.queue) >= 3:
               oldest = self.queue.popleft()
               oldest.fade_out()

           # 创建新气泡，添加到栈顶
           toast = ToastBubble(message, icon)
           self.queue.append(toast)
           self._relayout()  # 重新计算所有气泡位置 + 播放动画
   ```

---

## 文件结构规划

新增文件：
```
context_sensor.py     # 传感器：剪贴板监听 + 窗口追踪
context_gatekeeper.py # 规则拦截器：正则规则集 + 黑名单
context_toast.py     # 悬浮气泡 Widget + ToastManager
context_agent.py     # AI 推理（QThread 异步调用）
```

修改文件：
```
desktop_auto.py      # 主窗口中初始化 ContextAgent，
                     # 添加托盘图标（或菜单栏控制开关）
```

---

## 依赖与限制

- **纯 PySide6 + Windows API**：不引入额外重依赖
- **隐私**：
  - 进程黑名单在最前面物理级拦截
  - 规则过滤在本地完成
  - clipboard 文本只发送给用户指定的后端模型
- **性能**：
  - 传感器零轮询
  - 规则拦截 O(n)
  - 气泡动画用 QPropertyAnimation
  - AI 推理在独立 QThread 中
- **关闭机制**：用户可通过托盘菜单或设置面板全局关闭上下文感知

---

## 快速落地路线（单人 1 周完成）

| 天 | 任务 |
|----|------|
| Day 1 | `context_sensor.py` — 剪贴板 + 窗口追踪，跑通 |
| Day 2 | `context_gatekeeper.py` — 黑名单 + 正则规则，跑通 |
| Day 3 | `context_toast.py` — 气泡 UI + 堆叠管理，跑通 |
| Day 4 | `context_agent.py` — QThread 推理 + JSON 剥壳 + 完整流程串联 |
| Day 5 | 与 desktop_auto.py 集成，托盘控制，开关逻辑 |
| Day 6 | 细节打磨：防抖、动画、性能、边界情况 |

---

## 与现有架构的融合点

- **MCP 工具**：推断结果直接调用已有的 `search_local_files`、`run_workflow`、`launch_shortcut`
- **工作流引擎**：新感知动作可作为新的工作流步骤类型注册
- **单实例 IPC**：上下文感知作为主窗口的后台服务运行，不影响现有 IPC 架构

---

## 关键安全点清单 ⚠️

| 优先级 | 安全项 | 位置 |
|--------|--------|------|
| P0 | 进程黑名单（密码管理器、SSH 私钥） | `context_gatekeeper.py` |
| P0 | JSON 剥壳容错，绝不抛异常给用户 | `context_agent.py` |
| P0 | 远端调用独立线程，不阻塞 UI | `context_agent.py` |
| P1 | 气泡不抢焦点（WA_ShowWithoutActivating） | `context_toast.py` |
| P1 | 用户全局开关（托盘 / 设置面板） | `desktop_auto.py` |
| P2 | 剪贴板内容本地加密（可选 AES），落盘前不外泄 | `context_sensor.py` |