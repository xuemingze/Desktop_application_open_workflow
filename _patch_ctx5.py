# -*- coding: utf-8 -*-
"""Fix context_tab.py - normalize CRLF and fix docstring issue."""
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')

# First normalize CRLF -> LF
txt = Path('context_tab.py').read_text(encoding='utf-8')
txt = txt.replace('\r\n', '\n')

# Fix the docstring issue: """感知行为面板——选择启用哪些传感器"""
# should be kept as docstring (don't need i18n for internal docstrings)
txt = txt.replace(
    '""t("ctx_sensor_panel_doc")""',
    '"""感知行为面板——选择启用哪些传感器"""'
)
txt = txt.replace(
    '""t("ctx_rules_panel_doc")""',
    '"""嗅探规则面板——启用/禁用 + 自定义"""'
)
txt = txt.replace(
    '""t("ctx_blacklist_panel_doc")""',
    '"""进程黑名单面板"""'
)
txt = txt.replace(
    '""t("ctx_backend_panel_doc")""',
    '"""后端 AI 设置面板"""'
)
txt = txt.replace(
    '""t("ctx_proactive_panel_doc")""',
    '"""主动嗅探面板——用户档案 + 每日次数 + 调度状态"""'
)
txt = txt.replace(
    '""t("ctx_log_panel_doc")""',
    '"""实时活动日志面板"""'
)

Path('context_tab.py').write_text(txt, encoding='utf-8')
print('Fixed')
