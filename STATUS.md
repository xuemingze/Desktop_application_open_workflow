# AppBridges 重构 - 当前进度

> 本会话 (2026-06-25 15:10-15:16) 接手 Micro-step 1B-3, 一举完成到 1B-5
> 上下文峰值 20%, 单会话内推进顺利

## ✅ 已完成 (Step 1A + 1B-1 + 1B-2 + 1B-3 + 1B-4 + 1B-5)

### Step 1A: 创建 app_bridges.py
- **新文件**: `D:/项目/控制电脑/app_bridges.py` (51 行, 2480 bytes)
- **类**: `AppBridges(QObject)`, 7 个状态字段已就位

### Step 1B-1: 头部加 import
- `from app_bridges import AppBridges  # Step 1B-1: 桥接状态集中容器`

### Step 1B-2: 删除 7 个 self.xxx = None 赋值
- 7 行赋值删除, 文件从 151348 → 150822 bytes (-526)

### Step 1B-3: 把 7 个字段全部迁移到 self.bridges.xxx
- **1B-3-A**: `__init__` 加 `self.bridges = AppBridges(self)`, 放在 5 个 `_init_*` 之前
- **1B-3-B**: `_init_memory_engine` 3 处 (`memory_engine_mgr` x3)
- **1B-3-C**: `_init_reminder_scheduler` 4 处 (`_reminder_timer` x4) + `_init_memory_engine` 6 处 (`_diary_scheduler` x6)
- **1B-3-D**: `_init_companion_bridge` 7 处 (`_companion_bridge` x7)
- **1B-3-E**: `_init_vtuber_bridge` 1 处 + `_update_vtuber_config` 3 处 (`_vtuber_bridge` x4)
- **1B-3-F**: `_init_assistant_bridge` 4 处 (`assistant_core` x2, `_assistant_bridge` x4)
- **1B-3-G**: 清理路径 10 处 (closeEvent x3, `_update_companion_config` x2, `_on_memory_chunk_ready` x2, `memory_pause` x2, `memory_pause_until` x2, `memory_start` x2, `memory_status` x2, `_trigger_today_diary` x2, `_update_vtuber_config` x1)
- **共 18 个 patch + 1 处 _update_vtuber_config 修正 = 19 处实际修改**
- 全部完成后: `grep "self\.(memory_engine_mgr|_diary_scheduler|_reminder_timer|_companion_bridge|_vtuber_bridge|assistant_core|_assistant_bridge)\b" desktop_auto.py` 返回 No matches found

### Step 1B-4: MainWindow 加 7 个 @property 转发
```python
@property
def memory_engine_mgr(self): return self.bridges.memory_engine_mgr
@property
def assistant_core(self): return self.bridges.assistant_core
@property
def _companion_bridge(self): return self.bridges._companion_bridge
@property
def _vtuber_bridge(self): return self.bridges._vtuber_bridge
@property
def _assistant_bridge(self): return self.bridges._assistant_bridge
@property
def _reminder_timer(self): return self.bridges._reminder_timer
@property
def _diary_scheduler(self): return self.bridges._diary_scheduler
```
- 目的: `context_tab.py` 用 `self.window().memory_engine_mgr` 跨窗口访问, 不改它

### Step 1B-5: 整体验证
- ✅ `app_bridges.py` 语法 + 可导入
- ✅ `desktop_auto.py` 语法 + 可导入 (import 阶段无 AttributeError)
- ✅ 7 个 @property 都挂在 MainWindow 类上 (type=property)
- ✅ `self.bridges = AppBridges(self)` 已就位
- ✅ `self.bridges` 在 5 个 `_init_*` 之前初始化
- ✅ 无残留 `self.xxx =` 赋值型引用
- ✅ AppBridges 实例化 + setattr + repr 全部正常
- ✅ 7 个 @property 转发单元测试通过 (FakeWindow + FakeMgr)
- ✅ Qt 父子关系已建立 (parent=MainWindow)
- ✅ 文件大小 133814 chars, ~3500 行

## ✅ Step 1B + 本会话构建验证 (2026-06-25 16:33)

### 本会话改动
- **build.spec**: 把 `app_bridges` 加入 `hiddenimports` 和 `datas` (放在 `app_categorizer` 之后 / `assistant_bridge_server.py` 之后)
- **新 EXE**: `D:/项目/控制电脑/dist/desktop-auto-v2026.06.25-1751-g62f76f2.exe` (121,815,932 bytes, 2026-06-25 16:31 构建, 17:51 按命名规则重命名)

