# -*- coding: utf-8 -*-
"""Second pass patch for context_tab.py - handle remaining Chinese strings."""
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')

txt = Path('context_tab.py').read_text(encoding='utf-8')

# === Fix setText in _on_master_toggle ===
# status running
txt = txt.replace(
    'self.status_label.setText("🟢 运行中")',
    'self.status_label.setText(t("ctx_status_running"))'
)
# status stopped variants
for old in ['self.status_label.setText("已停止")',
            'self.status_label.setText("⚪ 已停止")',
            'self.status_label.setText("⚫ 已停止")']:
    txt = txt.replace(old, 'self.status_label.setText(t("ctx_status_stopped"))')

# === Fix log_count_label ===
txt = txt.replace(
    'self.log_count_label.setText(f"{self.log_view.document().blockCount()} 条记录")',
    'self.log_count_label.setText(t("ctx_log_count", count=self.log_view.document().blockCount()))'
)

# === Fix placeholder texts ===
ph_repls = [
    ('"例如：中文 / English / 日本語"', 't("ctx_placeholder_trans_lang")'),
    ('"规则名称，如 Git 仓库路径"', 't("ctx_placeholder_rule_name")'),
    ('"正则表达式，如 ^git@"', 't("ctx_placeholder_pattern")'),
    ('"进程名，如 1Password.exe"', 't("ctx_placeholder_process")'),
    ('"可选：Tavily API Key，联网搜索优先使用 Tavily"', 't("ctx_placeholder_tavily")'),
    ('"例如：爬山、摄影、围棋"', 't("ctx_placeholder_hobbies")'),
    ('"例如：AI、加密货币、独立游戏"', 't("ctx_placeholder_interests")'),
    ('"例如：Rust 编程、系统设计"', 't("ctx_placeholder_learning")'),
    ('"例如：桌面自动化、Python 后端"', 't("ctx_placeholder_work")'),
    ('"例如：鸣潮,原神,崩坏星穹铁道"', 't("ctx_placeholder_keywords")'),
]
for old, new in ph_repls:
    if old in txt:
        txt = txt.replace(old, new)
        print(f'OK: {old[:30]}')
    else:
        print(f'MISS placeholder: {old[:30]}')

# === Fix backend labels ===
lbl_repls = [
    ('"Base URL:"', 't("ctx_base_url")'),
    ('"API Key:"', 't("ctx_api_key")'),
    ('"Model:"', 't("ctx_model")'),
    ('"超时:"', 't("ctx_timeout")'),
    ('"Tavily Key:"', 't("ctx_tavily_key")'),
    ('"IP 地址"', 't("ctx_ip_address")'),
    ('"Nginx 配置"', 't("ctx_nginx_config")'),
]
for old, new in lbl_repls:
    if old in txt:
        txt = txt.replace(old, new)
        print(f'OK: {old}')
    else:
        print(f'MISS label: {old}')

# === Fix btn_add_rule (was missed) ===
# Find the button that should be btn_add_rule
txt = txt.replace(
    'QPushButton("➕ 添加")',
    'QPushButton(t("ctx_btn_add_rule"))',
)
# That might have replaced more than intended, let's check

# === Fix remaining items ===
# Proactive panel docstring hint
txt = txt.replace(
    '"💡 当检测到窗口/进程名包含这些关键词时，立即推送相关话题（5分钟/次冷却）"',
    't("ctx_kw_hint")'
)
txt = txt.replace(
    '"💡 问题会像聊天一样在右下角弹出气泡，可以点击互动或忽略 5 秒后自动消失。"',
    't("ctx_proactive_hint2")'
)

# Backend info group box text
txt = txt.replace(
    '"• 气泡点击后会调用 AI 推荐的工具（MCP 工具或工作流）\\n• 当前支持的工具：search_local_files / run_workflow / launch_shortcut\\n• 推荐工作流需要先在「工作流」标签页创建\\n• 整个过程可在「日志」标签页查看实时活动"',
    't("ctx_workflow_info")'
)

# docstrings (these are in comments so don't strictly need translation)
doc_repls = [
    ('"感知行为面板——选择启用哪些传感器"', 't("ctx_sensor_panel_doc")'),
    ('"嗅探规则面板——启用/禁用 + 自定义"', 't("ctx_rules_panel_doc")'),
    ('"进程黑名单面板"', 't("ctx_blacklist_panel_doc")'),
    ('"后端 AI 设置面板"', 't("ctx_backend_panel_doc")'),
    ('"主动嗅探面板——用户档案 + 每日次数 + 调度状态"', 't("ctx_proactive_panel_doc")'),
    ('"实时活动日志面板"', 't("ctx_log_panel_doc")'),
]
for old, new in doc_repls:
    txt = txt.replace(old, new)
    print(f'doc: {old[:30]}')

# Missing setSuffix for daily_count_spin (was replaced but check)
txt = txt.replace('self.daily_count_spin.setSuffix(" 次/天")', 'self.daily_count_spin.setSuffix(t("ctx_count_suffix"))')
txt = txt.replace('self.timeout_spin.setSuffix(" 秒")', 'self.timeout_spin.setSuffix(t("ctx_seconds_suffix"))')

Path('context_tab.py').write_text(txt, encoding='utf-8')
print('Saved')
