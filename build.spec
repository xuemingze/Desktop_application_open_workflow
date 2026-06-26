# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for desktop_auto.py
打包成单文件 exe,体积小、启动快
"""
import os
import subprocess
from datetime import datetime
from pathlib import Path

block_cipher = None


def _git_short_hash() -> str:
    """读取 HEAD 的 7 位 short hash (build 时必须先 commit, 否则 exe 名会显示旧 hash)。"""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
        ).decode("utf-8").strip()
    except Exception:
        return "unknown"


# 默认 exe 命名: desktop-auto-v{date}-{time}-g{hash}.exe
# 例: desktop-auto-v2026.06.26-0835-g08a6571.exe
# 优先级: BUILD_EXE_NAME 环境变量 > 默认生成
_DEFAULT_TAG = datetime.now().strftime("%Y.%m.%d-%H%M")
_DEFAULT_HASH = _git_short_hash()
_DEFAULT_EXE_NAME = f"desktop-auto-v{_DEFAULT_TAG}-g{_DEFAULT_HASH}.exe"


# 收集 PySide6 的所有子模块,避免运行时 ImportError
hiddenimports = [
    'i18n',
    'workflow_panel',
    'search_panel',
    'tools_tab',
    'context_tab',
    'context_chat',
    'context_agent',
    'context_sensor',
    'context_toast',
    'context_gatekeeper',
    'data_paths',
    'file_tools',
    'mcp_file_tools',
    'activity_log',
    'app_categorizer',
    'app_bridges',  # Step 1B: MainWindow 桥接状态容器
    'app_containers',  # Step 1C: 持久化容器组 (state/ipc/worker/shortcuts)
    'launch_worker',  # Step 2-2B: 启动 worker (LaunchWorker/ShortcutInfo + 2 helper)
    'memory_engine',
    'daily_diary',
    'companion_bridge',  # MetaPact 桌宠桥接
    'vtuber_bridge',       # Open-LLM-VTuber 事件转发桥接
    'vtuber_backend_manager',  # VTuber 后端进程启停管理
    'assistant_core',          # AssistantCore 纯逻辑层 (供 Bridge 和 ChatWorker 复用)
    'assistant_bridge_server', # Bridge HTTP 服务 (OpenAI 兼容，供 VTuber 调用)
    'websocket',                # vtuber_bridge 运行时需要 (try/except 无法被 PyInstaller 分析)
    'websocket.Client',         # 同上
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'win32com',
    'win32com.client',
    'win32com.shell',
    'win32api',
    'win32con',
    'win32gui',
    'win32process',
    'win32file',
    'win32pipe',
    'pywintypes',
    'PIL',
    'PIL.Image',
    'PIL.ImageGrab',
    'pyautogui',
    'pyperclip',
    'psutil',
    'numpy',
    'cv2',
    'cv2.cv2',
    'mcp',
    'mcp.server',
    'mcp.server.stdio',
    'mcp.server.models',
    'mcp.server.lowlevel',
    'mcp.server.lowlevel.helper',
    'mcp.server.session',
    'mcp.types',
    'mcp.shared',
    'mcp.shared.session',
    'mcp.shared.exceptions',
    'mcp.client',
    'mcp.client.stdio',
    'mcp.client.session',
    'mcp_embedded',
    'mcp_patch',
    'autostart',
    'jsonschema_specifications',
    'jsonschema_specifications._core',
    'referencing',
    'referencing.jsonschema',
]

# 数据文件: workflow_panel / image_match / workflows.json
try:
    from PyInstaller.utils.hooks import collect_data_files
    jsonschema_spec_datas = collect_data_files('jsonschema_specifications')
    print(f'[spec] jsonschema_specifications datas: {len(jsonschema_spec_datas)}')
except Exception as e:
    print(f'[spec] collect jsonschema_specifications datas failed: {e}')
    jsonschema_spec_datas = [
        ('.venv/Lib/site-packages/jsonschema_specifications/schemas', 'jsonschema_specifications/schemas'),
    ]

# Collect all websocket files for data
try:
    from PyInstaller.utils.hooks import collect_data_files, collect_all
    ws_datas, ws_binaries, ws_hiddenimports = collect_all('websocket')
    print('[spec] websocket datas:', len(ws_datas), 'binaries:', len(ws_binaries), 'hidden:', len(ws_hiddenimports))
except Exception as e:
    print('[spec] collect websocket_client failed:', e)
    ws_datas, ws_binaries, ws_hiddenimports = [], [], []

datas = (
    [
        ('workflow_panel.py', '.'),
        ('image_match.py', '.'),
        ('i18n.py', '.'),
        ('mcp_embedded.py', '.'),
        ('mcp_patch.py', '.'),
        ('autostart.py', '.'),
        ('assistant_core.py', '.'),  # AssistantCore 纯逻辑层
        ('assistant_bridge_server.py', '.'),  # Bridge HTTP 服务
        ('app_bridges.py', '.'),  # Step 1B: 桥接状态容器
        ('app_containers.py', '.'),  # Step 1C: 持久化容器组
        ('launch_worker.py', '.'),  # Step 2-2B: 启动 worker 模块
        ('samples', 'samples'),
        ('app_icon.ico', '.'),  # 应用图标
        ('app_icon_512_v2.png', '.'),  # README 用图标
    ] + jsonschema_spec_datas
    + ws_datas
)

binaries_list = ws_binaries

hiddenimports = hiddenimports + ws_hiddenimports

# 排除掉大且不需要的包
excludes = [
    'tkinter',
    'matplotlib',
    'scipy',
    'pandas',
    'pytest',
    'sphinx',
    'jupyter',
    'IPython',
    'notebook',
    'typer',  # mcp.cli 需要 typer,我们不用 CLI
    'mcp.cli',  # 不打包 CLI 避免 typer 依赖
    'mcp.cli.cli',
]

a = Analysis(
    ['desktop_auto.py'],
    pathex=[],
    binaries=binaries_list,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# 强制收集 mcp 包所有子模块
try:
    from PyInstaller.utils.hooks import collect_submodules, collect_data_files
    extra = collect_submodules('mcp') + collect_submodules('mcp.server') + collect_submodules('mcp.client')
    a.hiddenimports = list(set(a.hiddenimports + extra))
    print(f'[spec] mcp extra hiddenimports: {len(extra)}')
except Exception as e:
    print(f'[spec] collect_submodules failed: {e}')

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    # 默认名 = desktop-auto-v{date}-{time}-g{hash}.exe
    # 例: desktop-auto-v2026.06.26-0835-g08a6571.exe
    # 也可 export BUILD_EXE_NAME=... 覆盖 (CI/手动发布场景)
    # 前提: build 前必须先 commit, 否则 short hash 与 exe 实际内容会脱节
    name=os.environ.get('BUILD_EXE_NAME', _DEFAULT_EXE_NAME),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # 启用 UPX 压缩 (需要 UPX 可执行文件)
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # GUI 模式,无控制台
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app_icon.ico',  # 应用图标
)