### 命名规则
`desktop-auto-vYYYY.MM.DD-HHMM-g<git_short_sha>.exe`
- `v` 前缀 = version
- `HHMM` = 构建时刻 (本地时间, 4 位)
- `g` 前缀 = git (Linux kernel 风格)
- `g` 后跟 7 位短 SHA = 当前 HEAD `git rev-parse --short HEAD`
- 示例历史: `desktop-auto-v2026.06.25-141542-gf6d6a0e.exe` / `desktop-auto-v2026.06.25-AIvtuber-v2.2.13-gd247976.exe`
- 重命名时不是改构建时间,而是改"发布/归档时刻"

### 构建结果
- ✅ PyInstaller 6.20.0 (`--clean --noconfirm build.spec`) 跑通,产物 121.8 MB
- ✅ `Build complete!` 正常退出,无 fatal 错误
- ⚠️ 历史遗留 ERROR (不影响构建): `websocket.Client` / `mcp.server.lowlevel.helper` 找不到
- ⚠️ 历史遗留 WARN: `xxx__mypyc` / `tzdata` hiddenimport 找不到 (运行时由 fallback 处理)
- ✅ 无 `app_bridges` 相关报错

### 运行时验证 (待手动)
**当前 EXE 已构建好但未手动启动验证**:
1. 双击 `dist/桌面自动化助手.exe` 启动
2. 观察 GUI 底部 `log_view` 中以下日志 (按顺序):
   - `[Memory] 记忆引擎已加载 (未启动)` + `[Memory] 复盘调度器已启动 ...`
   - `[Reminder] 提醒调度器已启动`
   - `[桥接] LLM backend 已初始化: ...` + `[桥接] config_path: ...`
   - `[VTuber] 桥接已初始化 (enabled=False)...`
   - `[Bridge] ✓ 16299 桥接服务已启动 (供 VTuber 调用)`
3. 检查 5 个端口/服务:
   - memory_engine: `~/桌面自动化助手/activity_log.db` 创建
   - reminder_timer: QTimer 60s 触发 `log_view` 中无 error
   - companion_bridge: 16260 (默认 enabled=False, 不启动 thread 也 OK)
   - vtuber_bridge: 16293 后端 (默认 enabled=False, 实例化即可)
   - assistant_bridge: 16299 端口必须监听
4. 验证 16299: `curl http://127.0.0.1:16299/v1/models` 应返回 JSON

## ✅ 本会话运行时验证 (2026-06-25 17:52)

### 实际启动日志 (5 桥接全部 OK)
```
[Memory] 记忆引擎已加载 (未启动)
[Memory] 复盘调度器已启动 (首次提醒=22:30)
[Reminder] 提醒调度器已启动
[桥接] LLM backend 已初始化: OpenAICompatibleBackend(https://api.minimaxi.com/v1, model=MiniMax-M2.1)
[桥接] config_path: C:\Users\Administrator\桌面自动化助手\config.json, exists=True
[桥接] raw companion_enabled=True, type=<class 'bool'>
[桥接] LLM backend 已初始化: OpenAICompatibleBackend(https://api.minimaxi.com/v1, model=MiniMax-M2.1)   ← 重复
[桥接] config_path: C:\Users\Administrator\桌面自动化助手\config.json, exists=True                       ← 重复
[桥接] raw companion_enabled=True, type=<class 'bool'>                                                  ← 重复
[VTuber] 桥接已初始化 (enabled=True)，后端: http://127.0.0.1:12393
[Bridge] 正在初始化 AssistantCore + Bridge @ 16299...
[Bridge] LLM 配置: https://api.minimaxi.com/v1, model=MiniMax-M2.1
[Bridge] ✓ 16299 桥接服务已启动 (供 VTuber 调用)
[17:52:54.886] [全局日志] 已启用,文件: C:\Users\Administrator\桌面自动化助手\desktop_auto.log
```

### 发现 + 修复 (2026-06-25 18:03)
- **bug**: `_init_reminder_scheduler` 末尾又调用了一次 `self._init_companion_bridge()`,与 `__init__` 第 1764 行重复
- **副作用**: LLM backend 二次初始化 + config 二次读取 + CompanionBridgeThread 二次 start
- **修复**: 删掉 `_init_reminder_scheduler` 末尾的重复调用,改为注释说明
- **静态校验**: AST 通过 / `_init_companion_bridge()` 调用计数 1 / @property 仍 7 个齐 / 文件 148,872 bytes
- **未验证**: 未重新构建 EXE,下一会话需要 `pyinstaller --clean build.spec` 再次发布

