# Desktop Auto Assistant

<div align="center">
  <img src="app_icon_512_v2.png" width="128" height="128" alt="Logo"/>
</div>

> A PySide6-based Windows desktop automation tool supporting **direct launch**, **background click**, **image recognition**, **coordinate-capture click**, and **custom workflows**. Built-in **MCP (Model Context Protocol) Server** for AI client integration. Supports background tray operation and auto-start on boot.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey.svg)](https://www.microsoft.com/windows)
[![PySide6](https://img.shields.io/badge/GUI-PySide6-orange.svg)](https://www.qt.io/qt-for-python)

[中文文档](README.md) · English

---

## ✨ Features

- 🚀 **Multiple launch modes**: Direct / Background double-click / Shell / Coordinate-capture click / Image match
- 🔗 **Per-shortcut launch binding**: Each shortcut can bind a dedicated launch mode + coordinates, persisted to `shortcut_meta.json`
- 📍 **Coordinate-capture click**: Win+D to show clean desktop → multi-scale image match → simulate mouse double-click → restore foreground window
- 🔄 **Workflow system**: Multi-step task orchestration, supports image template match, key press, coord click, wait, text input
- 🧠 **AI Awareness**: Local Ollama/minimax model integration; selection translation, academic explanation, proactive interaction; no MCP or token required
- 🤖 **MCP integration**: Standard Model Context Protocol Server, callable from any AI client
- 🗂️ **Data directory**: Workflows, configs, and templates centralized under `~/桌面自动化助手/`
- ⚙️ **Tools → System Settings**: Auto-start, shortcut management, log toggle, MCP switch
- 🧩 **System tray**: Can minimize to background tray
- 🔒 **Privacy & security**: Process blacklist (password managers / SSH keys etc.) physically blocks at sensor layer
- 🌐 **i18n**: Switch between Chinese and English in Tools tab
- 🕐 **Temporal Memory Engine (Phase A)**: Background samples foreground window every 30s → SQLite WAL persistence → monthly tables → auto-segment [IDLE] after 3min inactivity → deep suspend after 30min for power saving → daily diary reminder bubble → AI generates Markdown diary
  - App categorization: Development / SysAdmin / Communication / Browser / Office / Design / Entertainment / Other (user-editable JSON)
  - Dual-thread architecture: MainPoll (30s sampling + state merge) + IdleWatcher (5s ultra-low-cost keyboard/mouse sniff, wakes main thread)
  - Tray menu: Start / Pause 1hr / Pause until tomorrow 9am / Generate diary now

---

## 📸 UI Preview

```
┌─────────────────────────────────────────────────────────────┐
│  [🚀 Quick Launch]  [🔄 Workflows]  [🛠 Tools]  [🧠 AI]   │
│  ┌─────────────┐  ┌────────────────────────────────────┐  │
│  │ Shortcut    │  │ Target Info: MiniMax Code          │  │
│  │ List        │  │ Launch: [🚀] [🖱️] [⚙️] [📸]      │  │
│  │ • AiPyPro   │  │ 🔗 Bind Launch: [Bind] [Clear]    │  │
│  │ • MobaXterm │  │ Template: AiPyPro_1.png           │  │
│  │ • MiniMax   │  │ 📍 Coords: X:[ 805] Y:[ 160]     │  │
│  │             │  │   [Capture] [🎯 Run] [⏹ Stop]    │  │
│  └─────────────┘  └────────────────────────────────────┘  │
│  Activity Log:                                              │
│  [14:30] 🖱️ Double-clicking desktop icon: AiPyPro          │
│  [14:30] 📸 Searching for desktop template...              │
│  [14:30] ✅ OpenCV match: scale=0.8 confidence=0.840       │
│  [14:30] ✅ Template double-click completed                │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install PySide6 pyautogui pillow pyperclip pywinauto psutil pywin32 mcp opencv-python
```

### 2. Launch GUI

Double-click `start.bat` or run in terminal:

```bash
python desktop_auto.py
```

### 3. Auto-start on Login (Optional)

In `Tools → System Settings → Auto-start Module`, check the box to register the program for Windows auto-start.

---

## 🎯 Launch Mode Details

### 1. 🚀 Direct Launch (Popen)

Parses `.lnk` shortcut → reads `TargetPath` → `subprocess.Popen` to launch the target exe. Most stable.

### 2. 🖱️ Double-click Desktop Icon (Default)

**Image-match-only strategy** (no fallback chain — by user request after testing showed fallback bugs):
- **B step**: Multi-scale screenshot template match (0.6x~1.5x, includes 125%/150% DPI scaling); on hit, simulate mouse double-click
- **B' step**: User-set coordinate priority — only when user explicitly set a coord, else fail loudly

Win+D shows clean desktop before clicking, foreground window auto-restored after.

### 3. ⚙️ Shell Launch

`cmd /c start "" "target.exe"` — for apps requiring a cmd environment.

### 4. 📸 Coordinate Capture Click

Use captured coordinates directly to simulate mouse double-click; suitable when icon position is fixed. Re-record after resolution change.

---

## 🔗 Launch Mode Binding

Each shortcut can bind a dedicated launch mode, persisted to `~/桌面自动化助手/shortcut_meta.json`, surviving restarts.

**Binding contents**:
- Launch mode (desktop / direct / shell / image / coord)
- Coordinates (X, Y, click_type)

**Workflow**:
1. Select target shortcut in Quick Launch tab
2. Set coordinates or choose launch mode
3. Click "🔗 Bind Launch Mode → 💾 Bind Current Launch Mode"
4. Subsequent double-clicks or workflow calls use the bound parameters

---

## 📁 Data Storage

All runtime data is stored under **user home / 桌面自动化助手 /**:

```
~/桌面自动化助手/
├── shortcut_meta.json      # Shortcut binding metadata (launch mode + coords)
├── workflows.json          # Workflow configs
├── samples/                # Screenshot template images
├── custom_apps.json        # Custom app list
├── window_state.json       # GUI window state (position, size)
├── config.json             # Global config (background mode, language)
└── context_aware_config.json  # AI awareness config
```

---

## 🛠 Tools → System Settings

| Feature | Description |
|---------|-------------|
| **Auto-start Module** | Toggle Windows auto-start registration |
| **Shortcut Management** | Manage custom app list |
| **Log Visibility** | Show/hide bottom activity log |
| **MCP Server** | Start/stop MCP Server |
| **Language** | Switch between Chinese/English |

---

## 🧠 AI Awareness (Local Models)

### How It Works

**Sense → Filter → Reason → Bubble**, four-step closed loop, all local.

```
User copies content
    ↓
[context_sensor] Clipboard change + foreground window detection
    ↓
[context_gatekeeper] Process blacklist + regex rule filter
    ↓ (rule hit)
[context_agent] Calls local Ollama for inference
    ↓
[context_toast] Breathing-state bubble display, stacked queue
```

### Quick Setup

**1. Install Ollama (Free, open source)**
```bash
# Download from https://ollama.com, follow installer
# Pull a small model (qwen2.5:7b ~4.7GB, sufficient for daily use)
ollama pull qwen2.5:7b
```

**2. Start Ollama service**
```bash
ollama serve
# Default listens on http://127.0.0.1:11434
```

**3. Enable in app**
`Tools → System Settings → AI Awareness`:
- API URL: `http://127.0.0.1:11434/v1`
- Model: `qwen2.5:7b`
- Toggle on the enable switch

### Privacy & Security

| Layer | Description |
|-------|-------------|
| Process blacklist | Password managers / Bitwarden / KeePass etc. physically intercepted at sensor layer; clipboard never leaks |
| Local inference | All AI inference runs locally via Ollama; no network transmission |
| Regex filter | Content not matching any regex rule won't trigger any call |

### Awareness Scenarios

| Copied Content | Detection | Suggested Action |
|----------------|-----------|------------------|
| `192.168.1.100` | IP address | Search local config / logs |
| `Traceback Error...` | Error message | Search related logs |
| `https://github.com/...` | URL | Open in browser |
| `pip install pyautogui` | CLI command | Open terminal & run |
| `C:\Users\Admin\...` | Windows path | Open in Explorer |

### Context Bubbles

- Stacked at bottom-right, no focus stealing
- 5s auto-fade, hover pauses timer
- Max 3 concurrent; oldest fades first when overflow
- Click bubble to trigger suggested action

---

## 🤖 MCP Integration

### Start MCP Server

**Method A: GUI (Recommended)**
In `Tools → System Settings → Start/Stop MCP`, click start.

**Method B: Command line**
```bash
python desktop_auto.py --mcp
```

### Client Configuration

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

See `mcp_config_example.json`.

### MCP Tools

| Tool | Description |
|------|-------------|
| `list_workflows` | List all workflows |
| `list_shortcuts` | List all desktop .lnk shortcuts |
| `run_workflow` | Execute named workflow (returns step logs) |
| `launch_shortcut` | Directly launch a desktop shortcut |

---

## 🔄 Workflow Step Types

| Step | Function | Key Params |
|------|----------|-----------|
| `launch_app` | Launch software | path |
| `wait` | Wait N seconds | seconds |
| `click_image` | Screenshot match + click | template, confidence, click_type |
| `key_press` | Key input | keys (supports combos like `ctrl+c`) |
| `type_text` | Type text (clipboard paste, supports CJK) | text, delay_before, press_enter, clear_first |
| `click_coords` | Coordinate click | x, y, click_type |
| `search_file` | Everything HTTP search | query, path, action |

---

## 🧩 System Tray

The program supports minimizing to background tray:
- Double-click tray icon → Restore window
- Right-click tray → Menu (Show/Hide, Start MCP, Quit)
- Close button → Default minimize to tray (configurable)

---

## 🌐 Internationalization

Switch UI language in `Tools → Language`:
- 中文 (default)
- English

After changing, restart the program to apply.

---

## 📦 Build

```powershell
# Default uses today's date as tag
.\build.ps1

# Specify date+time
.\build.ps1 -Date "2026.07.15" -Time "14:30"
```

Output filename format:
```
dist/
├── desktop-auto-v2026.06.14.exe        # First build
├── desktop-auto-v2026.06.14-2051.exe   # Same-day rebuild
└── desktop-auto-v2026.06.15.exe        # Next day
```

**Historical versions are never overwritten**, for easy rollback.

---

## 🐛 Recent Fixes

| # | Issue | Fix |
|---|-------|-----|
| 1 | Desktop icon click coord inaccurate | Multi-scale template match (0.6x~1.5x) |
| 2 | 125% DPI scaling match failure | Added 0.8x scale ratio |
| 3 | Foreground not restored after click | Record HWND → ShowWindow + SetForegroundWindow |
| 4 | OpenCV match success but exception in fallback path | Drop fallback chain, return on first match |
| 5 | Workflow PIL OOM (15 GiB allocation) | Switch to OpenCV multi-scale match |
| 6 | OpenCV non-ASCII path not supported | Use `cv2.imdecode + np.fromfile` |
| 7 | Killed unrelated Python scripts | Match by window title precisely |
| 8 | Launch mode not persistent | Bind to `shortcut_meta.json`, survives restart |
| 9 | Tools tab disorganized | Consolidated into System Settings groups |
| 10 | Cannot run in tray background | Added system tray icon support |
| 11 | MCP read stale workflows from project root | Read from user home dir first |

---

## 📦 Dependencies

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
numpy>=1.24
```

---

## 📄 License

[MIT](LICENSE)
