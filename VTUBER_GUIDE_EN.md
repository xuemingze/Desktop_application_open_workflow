# VTUBER Adapter Integration Guide

> This project integrates **[Open-LLM-VTuber](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber)** into the Desktop Auto Assistant, enabling **voice + text** dual-channel PC control. This guide covers the why, the how, and FAQs.

---

## 🙏 Acknowledgements — Open-LLM-VTuber

**[Open-LLM-VTuber](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber)** is an open-source desktop AI companion project with Live2D models, voice input, long-term memory, and more.

The original authors **deliberately do not ship any tool-calling capability** that could control your local computer — the LLM can chat, but it cannot launch apps or run workflows. This is a very reasonable design trade-off: for most users, fusing "can chat" and "can control my PC" in the same process introduces uncontrollable safety risk.

> **This project saw the opportunity:**
> Open-LLM-VTuber has already solved the hardest parts — ASR, TTS, Live2D, WebSocket long-connection, streaming output. The remaining work is to add a **safely controlled "tool brain"** that lets the LLM call local tools during conversation, but **only via strict keyword routing** — never triggering PC actions on every casual chat.

What I did:
1. **Slimmed and rewrote the core agent code** — removed modules unrelated to PC control, added a "dual-brain routing" architecture
2. **Localized the LLM backend** — defaults to OpenAI-compatible protocol, any Ollama / vLLM / gateway API works, **fully local setup is supported**
3. **Adapted to Desktop Auto Assistant** — tools are routed through an HTTP Bridge to the assistant's MCP, **never polluting the original VTUBER process**

---

## 🎯 Two Release Versions

This project publishes **two versions** on GitHub Releases — **choose based on your needs**:

### 🛠️ No-VTUBER Edition (Single exe, simplest)

You only need to download **1 file**:

| Filename | Best For | Size |
|----------|----------|------|
| `desktop-auto-v2026.06.20-engine-v2.2.7-gb794888.exe` | GUI + MCP + workflows only, no voice companion | ~110 MB |

### 🦊 AI VTUBER Edition ⭐ (Need 2, optional 1)

For voice/text dual-channel PC control, you need **2 required files**, plus **1 optional**:

| Type | Filename | Description |
|------|----------|-------------|
| **Required 1** 🧠 | `Open-LLM-VTuber-v1.2.1-zh-适配版.zip` | This project's slimmed VTUBER adapter (with Bridge integrated) |
| **Required 2** ⚙️ | `desktop-auto-v2026.06.20-AIvtuber-v2.2.13-g238644d.exe` | Desktop Auto Assistant backend, handles actual tool calls |
| **Optional** 🐾 | `open-llm-vtuber-1.2.1-setup.exe` | Official VTUBER desktop pet client, foreground companion |

> **AI VTUBER Edition architecture**: `VTUBER Adapter` ⇄ HTTP Bridge (127.0.0.1:16299) ⇄ `Desktop Auto Assistant` ⇄ MCP tool calls.
> LLM can be fully local Ollama, or any cloud API — see "Step 2: Configure LLM Backend" below.

> Pick whichever version fits your needs; the two are independent and can be installed side-by-side.

---

## 📦 Step 1: Download and Install Desktop Auto Assistant