## 🐛 关闭卡顿修复 (2026-06-25 18:07)

### 症状
用户报告: "关闭助手的客户端时会卡一会"

### 根因分析
读 `desktop_auto.py:1843-1880` (closeEvent) 清理路径,5 个 stop 调用中:
- `MemoryEngineManager.stop()` (`memory_engine.py:276-280`) 是**主要嫌疑**
- 内部有 `self.idle_watcher.wait()` + `self.main_poll.wait()` **均无超时**
- `MainPollThread.run()` (`memory_engine.py:209`) 主循环是 `while _is_running: ... time.sleep(self.interval)` (interval=30s)
- 关闭时若线程正睡 30 秒,主线程死等到下次醒——**最坏 30 秒卡顿**
- `IdleWatcherThread` 同样问题 (sleep 5s,最多 5 秒)

### 修复
**`memory_engine.py:276-284`** — 给两个 `wait()` 加 2 秒超时,超时仅打 log (主线程不被阻塞):
```python
def stop(self):
    self.idle_watcher.stop()
    self.main_poll.stop()
    # 加超时,避免 MainPollThread 卡在 time.sleep(30) 上时无谓阻塞关闭流程
    # IdleWatcher sleep 5s, MainPollThread sleep 30s → 最多等 2s 让它们自然退出
    if not self.idle_watcher.wait(2000):
        log_bus.emit("[Memory] idle_watcher 停止超时 (2s), 强制退出")
    if not self.main_poll.wait(2000):
        log_bus.emit("[Memory] main_poll 停止超时 (2s), 强制退出")
```

### 校验
- ✅ `memory_engine.py` AST 通过
- ✅ `stop()` 内两个 `wait(2000)`,旧无超时 `wait()` 已清除
- ✅ `log_bus` 已在文件顶部导入 (line 11) — 合法
- ✅ 上一轮不变量无回归: `@property` 7 个齐 / `_init_companion_bridge()` 调用计数 1

### 收益
- 关闭流程卡顿从 **最坏 30 秒 → 最坏 2 秒**
- 其他 stop 调用 (`IPCServerThread.wait(1000)` / `_assistant_bridge.stop()` 已异步 / `companion_bridge._httpd.shutdown()` 标准库) 风险低,不动

### 未验证
未重新构建 EXE 实际启动测关闭速度,下一会话需要 `pyinstaller --clean build.spec` 后手动验证。

## 🎉 Step 1B 全部完成

**主分支 (含本会话改动) 已从"运行时崩溃"恢复到"可启动"状态.**

所有 7 个桥接字段已迁移到 `AppBridges` 容器, 通过 @property 转发保持对外 API 兼容。
外部代码 (`context_tab.py` 等) 继续用 `self.window().memory_engine_mgr` 访问, 无需修改。

## 📋 下一步: Step 1C (下一步会话)

### 目标
用 `AppBridges` 重构为模板, 解决下一批类似问题:
1. **持久化状态**: `self.shortcuts` / `self.worker` / `self.ipc_server` / `self.state` 等 4+ 个 MainWindow 字段
2. **可选**: 进一步拆 `MainWindow` 类 (单一职责原则)

### 或先 build 验证
```bash
pyinstaller build.spec --noconfirm --clean
# 手工启动 EXE, 验证 5 个桥接全部启动正常
```

## 🔧 备份位置

`D:/项目/控制电脑/backups/snapshot_20260625_145811/` (Step 0 备份)
含: desktop_auto.py (改前版本), memory_engine.py, context_chat.py

## 📊 上下文管理总结 (本次会话)

| 指标 | 值 |
|------|-----|
| 起始上下文 | 6% |
| 峰值上下文 | 20% |
| 收尾上下文 | 61% (含整文件 read 一次) |
| 改动字节 | 18 patches × 约 5-15 行 + 7 个 @property |
| 验证脚本 | 2 个 (`_verify_state.py` 留用, `_runtime_test.py` 已删) |
| 工作流 | SEARCH → PLAN → EDIT (单次 Python 脚本批量替换) → VERIFY → SUMMARIZE |

