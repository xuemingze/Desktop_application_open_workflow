# -*- coding: utf-8 -*-
"""Patch context_tab.py with Chinese strings replaced by t() calls."""
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')

txt = Path('context_tab.py').read_text(encoding='utf-8')

# Add import at top
if 'from i18n import t' not in txt:
    lines = txt.split('\n')
    insert_at = 0
    for i, line in enumerate(lines):
        if line.startswith(('from __future__', 'from ', 'import ')):
            insert_at = i + 1
    lines.insert(insert_at, 'from i18n import t')
    txt = '\n'.join(lines)
    print('Added import')

# Replacement mapping: (old_string, new_string)
repls = [
    # Master switch and status
    ('"🟢 启用上下文感知"', 't("ctx_master_switch")'),
    ('"已停止"', 't("ctx_status_stopped")'),
    ('"⚪ 已停止"', 't("ctx_status_stopped")'),
    ('"⚫ 已停止"', 't("ctx_status_stopped")'),
    ('"🟢 运行中"', 't("ctx_status_running")'),

    # Tab names
    ('"🎛️ 感知行为"', 't("ctx_tab_sensor")'),
    ('"💬 AI 对话"', 't("ctx_tab_chat")'),
    ('"📋 嗅探规则"', 't("ctx_tab_rules")'),
    ('"🚫 进程黑名单"', 't("ctx_tab_blacklist")'),
    ('"⚙️ 后端"', 't("ctx_tab_backend")'),
    ('"🎯 主动嗅探"', 't("ctx_tab_proactive")'),
    ('"📊 日志"', 't("ctx_tab_log")'),

    # Sensor panel
    ('"传感器（多选）"', 't("ctx_sensor_box")'),
    ('"📋 剪贴板监听（推荐开启，零开销）"', 't("ctx_chk_clipboard")'),
    ('"🪟 前台窗口切换监听"', 't("ctx_chk_window")'),
    ('"📁 文件系统监视（手动添加目录）"', 't("ctx_chk_file")'),
    ('"⚙️ 进程启动/退出监听（配合主动嗅探用户档案触发）"', 't("ctx_chk_process")'),
    ('"文件监视路径"', 't("ctx_file_watch_path")'),
    ('"➕ 添加目录"', 't("ctx_btn_add_dir")'),
    ('"➖ 移除选中"', 't("ctx_btn_rm_dir")'),
    ('"🧪 测试剪贴板捕获"', 't("ctx_btn_test_clipboard")'),
    ('"💬 测试气泡"', 't("ctx_btn_test_toast")'),
    ('"🧹 清除所有气泡"', 't("ctx_btn_clear_toasts")'),

    # Rules panel
    ('"💡 只有当剪贴板内容命中下方任一规则时，才会被发送到 AI 推理。\n取消勾选可禁用对应规则。"', 't("ctx_clipboard_hint")'),
    ('"学习规则设置"', 't("ctx_learning_settings")'),
    ('"默认翻译语言:"', 't("ctx_default_trans_lang")'),
    ('"勾选规则后：检测到英文 → 推送 AI 翻译；检测到学术词汇 → 推送 AI 解释。"', 't("ctx_rule_tip")'),
    ('"说明:"', 't("ctx_rule_tip_label")'),
    ('"添加自定义规则"', 't("ctx_custom_rule")'),
    ('"名称:"', 't("ctx_rule_name")'),
    ('"正则:"', 't("ctx_rule_pattern")'),
    ('"➕ 添加"', 't("ctx_btn_add_rule")'),
    ('"➖ 删除选中"', 't("ctx_btn_rm_rule")'),

    # Blacklist panel
    ('"🛡️ 黑名单中的进程绝对不会被感知（剪贴板内容不会进入 AI 链路）。\n密码管理器、SSH 私钥工具等建议加入。"', 't("ctx_blacklist_hint")'),
    ('"添加进程"', 't("ctx_add_process")'),

    # Backend panel
    ('"AI 后端"', 't("ctx_backend_title")'),
    ('"后端类型:"', 't("ctx_backend_type")'),
    ('"💾 应用设置"', 't("ctx_btn_save_backend")'),
    ('"🧪 测试连通"', 't("ctx_btn_test_conn")'),
    ('"🔄 拉取模型列表"', 't("ctx_btn_fetch_models")'),
    ('"工作流交互"', 't("ctx_workflow_interaction")'),
    ('"• 气泡点击后会调用 AI 推荐的工具（MCP 工具或工作流）\n• 当前支持的工具：search_local_files / run_workflow / launch_shortcut\n• 推荐工作流需要先在「工作流」标签页创建\n• 整个过程可在「日志」标签页查看实时活动"', 't("ctx_workflow_info")'),

    # Backend placeholder texts
    ('"例如：中文 / English / 日本語"', 't("ctx_placeholder_trans_lang")'),
    ('"规则名称，如 Git 仓库路径"', 't("ctx_placeholder_rule_name")'),
    ('"正则表达式，如 ^git@"', 't("ctx_placeholder_pattern")'),
    ('"进程名，如 1Password.exe"', 't("ctx_placeholder_process")'),
    ('"可选：Tavily API Key，联网搜索优先使用 Tavily"', 't("ctx_placeholder_tavily")'),

    # Proactive panel
    ('"🎯 启用主动嗅探"', 't("ctx_proactive_switch")'),
    ('"每日主动次数"', 't("ctx_daily_count")'),
    ('"状态:"', 't("ctx_proactive_status")'),
    ('"用户档案（驱动话题主题）"', 't("ctx_profile_gb")'),
    ('"爱好:"', 't("ctx_profile_hobbies")'),
    ('"兴趣:"', 't("ctx_profile_interests")'),
    ('"学习:"', 't("ctx_profile_learning")'),
    ('"工作:"', 't("ctx_profile_work")'),
    ('"行为关键词:"', 't("ctx_profile_keywords")'),
    ('"💡 当检测到窗口/进程名包含这些关键词时，立即推送相关话题（5分钟/次冷却）"', 't("ctx_kw_hint")'),
    ('"💡 问题会像聊天一样在右下角弹出气泡，可以点击互动或忽略 5 秒后自动消失。"', 't("ctx_proactive_hint2")'),
    ('"最近问过的问题"', 't("ctx_history_gb")'),
    ('"💡 现在生成一个"', 't("ctx_btn_now")'),
    ('"🧹 清空历史"', 't("ctx_btn_clear")'),

    # Log panel
    ('"🧹 清空"', 't("ctx_btn_clear_log")'),

    # Panel docstrings (comments, translate for consistency)
    ('"感知行为面板——选择启用哪些传感器"', 't("ctx_sensor_panel_doc")'),
    ('"嗅探规则面板——启用/禁用 + 自定义"', 't("ctx_rules_panel_doc")'),
    ('"进程黑名单面板"', 't("ctx_blacklist_panel_doc")'),
    ('"后端 AI 设置面板"', 't("ctx_backend_panel_doc")'),
    ('"主动嗅探面板——用户档案 + 每日次数 + 调度状态"', 't("ctx_proactive_panel_doc")'),
    ('"实时活动日志面板"', 't("ctx_log_panel_doc")'),

    # AI Chat tab label (used in context_chat.py)
    ('"AI 感知"', 't("ctx_ai_perception")'),
]

