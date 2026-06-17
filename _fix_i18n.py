# -*- coding: utf-8 -*-
"""Fix corrupted i18n.py lines."""
from pathlib import Path
import sys
sys.stdout.reconfigure(encoding='utf-8')

txt = Path('i18n.py').read_text(encoding='utf-8')

# Fix the corrupted line: tools_status_autostart_enabled entry got merged with ctx_sensor_box
bad = "    'tools_status_autostart_enabled': '状态: ✅ 已启用 (启动项: {cmd    'ctx_sensor_box': '感通器（多选）',\n"
good = "    'tools_status_autostart_enabled': '状态: ✅ 已启用 (启动项: {cmd})',\n    'ctx_sensor_box': '传感器（多选）',\n"
if bad in txt:
    txt = txt.replace(bad, good)
    print('Fixed tools_status_autostart_enabled + ctx_sensor_box')
else:
    print('Pattern not found for main fix')
    # Show what's there
    idx = txt.find('tools_status_autostart_enabled')
    print(repr(txt[idx:idx+200]))

# Fix ctx_chk_clipboard
bad2 = "    'ctx_chk_clipboard': '\\ud83d\\udccb 剪贴板监听（推荐开听，零开销）',\n"
good2 = "    'ctx_chk_clipboard': '📋 剪贴板监听（推荐开启，零开销）',\n"
if bad2 in txt:
    txt = txt.replace(bad2, good2)
    print('Fixed ctx_chk_clipboard')
else:
    # Try to find what IS there
    idx2 = txt.find("ctx_chk_clipboard")
    if idx2 >= 0:
        print('ctx_chk_clipboard found, current:', repr(txt[idx2:idx2+80]))
    else:
        print('ctx_chk_clipboard not found')

Path('i18n.py').write_text(txt, encoding='utf-8')
print('Done')