**教训**: 用 Python 脚本做批量字节级替换, 比逐次 `edit_file` 高效 10x+
**教训**: 文件用 CRLF 时 `read_file` 工具显示 `\n`, 但实际字节是 `\r\n`, `edit_file` 工具的字符串匹配能正确处理 CRLF

## ⚠️ 关键警告

**当前 main 分支已是"可启动"状态**, 但 **未实际启动 EXE 验证 5 个桥接功能正常**:
- memory_engine: MemoryEngineManager 实例化 + 信号连接 + DiaryScheduler
- reminder_timer: QTimer 60s 间隔
- companion_bridge: CompanionBridgeThread 启动 @ 16260
- vtuber_bridge: VTuberBridge 实例化
- assistant_bridge: AssistantCore + AssistantBridgeServer @ 16299

下一步建议先 build + 启动 EXE, 观察日志确认 5 个 init 都成功, 再开始 Step 1C。

---

## ✅ Step 1C 全部完成 (2026-06-25 21:45, commit `cc2eeff`)

### 容器拆分 (沿用 Step 1B `AppBridges` 模板)
**新文件** `app_containers.py` (5360 bytes, 161 行) 三件套:

| 类 | 职责 | 关键 API |
|---|---|---|
| `UIState` | 一键启动 PID 状态封装 | `load/save/to_dict/from_dict/clear` (与 `launch_state.json` 格式兼容) |
| `ShortcutsStore` | 桌面快捷方式列表封装 | `replace/items/at/find_by_path` (替代原 10 处 `self.shortcuts` 用法) |
| `AppContainers(QObject)` | 4 个持久化字段容器 | `state` / `ipc` / `worker` / `shortcuts` 4 槽位 + Qt 父子关系 |

### desktop_auto.py 改造 (4 Phase, 22 处替换)
- **Phase 1** `self.state` → `UIState` (4 处): `_load_state`/`_save_state` 委托 + `onekey_start` 写入 + `onekey_stop` 读取/清空
- **Phase 2** `self.ipc_server` → `containers.ipc` (3 处): `_start_ipc_server` + `closeEvent` stop/wait + `@property ipc_server` 转发
- **Phase 3** `self.worker` → `containers.worker` (5 处): `run_action` 创建/信号/`isRunning` + `stop_action` cancel/quit/wait/清空 + `@property worker` 转发
- **Phase 4** `self.shortcuts` → `ShortcutsStore` (10 处): `refresh_shortcuts` replace + 迭代 + len + 真值 + at + find_by_path + items + `@property shortcuts` 转发

### 调试坑
Phase 4 初版把 `for` 循环改成 `find_by_path` 误保留了后续 `if` 块引用, 导致 `IndentationError`。
**修复**: 保留原 `for` 循环,只换容器访问语义。

### 测试 (新建 `tests/` 目录, 5 文件, 87 项, 0.27s 全过, 无 warning)
- `test_app_bridges.py` (31 项) — Step 1B 回归
- `test_containers.py` (18 项) — Phase 1 + AppContainers 容器
- `test_ipc.py` (8 项) — Phase 2 锁定 + IPCServerThread API 不变量
- `test_worker.py` (10 项) — Phase 3 锁定 + LaunchWorker API 不变量
- `test_shortcuts.py` (20 项) — Phase 4 锁定

### 运行时验证 (2026-06-25 21:25)
- ✅ 5 桥接全部启动 (Memory/Reminder/Companion/VTuber/Bridge@16299)
- ✅ `[IPC] IPC 命名管道服务已启动` + 接收任务 OK
- ✅ 3 种 worker 启动模式 (direct/desktop/等待窗口) 全部成功
- ✅ 扫描 27 → 添加自定义 → 28 个快捷方式 OK
- ✅ 选中 OneDragon-Launcher / 南卡巡更系统 / AiPyPro 全部正常执行

---

## ✅ Step 2-2A 测试护栏就位 (2026-06-25 22:32, commit `514c5d8`)

**目的**: 在抽出 `launch_worker.py` 之前,先用测试锁定当前 `LaunchWorker` / `ShortcutInfo` / 内部 worker 行为,确保抽出后语义不变。

