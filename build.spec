# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for desktop_auto.py
打包成单文件 exe,体积小、启动快
"""
import os
from pathlib import Path

block_cipher = None

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
    'memory_engine',
    'daily_diary',
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

datas = [
    ('workflow_panel.py', '.'),
    ('image_match.py', '.'),
    ('i18n.py', '.'),
    ('mcp_embedded.py', '.'),
    ('mcp_patch.py', '.'),
    ('autostart.py', '.'),
    ('samples', 'samples'),
    ('app_icon.ico', '.'),  # 应用图标
    ('app_icon_512_v2.png', '.'),  # README 用图标
] + jsonschema_spec_datas

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
    binaries=[],
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
    # 默认名 = 桌面自动化助手; build.bat/build.ps1 会重命名为 -vYYYY.MM.DD[-HHMM].exe
    # 也可直接指定环境变量 BUILD_TAG=YYYY.MM.DD-HHMM 来一次性生成带 tag 的 EXE
    name=os.environ.get('BUILD_EXE_NAME', '桌面自动化助手'),
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
