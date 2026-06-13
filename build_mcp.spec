# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for workflow_mcp_server.py
打包成单文件 MCP server (无控制台窗口)
"""
block_cipher = None

hiddenimports = [
    'mcp',
    'mcp.server',
    'mcp.server.stdio',
    'mcp.types',
    'win32com',
    'win32com.client',
    'win32com.shell',
    'win32api',
    'win32con',
    'PIL',
    'PIL.Image',
    'PIL.ImageGrab',
    'pyautogui',
    'numpy',
]

datas = [
    ('workflow_panel.py', '.'),
    ('image_match.py', '.'),
    ('workflows.json', '.'),
]

excludes = [
    'tkinter',
    'matplotlib',
    'scipy',
    'pandas',
    'pytest',
    'PySide6',
]

a = Analysis(
    ['workflow_mcp_server.py'],
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

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='workflow-mcp-server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