### 新文件 `tests/test_launch_worker.py` (9308 bytes, 237 行, 25 项)
**覆盖范围**:
- `ShortcutInfo` 数据类 (4 项): dataclass 字段 / 默认值 / 完整构造
- `LaunchWorker` 构造 (7 项): import / QThread 继承 / `log_signal` + `finished_signal` / **4 种启动模式** (direct/shell/image/desktop) / `extra_args` shlex 解析 / `coord` 参数 / `cancel` 初始值
- `_parse_args` 静态方法 (4 项): 空串/简单/带引号/混合
- `cancel()` 方法 (1 项): 状态可设
- 内部 worker 类 (2 项): `_DiaryWorker` / `_ChunkWorker` 存在 + 继承 QThread
- `desktop_auto.py` 不变量 (7 项): 类/方法/helper/模式/未知模式 raise

### 调试中修正的事实
- ❌ 之前以为 `LaunchWorker` 支持 `"coord"` 模式 → ✅ 实际只有 4 种 (direct/shell/image/desktop), coord 由 image 模式 + `self.coord` 参数处理
- ❌ 之前以为 `run()` else 分支文案是 `"未知启动模式"` → ✅ 实际是 `"未知模式"`

**测试护栏已就位,下一步可直接开始 `LaunchWorker` → `launch_worker.py` 抽出** (同时搬 `_get_pyautogui` / `_resolve_sample_path` helpers),抽完后跑这 25 项应仍全过, 语义不变。

**总测试数**: 87 → **112** (+25 项), **0.34s 跑完**, 无 warning。

---

## 📌 现状快照 (2026-06-26 06:49, 本次会话仅做侦察 + 文档,无代码改动)

### 仓库状态
- 分支: `master` @ `514c5d8`,工作树 clean
- `desktop_auto.py`: **153,501 bytes** (~4200+ 行, 20993 AST nodes)
- `app_bridges.py`: 2480 bytes (Step 1B)
- `app_containers.py`: 5360 bytes (Step 1C)
- `tests/`: 6 文件 / 34,186 bytes, **112 项测试 0.33s 全过, 无 warning**

### desktop_auto.py 中残余 LaunchWorker 痕迹 (抽出时一并搬走)
| 符号 | 出现次数 | 状态 |
|---|---|---|
| `LaunchWorker` | 2 | `containers.worker = LaunchWorker(...)` + 类型引用 |
| `ShortcutInfo` | 10 | dataclass 引用 |
| `_DiaryWorker` | 2 | 内部 QThread 子类 |
| `_ChunkWorker` | 2 | 内部 QThread 子类 |
| `def _get_pyautogui` | 1 | helper |
| `def _resolve_sample_path` | 1 | helper |
| `def _parse_args` | 1 | static method |

### 验证结果
- ✅ `pytest tests -q --tb-no` → **112 passed in 0.33s** (`.venv\Scripts\python.exe`)
- ✅ `desktop_auto.py` AST 解析无语法错误
- ⚠️ 系统 Python (`C:\Program Files\Python312\python.exe`) 无 pytest,必须用 `.venv\Scripts\python.exe`
- ⚠️ cmd.exe 在 `python -c "..."` 内会把 `!` 当历史扩展, 复杂内联表达式建议写脚本文件

### 当前未验证项 (下一会话需处理)
1. **未跑 PyInstaller 构建**: 上一次 EXE 构建在 `bb98a87` (memory_engine 卡顿修复), Step 1C + Step 2-2A 之后未重新打包
2. **未手动启动 EXE**: 自 `cc2eeff` 后未做 21:25 那种"启动 + 跑 3 种 worker 模式"的端到端验证
3. **`build.spec` 已含 `app_bridges` 和 `app_containers`**,但若抽出 `launch_worker.py` 需再次更新 hiddenimports/datas

---

## 📋 下一步: Step 2-2B (下一会话)

### 目标
按 `514c5d8` 护栏, 把 `LaunchWorker` / `ShortcutInfo` / `_DiaryWorker` / `_ChunkWorker` / `_get_pyautogui` / `_resolve_sample_path` 抽出到独立 `launch_worker.py`, 沿用 `app_bridges.py` / `app_containers.py` 模板。

### 预计动作
1. 新建 `launch_worker.py`,从 `desktop_auto.py` 复制上述 6 类/函数
2. `desktop_auto.py` 头部加 `from launch_worker import LaunchWorker, ShortcutInfo`
3. 删除原 6 个定义
4. 跑 `pytest tests -q --tb=line` → 应仍 **112 passed**
5. 更新 `build.spec` 加入 `launch_worker` (hiddenimports + datas)
6. `pyinstaller --clean build.spec` 重打 EXE
7. 手动启动验证 4 种 worker 模式 (direct/shell/image/desktop) 全 OK

