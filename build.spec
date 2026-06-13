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
    'PIL',
    'PIL.Image',
    'PIL.ImageGrab',
    'pyautogui',
    'pyperclip',
    'psutil',
    'numpy',
]

# 数据文件: workflow_panel / image_match / workflows.json
datas = [
    ('workflow_panel.py', '.'),
    ('image_match.py', '.'),
    ('workflows.json', '.'),
    ('samples', 'samples'),
    ('app_icon.ico', '.'),  # 应用图标
    ('app_icon_512_v2.png', '.'),  # README 用图标
]

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
    'cv2',  # 故意排除,避免 DLL 问题
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

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='桌面自动化助手',
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