1. Go to the [Releases page](../../releases) and download the matching version
2. Extract to any directory (recommended: `D:\桌面自动化助手\` or `C:\Users\Administrator\Desktop\控制电脑\`)
3. Double-click the exe to launch — first run will auto-create `~/桌面自动化助手/` data directory
4. Close the exe

---

## 🧠 Step 2: Configure LLM Backend (Required)

The assistant's "tool brain" requires an LLM endpoint. **Fully local Ollama is the simplest, zero-cost, privacy-safe option**.

### Option A: Local Ollama (Recommended)

**1. Download and install Ollama**
- Official site: https://ollama.com
- The Windows installer auto-starts the service

**2. Pull a model**
```bash
# Recommended qwen2.5:7b (~4.7 GB, Chinese-friendly, stable tool-calling)
ollama pull qwen2.5:7b
```

**3. Verify the service**
```bash
curl http://127.0.0.1:11434/v1/models
```
Should return a JSON list containing `qwen2.5:7b`.

**4. Configure in the assistant**
- Launch the exe
- Go to `Tools → AI Awareness`
- API URL: `http://127.0.0.1:11434/v1`
- Model: `qwen2.5:7b`
- Toggle the enable switch
- Save

### Option B: OpenAI-Compatible API (any cloud LLM)

The assistant also supports any **OpenAI Chat Completions-compatible** endpoint (DeepSeek / Zhipu / Moonshot / OpenAI / gateway API):

- Launch the exe → `Tools → AI Awareness`
- API URL: your endpoint base URL (e.g. `https://api.deepseek.com/v1`)
- API Key: your key
- Model: any model the platform supports (e.g. `deepseek-chat`)
- Save

> ⚠️ **Privacy note**: cloud LLMs upload your conversation (including tool call results). If you handle passwords or sensitive files, **use local Ollama**.

---

## 🦊 Step 3: Download the VTUBER Adapter

> ⚠️ **Important**: do NOT clone the original Open-LLM-VTuber directly — the original is a pure chat project with **no tool integration**. This project maintains a **slimmed adapter** specifically tuned for the assistant.

**Adapter download method** (from the AI VTUBER Edition release):

- Visit this project's [Releases](../../releases) page
- Download `Open-LLM-VTuber-v1.2.1-zh-适配版.zip`
- Extract to any directory (e.g. `D:\Open-LLM-VTuber-adapter\`)

Adapter vs. original differences:

| Module | Original | Adapter |
|--------|----------|---------|
| Agent core | `AgentInterface` abstract class + multiple impls | **Slimmed to `RouterAgent`**, keyword-routing only |
| LLM backend | OpenAI-compatible only | **One-click local Ollama** (default config) |
| Live2D | Off by default | **On by default + simplified config** |
| Tool calling | ❌ None | ✅ HTTP Bridge to Desktop Auto Assistant |
| Config complexity | High (dozens of `conf.yaml` items) | **Minimal (5 core items)** |

---

## 🚀 Step 4: Launch and Connect

### 4.1 Start Desktop Auto Assistant (Backend)

1. Double-click `desktop-auto-...exe`
2. **Don't close it** — let it run in the background
3. There will be a system tray icon; right-click for Show/Hide/Quit

### 4.2 Start VTUBER Adapter (Frontend)

1. Enter the adapter extraction directory
2. Double-click `start.bat` (Windows) or run `python run_server.py` in a terminal
3. The terminal will show:
   ```
   [VTuber] HTTP server started at http://127.0.0.1:12393
   [VTuber] WebSocket ready at /client-ws
   [Bridge] http://127.0.0.1:16299 listening
   ```
4. Browser auto-opens `http://127.0.0.1:12393` — this is the VTuber frontend
5. You can also use the desktop client (the adapter ships with a `frontend/` directory, some versions auto-open it)

### 4.3 Verify Connectivity

In the VTuber frontend chat box, type:
```
@助手 hi, what can you do?
```
- **Expected**: the VTuber character replies with a description
- **If it fails**: check the terminal logs to see if the Bridge started

### 4.4 First Tool Call

Try:
```
@助手 open ok-nte
```
or (action words like "run" also trigger the workflow):
```
run the zzz daily workflow
```

**Expected flow**:
1. VTuber character shows a "thinking" expression (Live2D animation)
2. Bridge forwards to Desktop Auto Assistant
3. Assistant executes the tool (open app / run workflow)
4. VTuber character speaks the result (voice + text)

---

## 🗣️ Keyword Routing Rules (Dual-Brain Core)

The assistant **does NOT** act on every conversation — it only takes over when **keywords match**. This mechanism is called **"Dual-Brain Routing"**.

> ⚠️ **Important note**: the `/cmd` prefix is a known bug (causes  to crash) — **do NOT use it**. To trigger a tool call, use any of the following:
> - **Prefix trigger**: `@助手` / `助手 ` / `系统 `
> - **Action verb trigger**: `open` / `run` / `execute` / `search` / `find` / `close` / `create` / `start` / `trigger`
> 
> For example: "run zzz workflow" works exactly the same as "@助手 run zzz workflow".

**Trigger keywords** (any match takes over):

**Prefixes**:
- `@助手` / `助手 ` / `系统 `

**Action verbs**:
- open / close / find / search / run / execute / start / create / launch / trigger

**Common objects** (typical PC action targets):
- file / folder / desktop / path / directory / window / app / program / software / workflow / command / cmd / powershell / system / memory / cpu / disk / diary / review / reminder / alarm / profile / memory / clipboard

**Examples**:
| Input | Brain | Behavior |
|-------|-------|----------|
| `How's the weather today?` | 🧠 VTuber LLM (default) | Pure chat, no tool call |
| `You're so cute` | 🧠 VTuber LLM (default) | Pure chat, may have expression |
| `@助手 open ok-nte` | 🛠 Bridge → Assistant | Calls `launch_shortcut` |
| `run zzz workflow` | 🛠 Bridge → Assistant | Calls `run_workflow` |
| `Search for "April invoice"` | 🛠 Bridge → Assistant | Calls `search_local_files` |
| `Check system memory` | 🛠 Bridge → Assistant | Calls `get_system_info` |

> **Design philosophy**: casual chat uses VTuber's own character LLM (can be a cheap small model); PC actions require **explicit triggering** (keywords) to take over. **Never default to acting on every chat**.

---

## 🛠️ Tool List (Exposed to VTUBER)

Via the Bridge, VTUBER can call the following tools:

| Tool Name | Function | Example Prompt |
|-----------|----------|----------------|
| `launch_shortcut` | Open a desktop shortcut | `@助手 open AiPyPro` |
| `run_workflow` | Execute a configured workflow | `run zzz workflow` |
| `list_shortcuts` | List all launchable shortcuts | `@助手 what apps on desktop` |
| `list_workflows` | List all workflows | `list all workflows` |
| `search_local_files` | Search local files (requires Everything) | `search for April invoice png` |
| `read_file_content` | Read file content | `open D:\note.txt` |
| `open_system_file` | Open with system default app | `open this html in browser` |
| `create_reminder` | Create a reminder | `remind me to drink water in 30 minutes` |
| `web_search` | Web search | `search for latest GPT-4o news` |

---

## ❓ FAQ

### Q1: VTUBER launches but browser won't open?

**A:** Check if port 12393 is in use:
```bash
netstat -ano | findstr :12393
```
If occupied, kill the PID or change `server_port` in the adapter's `conf.yaml`.

### Q2: Bridge connection failed?

**A:** Desktop Auto Assistant **must be started first** (and kept running in the background) for the Bridge to come up. Check the system tray icon.

### Q3: Tool call timed out?

**A:** Default timeout is 30 seconds. For slow tools (e.g. `search_local_files` scanning large dirs), bump `LLM_TIMEOUT` in `assistant_core.py`.

### Q4: VTUBER character "stuck" not speaking?

**A:** 99% chance the LLM endpoint is misconfigured. Check:
1. Is Ollama running? (`curl http://127.0.0.1:11434/v1/models`)
2. Are `api_base` and `model` correct in the adapter's `conf.yaml`?

### Q5: Can I use the original VTUBER (no tools)?

**A:** Fully supported! Original repo: https://github.com/Open-LLM-VTuber/Open-LLM-VTuber
- The original is a pure chat project, **no tool calls at all**
- If you have a bit of coding background, you can clone the original and swap `AgentInterface` for the adapter's `RouterAgent`
- Or simply use the "No-VTUBER Edition" exe (no voice companion)

### Q6: Can I run multiple VTUBER characters at once?

**A:** Yes — change `character_config` path in the adapter's `conf.yaml`, one config per character.

---

## 🔧 Advanced: Adapting Other VTUBER Projects

If you use other VTUBER derivatives (RVC voice cloning, Whisper offline ASR, etc.) and want them to talk to this assistant's Bridge:

**Core contract**:
- VTUBER side exposes one HTTP POST `/v1/chat/stream`, body like:
  ```json
  {
    "user_text": "user's words",
    "session_id": "optional session id"
  }
  ```
- Response is `text/event-stream`, each chunk:
  ```
  data: {"type": "text", "content": "Processing..."}\n\n
  data: {"type": "tool_start", "tool": "launch_shortcut", "args": {...}}\n\n
  data: {"type": "tool_finish", "result": {...}}\n\n
  data: {"type": "text", "content": "ok-nte opened"}\n\n
  data: {"type": "done"}\n\n
  ```

**Bridge config**:
- After the assistant launches, the Bridge listens on `127.0.0.1:16299`
- Any frontend honoring the above contract can connect
- See `assistant_bridge_server.py` source for details

---

## 📜 License & Acknowledgements

- **This project**: MIT License
- **Open-LLM-VTuber original**: MIT License (thanks to original author [yamatonabe](https://github.com/yamatonabe) and all contributors)
- **This project is NOT an official Open-LLM-VTuber fork** — it's an independent adapter tool

If the original authors have any concerns about the adapter distribution, **please contact me**, I will respond immediately.

---

**Back to** [README.md](README_EN.md) · [中文文档](README.md)