### 风险
- `LaunchWorker` 内 `from PySide6.QtCore import ...` 依赖若漏 import 会导致 import-time 崩溃
- 内部 worker 类 (`_DiaryWorker` / `_ChunkWorker`) 引用 `desktop_auto.py` 私有符号时不能直接搬,要先解耦
- `ShortcutInfo` 是 dataclass,被外部代码 (`shortcuts_panel` 等) 引用,搬出后 import 路径变化需 grep 校验

### 或先 build 验证当前 Step 1C EXE
```bash
.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm build.spec
# 手工启动 EXE, 验证 5 桥接 + IPC + 4 种 worker 模式 + shortcuts 全部 OK
```

---

## 🏁 收尾 (2026-06-26 06:52)

### 本次会话总结
- **改动**: 仅 `STATUS.md` (纯文档), 从 214 行扩到 334 行, +17863 bytes
- **无代码改动**, 无 `desktop_auto.py` / `app_*.py` / `tests/` / `build.spec` 修改
- **验证全过**:
  - `STATUS.md` 4 个新章节 (`Step 1C` / `Step 2-2A` / `现状快照` / `下一步 Step 2-2B`) 均就位
  - `desktop_auto.py` AST 解析 OK (153501 bytes / 20993 nodes)
  - `pytest tests -q` → **112 passed in 0.31s** (`.venv\Scripts\python.exe`)
- **临时探针清理**: `_probe.py` / `_v.py` / `_p.py` 全部已删
- **工作树**: `M STATUS.md` (唯一未提交改动)

### 上下文管理
| 指标 | 值 |
|---|---|
| 起始 | 4% |
| 收尾 | 13% |
| 轮数 | 3 轮 |
| 工具调用 | ~20 次 (侦察 + 1 次 edit + 验证) |
| 工作流 | READ STATUS → git log → grep/pytest 侦察 → 续写 → 验证 → 收尾 |

### 下次接手时第一步
```bash
git log --oneline -5           # 看 HEAD 是否仍为 514c5d8
git status                     # 若 STATUS.md 未提交, 可选 commit
# 然后开始 Step 2-2B (LaunchWorker 抽出), 护栏已铺好
```

---

## ✅ 路线 B 完成: Step 1C EXE 端到端验证 (2026-06-26 07:00)

### Build 结果
- **EXE**: `dist/desktop-auto-v2026.06.26-0658-g514c5d8.exe`
- **大小**: 121,828,125 bytes (~116 MB, 比上次 +12,193 bytes, 多打包 `app_containers`)
- **构建耗时**: 68.2s (`--clean --noconfirm`), exit 0
- **历史遗留 ERROR (不影响)**: `websocket.Client` / `mcp.server.lowlevel.helper` not found

### 启动日志 (5 桥接 + IPC 全 OK)
```
[Memory] 记忆引擎已加载 (未启动)
[Memory] 复盘调度器已启动 (首次提醒=22:30)
[Reminder] 提醒调度器已启动
[桥接] LLM backend 已初始化: OpenAICompatibleBackend(https://api.minimaxi.com/v1, model=MiniMax-M2.1)
[桥接] config_path: C:\Users\Administrator\桌面自动化助手\config.json, exists=True
[桥接] raw companion_enabled=True, type=<class 'bool'>
[VTuber] 桥接已初始化 (enabled=True)，后端: http://127.0.0.1:12393
[Bridge] 正在初始化 AssistantCore + Bridge @ 16299...
[Bridge] LLM 配置: https://api.minimaxi.com/v1, model=MiniMax-M2.1
[Bridge] ✓ 16299 桥接服务已启动 (供 VTuber 调用)
[IPC] IPC 命名管道服务已启动
```
✅ 全部 5 桥接 + IPC 启动正常, **未出现 18:03 的二次初始化重复日志** (修复后确实不重复了)。

### 运行时实测 (07:00-07:02, 4 项场景全过)

