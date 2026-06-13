# 桌面自动化助手 (Desktop Auto Assistant)

基于 PySide6 的 Windows 桌面自动化工具,支持**直接启动**、**后台点击**、**图像识别**、**坐标点击**和**自定义工作流**。

## 📁 项目结构

```
控制电脑/
├── desktop_auto.py       # 主程序 (PySide6 GUI)
├── workflow_panel.py     # 工作流编辑面板
├── image_match.py        # 纯 PIL 模板匹配 (无 OpenCV 依赖)
├── workflows.json        # 工作流配置 (运行时生成)
├── samples/              # 模板图片目录
│   └── *.png             # 截图模板
├── start.bat             # Windows 启动脚本
├── start.ps1             # PowerShell 启动脚本
└── README.md             # 本文件
```

## 🚀 启动

双击 `start.bat` 或 `start.ps1` 即可启动 GUI。

## ✨ 主要功能

### 1. 快速启动 (4 种模式)

| 模式 | 说明 |
|------|------|
| 🖱️ **鼠标双击桌面图标** | IShellFolder 枚举 + ListView 后台消息点击 |
| 🚀 **直接启动 (Popen)** | 解析 .lnk 快捷方式后直接启动目标 exe (推荐) |
| ⚙️ **Shell 启动** | `cmd /c start` 启动,适合特殊场景 |
| 📸 **图像识别点击 / 坐标点击** | 模板匹配 或 用户捕捉的坐标点击 |

### 2. 坐标点击组 (替代图像识别)

- **X / Y** 数字框:输入坐标
- **点击类型**:双击(默认)/左键单击/右键单击
- **🎯 捕捉坐标 按钮**:点击后自动 `Win+D` → 隐藏 GUI → 3秒倒计时 → 自动捕捉当前鼠标坐标

执行时按 `Win+D` 显示桌面 → 在指定坐标点击 → 等待窗口就绪。

### 3. 工作流系统 (🔄 工作流 标签)

支持多步骤任务编排:

- **启动软件** (从桌面快捷方式下拉选择)
- **等待** (1-3600 秒)
- **截图匹配点击** (支持单/双击,可设匹配阈值 5%-100%)
- **按键输入** (支持组合键 `ctrl+c`、`win+d` 等)
- **坐标点击** (左键单击/双击/右键单击,带捕捉功能)

#### 工作流截图框选

点「✂️ 截图框选」→ **GUI 自动隐藏** → 全屏透明框选 → 框选完 GUI 自动恢复。模板自动保存到 `samples/wf_<时间戳>.png`。

#### 工作流坐标捕捉

点「🎯 捕捉当前鼠标坐标」→ **GUI 自动隐藏** → 3秒倒计时 → 自动填入当前鼠标位置坐标。

工作流存于 `workflows.json`,格式示例:

```json
{
  "zzz日常": {
    "name": "zzz日常",
    "description": "打开 MiniMax 测试",
    "steps": [
      {
        "type": "launch_app",
        "name": "启动 MiniMax",
        "params": {"path": "C:\\..."},
        "enabled": true
      },
      {
        "type": "wait",
        "name": "等待启动",
        "params": {"seconds": 5},
        "enabled": true
      }
    ]
  }
}
```

## 🔧 技术亮点

### 1. 纯 PIL 模板匹配 (`image_match.py`)

不依赖 OpenCV (因为某些 venv 环境的 OpenCV wheel 缺 `opencv_imgcodecs` DLL)。

使用 **NCC (归一化互相关)** 算法,滑窗扫描,鲁棒性高。

### 2. 后台 SendMessage 点击

直接给 `SysListView32` 窗口发送 `WM_LBUTTONDBLCLK` 消息,完全不影响前台焦点。

### 3. .lnk 快捷方式解析

启动前用 `WScript.Shell` 解析 `.lnk` 拿到真实 `TargetPath`,准确检测进程名。

## 🐛 已修复的关键 Bug

| # | 问题 | 修复 |
|---|------|------|
| 1 | ListView 永远找不到 | 嵌套函数 `global` 作用域 bug → 改用 dict 容器 |
| 2 | `ShortcutInfo.path` 字段名错 | 改为 `lnk_path` |
| 3 | 进程名查找失败 | 解析 .lnk 拿真实 exe 名,大小写问题解决 |
| 4 | A 段成功后重复调用 C 段 | A 段直接 return |
| 5 | GUI 窗口挡住图标 | 改 SendMessage 后台点击 + Win+D |
| 6 | OpenCV 读不到 PNG | 模板匹配改用纯 PIL + NCC |
| 7 | NCC 分数低(0.4) | 阈值降至 5%,支持弱匹配 |
| 8 | 步骤无法保存/删除 | 用 `self._current_workflow` 记住当前工作流 |
| 9 | 中文路径导致 OpenCV 报错 | 截图文件名改纯英文 |
| 10 | 坐标点击参数没传到 worker | LaunchWorker 接受 `coord` 参数 |
| 11 | 捕捉坐标后 GUI 不在前台 | showNormal + setWindowState + raise_ + activateWindow |

## 📦 依赖

```
pip install PySide6 pyautogui pillow pyperclip pywinauto psutil pywin32
```

(无需 OpenCV)

## 🎯 使用技巧

1. **快速启动 MiniMax**: 选中 → 选「🚀 直接启动」→ 「执行」
2. **用工作流打开 MobaXterm 并点击按钮**: 切换到「🔄 工作流」→ 添加「启动 MobaXterm」+「等待 2s」+「截图匹配点击 MobaXterm 按钮」
3. **批量启动多个程序**: 在工作流里连续添加多个「启动软件」步骤
4. **首次添加 click_image 步骤**: 点「✂️ 截图框选」框选要点击的图标 → 设置阈值 30% → 保存

## ⚠️ 注意事项

- `image_match.py` 使用 NCC 算法,对**亮度/颜色变化敏感**,阈值 30%-50% 通常够用
- `Win+D` 会让所有窗口最小化(包括其他应用),但**不影响目标程序状态**
- 截图中**避免中文字符的文件名**(OpenCV 不认,纯 PIL 方案后此问题已不存在)
