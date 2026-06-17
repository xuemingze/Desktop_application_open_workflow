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

# For multiline strings in QLabel, find the QLabel line and replace
# Strategy: replace specific distinctive fragments within larger QLabel calls

# (search_fragment, full_line_replacement)
# We'll do targeted in-place replacements on the specific lines

lines = txt.split('\n')
changed = 0
for i, line in enumerate(lines):
    orig = line

    # Master switch
    if 'QCheckBox("🟢 启用上下文感知")' in line:
        lines[i] = line.replace('"🟢 启用上下文感知"', 't("ctx_master_switch")')
        changed += 1; print(f'L{i}: master_switch')

    # Status label
    elif 'setText("已停止")' in line or 'setText("⚪ 已停止")' in line or 'setText("⚫ 已停止")' in line:
        lines[i] = line.replace('setText("已停止")', 'setText(t("ctx_status_stopped"))')
        lines[i] = lines[i].replace('setText("⚪ 已停止")', 'setText(t("ctx_status_stopped"))')
        lines[i] = lines[i].replace('setText("⚫ 已停止")', 'setText(t("ctx_status_stopped"))')
        changed += 1; print(f'L{i}: status_stopped')

    elif 'setText("🟢 运行中")' in line:
        lines[i] = line.replace('"🟢 运行中"', 't("ctx_status_running")')
        changed += 1; print(f'L{i}: status_running')

    # Tab names (addTab)
    elif 'addTab(self._build_sensor_panel(), "🎛️ 感知行为")' in line:
        lines[i] = line.replace('"🎛️ 感知行为"', 't("ctx_tab_sensor")')
        changed += 1; print(f'L{i}: tab_sensor')
    elif 'addTab(self.context_chat_tab, "💬 AI 对话")' in line:
        lines[i] = line.replace('"💬 AI 对话"', 't("ctx_tab_chat")')
        changed += 1; print(f'L{i}: tab_chat')
    elif 'addTab(self._build_rules_panel(), "📋 嗅探规则")' in line:
        lines[i] = line.replace('"📋 嗅探规则"', 't("ctx_tab_rules")')
        changed += 1; print(f'L{i}: tab_rules')
    elif 'addTab(self._build_blacklist_panel(), "🚫 进程黑名单")' in line:
        lines[i] = line.replace('"🚫 进程黑名单"', 't("ctx_tab_blacklist")')
        changed += 1; print(f'L{i}: tab_blacklist')
    elif 'addTab(self._build_backend_panel(), "⚙️ 后端")' in line:
        lines[i] = line.replace('"⚙️ 后端"', 't("ctx_tab_backend")')
        changed += 1; print(f'L{i}: tab_backend')
    elif 'addTab(self._build_proactive_panel(), "🎯 主动嗅探")' in line:
        lines[i] = line.replace('"🎯 主动嗅探"', 't("ctx_tab_proactive")')
        changed += 1; print(f'L{i}: tab_proactive')
    elif 'addTab(self._build_log_panel(), "📊 日志")' in line:
        lines[i] = line.replace('"📊 日志"', 't("ctx_tab_log")')
        changed += 1; print(f'L{i}: tab_log')

    # Sensor panel - QGroupBox and checkboxes
    elif 'QGroupBox("传感器（多选）")' in line:
        lines[i] = line.replace('"传感器（多选）"', 't("ctx_sensor_box")')
        changed += 1; print(f'L{i}: sensor_box')
    elif 'QCheckBox("📋 剪贴板监听' in line:
        lines[i] = line.replace('"📋 剪贴板监听（推荐开启，零开销）"', 't("ctx_chk_clipboard")')
        changed += 1; print(f'L{i}: chk_clipboard')
    elif 'QCheckBox("🪟 前台窗口切换监听")' in line:
        lines[i] = line.replace('"🪟 前台窗口切换监听"', 't("ctx_chk_window")')
        changed += 1; print(f'L{i}: chk_window')
    elif 'QCheckBox("📁 文件系统监视' in line:
        lines[i] = line.replace('"📁 文件系统监视（手动添加目录）"', 't("ctx_chk_file")')
        changed += 1; print(f'L{i}: chk_file')
    elif 'QCheckBox("⚙️ 进程启动/退出监听' in line:
        lines[i] = line.replace('"⚙️ 进程启动/退出监听（配合主动嗅探用户档案触发）"', 't("ctx_chk_process")')
        changed += 1; print(f'L{i}: chk_process')

    # File watch paths group
    elif 'QGroupBox("文件监视路径")' in line:
        lines[i] = line.replace('"文件监视路径"', 't("ctx_file_watch_path")')
        changed += 1; print(f'L{i}: file_watch_path')

    # Path buttons
    elif 'QPushButton("➕ 添加目录")' in line:
        lines[i] = line.replace('"➕ 添加目录"', 't("ctx_btn_add_dir")')
        changed += 1; print(f'L{i}: btn_add_dir')
    elif 'QPushButton("➖ 移除选中")' in line:
        lines[i] = line.replace('"➖ 移除选中"', 't("ctx_btn_rm_dir")')
        changed += 1; print(f'L{i}: btn_rm_dir')

    # Test buttons
    elif 'QPushButton("🧪 测试剪贴板捕获")' in line:
        lines[i] = line.replace('"🧪 测试剪贴板捕获"', 't("ctx_btn_test_clipboard")')
        changed += 1; print(f'L{i}: btn_test_clipboard')
    elif 'QPushButton("💬 测试气泡")' in line:
        lines[i] = line.replace('"💬 测试气泡"', 't("ctx_btn_test_toast")')
        changed += 1; print(f'L{i}: btn_test_toast')
    elif 'QPushButton("🧹 清除所有气泡")' in line:
        lines[i] = line.replace('"🧹 清除所有气泡"', 't("ctx_btn_clear_toasts")')
        changed += 1; print(f'L{i}: btn_clear_toasts')

    # Rules panel - clipboard hint multiline
    elif 'QLabel("💡 只有当剪贴板内容命中' in line:
        lines[i] = line.replace(
            '"💡 只有当剪贴板内容命中下方任一规则时，才会被发送到 AI 推理。\\n"',
            't("ctx_clipboard_hint") + "\\n"'
        )
        # Also replace the continuation line
        changed += 1; print(f'L{i}: clipboard_hint')

    # Learning rules
    elif 'QGroupBox("学习规则设置")' in line:
        lines[i] = line.replace('"学习规则设置"', 't("ctx_learning_settings")')
        changed += 1; print(f'L{i}: learning_settings')
    elif 'lf.addRow("默认翻译语言:",' in line:
        lines[i] = line.replace('"默认翻译语言:"', 't("ctx_default_trans_lang")')
        changed += 1; print(f'L{i}: default_trans_lang')
    elif 'lf.addRow("说明:", tip)' in line:
        lines[i] = line.replace('"说明:"', 't("ctx_rule_tip_label")')
        changed += 1; print(f'L{i}: rule_tip_label')

    # Custom rule
    elif 'QGroupBox("添加自定义规则")' in line:
        lines[i] = line.replace('"添加自定义规则"', 't("ctx_custom_rule")')
        changed += 1; print(f'L{i}: custom_rule')
    elif 'cv.addRow("名称:",' in line:
        lines[i] = line.replace('"名称:"', 't("ctx_rule_name")')
        changed += 1; print(f'L{i}: rule_name')
    elif 'cv.addRow("正则:",' in line:
        lines[i] = line.replace('"正则:"', 't("ctx_rule_pattern")')
        changed += 1; print(f'L{i}: rule_pattern')
    elif 'QPushButton("➕ 添加")' in line and 'btn_add.clicked' in line:
        lines[i] = line.replace('"➕ 添加"', 't("ctx_btn_add_rule")')
        changed += 1; print(f'L{i}: btn_add_rule')
    elif 'QPushButton("➖ 删除选中")' in line:
        lines[i] = line.replace('"➖ 删除选中"', 't("ctx_btn_rm_rule")')
        changed += 1; print(f'L{i}: btn_rm_rule')

    # Blacklist panel
    elif 'QLabel("🛡️ 黑名单中的进程绝对' in line:
        lines[i] = line.replace(
            '"🛡️ 黑名单中的进程绝对不会被感知（剪贴板内容不会进入 AI 链路）。\\n"',
            't("ctx_blacklist_hint") + "\\n"'
        )
        changed += 1; print(f'L{i}: blacklist_hint')
    elif 'QGroupBox("添加进程")' in line:
        lines[i] = line.replace('"添加进程"', 't("ctx_add_process")')
        changed += 1; print(f'L{i}: add_process')

    # Backend panel
    elif 'QGroupBox("AI 后端")' in line:
        lines[i] = line.replace('"AI 后端"', 't("ctx_backend_title")')
        changed += 1; print(f'L{i}: backend_title')
    elif 'f.addRow("后端类型:",' in line:
        lines[i] = line.replace('"后端类型:"', 't("ctx_backend_type")')
        changed += 1; print(f'L{i}: backend_type')

    # Backend combo items
    elif '"EchoBackend (本地测试，不发请求)"' in line:
        lines[i] = line.replace('"EchoBackend (本地测试，不发请求)"', 't("ctx_backend_echo")')
        changed += 1; print(f'L{i}: backend_echo')
    elif '"OpenAI 兼容 (Hermes/Qianlia/本地模型)"' in line:
        lines[i] = line.replace('"OpenAI 兼容 (Hermes/Qianlia/本地模型)"', 't("ctx_backend_openai")')
        changed += 1; print(f'L{i}: backend_openai')

    # Backend labels
    elif 'f.addRow("Base URL:",' in line:
        lines[i] = line.replace('"Base URL:"', 't("ctx_base_url")')
        changed += 1; print(f'L{i}: base_url')
    elif 'f.addRow("API Key:",' in line:
        lines[i] = line.replace('"API Key:"', 't("ctx_api_key")')
        changed += 1; print(f'L{i}: api_key')
    elif 'f.addRow("Model:",' in line:
        lines[i] = line.replace('"Model:"', 't("ctx_model")')
        changed += 1; print(f'L{i}: model')
    elif 'f.addRow("超时:",' in line:
        lines[i] = line.replace('"超时:"', 't("ctx_timeout")')
        changed += 1; print(f'L{i}: timeout')
    elif 'f.addRow("Tavily Key:",' in line:
        lines[i] = line.replace('"Tavily Key:"', 't("ctx_tavily_key")')
        changed += 1; print(f'L{i}: tavily_key')

    # Backend buttons
    elif 'QPushButton("💾 应用设置")' in line:
        lines[i] = line.replace('"💾 应用设置"', 't("ctx_btn_save_backend")')
        changed += 1; print(f'L{i}: btn_save_backend')
    elif 'QPushButton("🧪 测试连通")' in line:
        lines[i] = line.replace('"🧪 测试连通"', 't("ctx_btn_test_conn")')
        changed += 1; print(f'L{i}: btn_test_conn')
    elif 'QPushButton("🔄 拉取模型列表")' in line:
        lines[i] = line.replace('"🔄 拉取模型列表"', 't("ctx_btn_fetch_models")')
        changed += 1; print(f'L{i}: btn_fetch_models')

    # Workflow interaction
    elif 'QGroupBox("工作流交互")' in line:
        lines[i] = line.replace('"工作流交互"', 't("ctx_workflow_interaction")')
        changed += 1; print(f'L{i}: workflow_interaction')

    # Proactive panel
    elif 'QCheckBox("🎯 启用主动嗅探")' in line:
        lines[i] = line.replace('"🎯 启用主动嗅探"', 't("ctx_proactive_switch")')
        changed += 1; print(f'L{i}: proactive_switch')
    elif 'QGroupBox("每日主动次数")' in line:
        lines[i] = line.replace('"每日主动次数"', 't("ctx_daily_count")')
        changed += 1; print(f'L{i}: daily_count')
    elif 'cv.addRow("次数:",' in line:
        lines[i] = line.replace('"次数:"', 't("ctx_count_label")')
        changed += 1; print(f'L{i}: count_label')
    elif 'cv.addRow("", self.proactive_status)' in line:
        # Insert label text before proactive_status
        lines[i] = line.replace(
            'cv.addRow("", self.proactive_status)',
            'cv.addRow(t("ctx_proactive_status"), self.proactive_status)'
        )
        changed += 1; print(f'L{i}: proactive_status_row')
    elif 'QGroupBox("用户档案（驱动话题主题）")' in line:
        lines[i] = line.replace('"用户档案（驱动话题主题）"', 't("ctx_profile_gb")')
        changed += 1; print(f'L{i}: profile_gb')
    elif 'pv.addRow("爱好:",' in line:
        lines[i] = line.replace('"爱好:"', 't("ctx_profile_hobbies")')
        changed += 1; print(f'L{i}: profile_hobbies')
    elif 'pv.addRow("兴趣:",' in line:
        lines[i] = line.replace('"兴趣:"', 't("ctx_profile_interests")')
        changed += 1; print(f'L{i}: profile_interests')
    elif 'pv.addRow("学习:",' in line:
        lines[i] = line.replace('"学习:"', 't("ctx_profile_learning")')
        changed += 1; print(f'L{i}: profile_learning')
    elif 'pv.addRow("工作:",' in line:
        lines[i] = line.replace('"工作:"', 't("ctx_profile_work")')
        changed += 1; print(f'L{i}: profile_work')
    elif 'pv.addRow("行为关键词:",' in line:
        lines[i] = line.replace('"行为关键词:"', 't("ctx_profile_keywords")')
        changed += 1; print(f'L{i}: profile_keywords')

    # Proactive history
    elif 'QGroupBox("最近问过的问题")' in line:
        lines[i] = line.replace('"最近问过的问题"', 't("ctx_history_gb")')
        changed += 1; print(f'L{i}: history_gb')
    elif 'QPushButton("💡 现在生成一个")' in line:
        lines[i] = line.replace('"💡 现在生成一个"', 't("ctx_btn_now")')
        changed += 1; print(f'L{i}: btn_now')
    elif 'QPushButton("🧹 清空历史")' in line:
        lines[i] = line.replace('"🧹 清空历史"', 't("ctx_btn_clear")')
        changed += 1; print(f'L{i}: btn_clear')

    # Log panel
    elif 'QPushButton("🧹 清空")' in line and 'log_view.clear' in line:
        lines[i] = line.replace('"🧹 清空"', 't("ctx_btn_clear_log")')
        changed += 1; print(f'L{i}: btn_clear_log')

    # Spinbox suffixes
    elif 'setSuffix(" 秒")' in line:
        lines[i] = line.replace('" 秒"', 't("ctx_seconds_suffix")')
        changed += 1; print(f'L{i}: seconds_suffix')
    elif 'setSuffix(" 次/天")' in line:
        lines[i] = line.replace('" 次/天"', 't("ctx_count_suffix")')
        changed += 1; print(f'L{i}: count_suffix')

txt = '\n'.join(lines)
Path('context_tab.py').write_text(txt, encoding='utf-8')
print(f'Done. {changed} lines changed.')