# Apply replacements
for old, new in repls:
    if old in txt:
        txt = txt.replace(old, new)
        print(f'OK: {old[:40]}')
    else:
        print(f'MISS: {old[:40]}')

# Fix specific setText/setSuffix calls
# status_label setText
txt = txt.replace(
    'self.status_label.setText("🟢 运行中")',
    'self.status_label.setText(t("ctx_status_running"))'
)
txt = txt.replace(
    'self.status_label.setText("⚪ 已停止")',
    'self.status_label.setText(t("ctx_status_stopped"))'
)
txt = txt.replace(
    'self.status_label.setText("⚫ 已停止")',
    'self.status_label.setText(t("ctx_status_stopped"))'
)
txt = txt.replace(
    'self.status_label.setText("已停止")',
    'self.status_label.setText(t("ctx_status_stopped"))'
)

# log_count_label
txt = txt.replace(
    'self.log_count_label.setText(f"{self.log_view.document().blockCount()} 条记录")',
    'self.log_count_label.setText(t("ctx_log_count", count=self.log_view.document().blockCount()))'
)

# spinbox suffixes
txt = txt.replace(
    'self.timeout_spin.setSuffix(" 秒")',
    'self.timeout_spin.setSuffix(t("ctx_seconds_suffix"))'
)
txt = txt.replace(
    'self.daily_count_spin.setSuffix(" 次/天")',
    'self.daily_count_spin.setSuffix(t("ctx_count_suffix"))'
)

# combo items
txt = txt.replace(
    '"EchoBackend (本地测试，不发请求)"',
    't("ctx_backend_echo")'
)
txt = txt.replace(
    '"OpenAI 兼容 (Hermes/Qianlia/本地模型)"',
    't("ctx_backend_openai")'
)

# backend form labels
txt = txt.replace('"Base URL:"', 't("ctx_base_url")')
txt = txt.replace('"API Key:"', 't("ctx_api_key")')
txt = txt.replace('"Model:"', 't("ctx_model")')
txt = txt.replace('"超时:"', 't("ctx_timeout")')
txt = txt.replace('"Tavily Key:"', 't("ctx_tavily_key")')
txt = txt.replace('"IP 地址"', 't("ctx_ip_address")')
txt = txt.replace('"Nginx 配置"', 't("ctx_nginx_config")')

# placeholder text for profile
txt = txt.replace('"例如：爬山、摄影、围棋"', 't("ctx_placeholder_hobbies")')
txt = txt.replace('"例如：AI、加密货币、独立游戏"', 't("ctx_placeholder_interests")')
txt = txt.replace('"例如：Rust 编程、系统设计"', 't("ctx_placeholder_learning")')
txt = txt.replace('"例如：桌面自动化、Python 后端"', 't("ctx_placeholder_work")')
txt = txt.replace('"例如：鸣潮,原神,崩坏星穹铁道"', 't("ctx_placeholder_keywords")')

Path('context_tab.py').write_text(txt, encoding='utf-8')
print('Saved context_tab.py')