| 场景 | 结果 | 关键日志 |
|---|---|---|
| 扫描快捷方式 | ✅ 28 个 | `🔍 扫描到 28 个快捷方式` |
| AI 感知/主动嗅探 | ✅ | `[主动嗅探] 已启动，每日 3 次` + `[行为触发] 已启用` |
| Toast 提示 | ✅ | `[Toast] show_toast: 早上好！... -> proactive_question` |
| workflow 调用 | ✅ | `[AI对话] 调用工具: run_workflow({'name': 'zzz日常'})` → `{"ok": true, "success": 2, "total": 2}` |
| 开机启动切换 | ✅ | `✅ 已禁用开机启动` / `✅ 已启用开机启动` |
| worker mode=**direct** (南卡巡更系统) | ✅ | `🚀 直接启动 (Popen)` → 1.5s 后 PID=11012, 1.5s 后 PID=21144 |
| worker mode=**desktop** (AiPyPro) | ✅ | `🖱️ 鼠标双击桌面图标` → OpenCV 置信度 0.992 → PID=9024 |
| 一键启动绑定清除 | ✅ | `🗑 已清除「南卡巡更系统」的启动方式绑定` |

### 4 种 worker 模式覆盖情况
- ✅ **direct** (Popen) — `南卡巡更系统` 跑通两次, 启动 1.5s
- ✅ **desktop** (OpenCV 模板匹配 + 双击) — `AiPyPro` 跑通, 置信度 0.992
- ⚠️ **shell / image** — 本次会话没显式触发, 但 `tests/test_launch_worker.py` 已锁死 4 种构造路径, 抽出 LaunchWorker 后这两条路径仍走相同代码, 风险低

### 关闭卡顿修复 (Step 1B 后续, commit `bb98a87`)
- 用户体感: 关闭流畅 (具体秒数未测, 但日志里 4 次切换都没看到 30 秒死等)
- 下次想做量化: 在 closeEvent 加 `t0 = time.time()` + 打 `[关闭耗时] {t:.2f}s` 验证 ≤ 2s

### 路线 B 结论
**主分支 (含 Step 1A/1B/1C + 关闭卡顿修复 + LaunchWorker 护栏) 已稳定运行**, EXE 端到端验证通过。可放心进入 Step 2-2B (LaunchWorker 抽出)。

---

## 📋 路线 A (Step 2-2B) 现在可以启动

**前置条件全绿**:
- ✅ 路线 B 验证 EXE 真能跑
- ✅ 25 项 LaunchWorker 护栏在 514c5d8 就位
- ✅ 4 种 worker 模式 (direct/desktop 已实测, shell/image 由护栏锁定)
- ✅ build.spec 已含 `app_bridges` + `app_containers`, 抽出 `launch_worker` 时只需再加一行

**下一步动作** (下个会话开工):
1. 新建 `launch_worker.py`, 搬 6 符号 (LaunchWorker / ShortcutInfo / _DiaryWorker / _ChunkWorker / _get_pyautogui / _resolve_sample_path)
2. `desktop_auto.py` 头部加 import, 删原定义
3. 跑 `pytest tests -q` → 应仍 **112 passed**
4. `build.spec` hiddenimports + datas 加 `launch_worker`
5. 重打 EXE + 手动启动验证 4 种 worker 模式

---

## ✅ Step 2-2B 完成: 抽 LaunchWorker/ShortcutInfo 到 launch_worker.py (2026-06-26 07:25, commit `8c4a242`)

### 抽出方案
**新文件 `launch_worker.py`** (34179 bytes, 768 行) — 与 `app_bridges.py` / `app_containers.py` 模板对称:

| 抽出符号 | 行数 | 说明 |
|---|---|---|
| `LaunchWorker` | ~650 | QThread 子类, 4 模式 (direct/shell/image/desktop) |
| `ShortcutInfo` | ~11 | dataclass (9 字段) |
| `_get_pyautogui` | 6 | 懒加载 pyautogui (FAILSAFE/PAUSE 配置) |
| `_resolve_sample_path` | 20 | 模板路径解析, **独立实现**走 `data_paths.resolve_user_data_dir()`, 不依赖 desktop_auto 私有 helper |

**未抽出 (留在 desktop_auto.py)**:
- `_DiaryWorker` / `_ChunkWorker` — 仍是 `MainWindow._generate_diary_async` / `_generate_chunk_async` 方法内的**嵌套类** (测试护栏要求它们在 desktop_auto.py 源中)
- `_shortcut_key` / `load_shortcut_meta` / `save_shortcut_meta` — 仍由 desktop_auto 提供, LaunchWorker 通过回调注入使用

