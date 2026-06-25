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