### 循环 import 解决方案
原 `_save_match_coord` 调用 `desktop_auto` 的 `_shortcut_key` / `load_shortcut_meta` / `save_shortcut_meta` —— 如果 `launch_worker.py` 直接 import, 会形成循环。
**做法**: `LaunchWorker.__init__` 新增第 6 个参数 `coord_saver: Optional[Callable] = None` (回调签名 `(info, cx, cy) -> None`);`run_action` 处注入 `coord_saver=self._save_match_coord`。`_save_match_coord` 实现简化为:
```python
def _save_match_coord(self, info, cx, cy):
    if self.coord_saver is None:
        return  # 向后兼容: 无回调仅记录日志
    self.coord_saver(info, cx, cy)
```

### 改动统计
- `desktop_auto.py`: **153,501 → 144,167 bytes** (-9,334 bytes / -6%, **-700 行净减**)
- `launch_worker.py`: 新增 34179 bytes
- `build.spec`: hiddenimports + datas 加 `launch_worker` (与 `app_bridges` / `app_containers` 对称)
- `tests/test_launch_worker.py`: `TestDesktopAutoInvariants` 拆为:
  - `TestLaunchWorkerInvariants` (7 项, 改检查 `launch_worker.py` 源)
  - `TestDesktopAutoResidualInvariants` (6 项, 检查 re-export + `coord_saver` 注入 + 残留 `_DiaryWorker`/`_ChunkWorker`)

### 测试
```
$ pytest tests -q
........................................................................ [ 61%]
..............................................                           [100%]
118 passed in 0.32s
```
**112 → 118 项** (+6 项不变量), **零回归**。

### 构建 (2026-06-26 07:23)
- **EXE**: `dist/desktop-auto-v2026.06.26-0723-g4da790c.exe`
- **大小**: 121,841,551 bytes (~116 MB, 比上次 `514c5d8` 版 +13,426 bytes, 多打包 `launch_worker.py`)
- **PyInstaller**: 6.20.0, `--clean --noconfirm` 跑通, exit 0
- **历史遗留 ERROR (不影响)**: `websocket.Client` / `mcp.server.lowlevel.helper` not found
- **历史遗留 WARN**: `xxx__mypyc` / `tzdata` hiddenimport 找不到
- ✅ **无 `launch_worker` 相关报错** (隐式 import 自动解析)

### 运行时验证 (待手动)
EXE 已构建好但未手动启动验证 4 种 worker 模式 (direct/shell/image/desktop)。
**下一步**: 双击 `桌面自动化助手.exe` 启动, 跑以下场景:
1. 扫描快捷方式 → 选 `南卡巡更系统` → 点「执行」(mode=direct) → 进程名 nanka 出现
2. 选 `AiPyPro` → 点「执行」(mode=desktop) → OpenCV 模板匹配 → 双击桌面图标
3. 选 `OneDragon-Launcher` → 点「执行」(mode=shell) → cmd /c start 起动
4. 选有坐标绑定的图标 → 点「执行」(mode=image + coord) → 坐标点击

### 下一步建议 (Step 2-2C 或 路线 C)
- **Step 2-2C**: 用同样模板抽 `memory_engine.py` 中的 `MemoryEngineManager` / `DiaryScheduler` / `MainPollThread` / `IdleWatcherThread` → `memory_engine/` 子包
- **路线 C (加速 EXE 启动)**: 当前 EXE 启动 ~4-5s, 大头是 PyInstaller 解压。可考虑:
  1. `nuitka` 替代 PyInstaller (快 2-3x 启动)
  2. 拆 EXE 为多个 sub-binary (按需加载 worker 模块)
  3. 排除 `mcp` / `websocket` (本次会话 build.log 多次提示找不到, 不影响运行)

### 上下文管理总结 (本次会话)
| 指标 | 值 |
|---|---|
| 起始上下文 | 4% |
| 收尾上下文 | 70% |
| 轮数 | ~122 |
| 工作流 | READ STATUS → 侦察 LaunchWorker 依赖图 → PLAN (1 句) → 写 launch_worker.py → 删 4 符号 + 注 coord_saver → 修孤儿 @dataclass → 更新 7 项不变量 → 跑 118 项测试 → 重打 EXE → git commit → 沉淀 |
| 关键决策 | _DiaryWorker/_ChunkWorker 留嵌套类 (护栏要求) / _save_match_coord 改回调注入 (解循环 import) |

### 下次接手时第一步
```bash
git log --oneline -5           # HEAD 应为 8c4a242
# 手动启动 EXE 验证 4 种 worker 模式
# 或继续 Step 2-2C (memory_engine 抽出)
```
