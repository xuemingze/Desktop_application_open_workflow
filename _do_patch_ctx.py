# -*- coding: utf-8 -*-
"""Patch context_tab.py: replace Chinese strings with t() calls."""
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')

txt = Path('context_tab.py').read_text(encoding='utf-8')

# All replacements: (old_string, new_string)
# We use a dict to avoid ordering issues
REPLS = {
    # Master switch and status
    '"\\U0001f7e2 \\u542f\\u7528\\u4e0a\\u4e0b\\u6587\\u611f\\u77e9"': 't("ctx_master_switch")',
    '"\\u5df2\\u505c\\u6b62"': 't("ctx_status_stopped")',
    '"\\U0001f7e2 \\u8fd0\\u884c\\u4e2d"': 't("ctx_status_running")',
    '"\\u26a0\\ufe0f \\u5df2\\u505c\\u6b62"': 't("ctx_status_stopped")',

    # Tab names
    '"\\U0001f500 \\u611f\\u77e9\\u884c\\u4e3a"': 't("ctx_tab_sensor")',
    '"\\U0001f4ac AI \\u5bf9\\u8bdd"': 't("ctx_tab_chat")',
    '"\\U0001f4cb \\u5616\\u89c9\\u89c4\\u5219"': 't("ctx_tab_rules")',
    '"\\U0001f72b \\u8fdb\\u7a0b\\u9ed1\\u540d\\u5355"': 't("ctx_tab_blacklist")',
    '"\\u2699\\ufe0f \\u540e\\u7aef"': 't("ctx_tab_backend")',
    '"\\U0001f3af \\u4e3b\\u52a8\\u5616\\u89c9"': 't("ctx_tab_proactive")',
    '"\\U0001f4ca \\u65e5\\u5fd7"': 't("ctx_tab_log")',

    # Sensor panel
    '"\\u611f\\u901a\\u5668\\uff08\\u591a\\u9009\\uff09"': 't("ctx_sensor_box")',
    '"\\U0001f4cb \\u526a\\u8d34\\u677f\\u76d1\\u542c\\uff08\\u63a8\\u8350\\u5f00\\u542c\\uff0c\\u96f6\\u5f00\\u9500\\uff09"': 't("ctx_chk_clipboard")',
    '"\\U0001f309 \\u524d\\u53f0\\u7a97\\u53e3\\u5207\\u6362\\u76d1\\u542c"': 't("ctx_chk_window")',
    '"\\U0001f4c1 \\u6587\\u4ef6\\u7cfb\\u7edf\\u76d1\\u89c6\\uff08\\u624b\\u52a8\\u6dfb\\u52a0\\u76ee\\u5f55\\uff09"': 't("ctx_chk_file")',
    '"\\u2699\\ufe0f \\u8fdb\\u7a0b\\u542f\\u52a8\\/\\u9000\\u51fa\\u76d1\\u542c\\uff08\\u914d\\u5408\\u4e3b\\u52a8\\u5616\\u89c9\\u7528\\u6237\\u6863\\u6848\\u89e6\\u53d1\\uff09"': 't("ctx_chk_process")',
    '"\\u6587\\u4ef6\\u76d1\\u89c6\\u8def\\u5f84"': 't("ctx_file_watch_path")',
    '"\\u2795 \\u6dfb\\u52a0\\u76ee\\u5f55"': 't("ctx_btn_add_dir")',
    '"\\u2796 \\u79fb\\u9664\\u9009\\u4e2d"': 't("ctx_btn_rm_dir")',
    '"\\U0001f9ea \\u6d4b\\u8bd5\\u526a\\u8d34\\u677f\\u6349\\u53d6"': 't("ctx_btn_test_clipboard")',
    '"\\U0001f4ac \\u6d4b\\u8bd5\\u6c14\\u6ce1"': 't("ctx_btn_test_toast")',
    '"\\U0001f9f9 \\u6e05\\u9664\\u6240\\u6709\\u6c14\\u6ce1"': 't("ctx_btn_clear_toasts")',

    # Rules panel
    '"\\U0001f4a1 \\u53ea\\u6709\\u5f53\\u526a\\u8d34\\u677f\\u5185\\u5bb9\\u547d\\u4e2d\\u4e0b\\u65b9\\u4efb\\u4e00\\u89c4\\u5219\\u65f6\\uff0c\\u624d\\u4f1a\\u88ab\\u53d1\\u9001\\u5230 AI \\u63a8\\u7406\\u3002\\n\\u53d6\\u6d88\\u52fe\\u9009\\u53ef\\u7981\\u7528\\u5bf9\\u5e94\\u89c4\\u5219\\u3002"': 't("ctx_clipboard_hint")',
    '"\\u5b66\\u4e60\\u89c4\\u5219\\u8bbe\\u7f6e"': 't("ctx_learning_settings")',
    '"\\u9ed8\\u8ba4\\u7ffb\\u8bd1\\u8bed\\u8a00:"': 't("ctx_default_trans_lang")',
    '"\\u52fe\\u9009\\u89c4\\u5219\\u540e\\uff1a\\u68c0\\u6d4b\\u5230\\u82f1\\u6587 \\u2192 \\u63a8\\u9001 AI \\u7ffb\\u8bd1\\uff1b\\u68c0\\u6d4b\\u5230\\u5b66\\u672f\\u8bcd\\u6c47 \\u2192 \\u63a8\\u9001 AI \\u89e3\\u91ca\\u3002"': 't("ctx_rule_tip")',
    '"\\u8bf4\\u660e:"': 't("ctx_rule_tip_label")',
    '"\\u6dfb\\u52a0\\u81ea\\u5b9a\\u4e49\\u89c4\\u5219"': 't("ctx_custom_rule")',
    '"\\u540d\\u79f0:"': 't("ctx_rule_name")',
    '"\\u6b63\\u5219:"': 't("ctx_rule_pattern")',
    '"\\u2795 \\u6dfb\\u52a0"': 't("ctx_btn_add_rule")',
    '"\\u2796 \\u5220\\u9664\\u9009\\u4e2d"': 't("ctx_btn_rm_rule")',

    # Blacklist panel
    '"\\U0001f6e1\\ufe0f \\u9ed1\\u540d\\u5355\\u4e2d\\u7684\\u8fdb\\u7a0b\\u7edd\\u5bf9\\u4e0d\\u4f1a\\u88ab\\u611f\\u77e5\\u3002\\n\\u5bc6\\u7801\\u7ba1\\u7406\\u5668\\u3001SSH \\u79c1\\u94a5\\u5de5\\u5177\\u7b49\\u5efa\\u8bae\\u52a0\\u5165\\u3002"': 't("ctx_blacklist_hint")',
    '"\\u6dfb\\u52a0\\u8fdb\\u7a0b"': 't("ctx_add_process")',

    # Backend panel
    '"AI \\u540e\\u7aef"': 't("ctx_backend_title")',
    '"\\u540e\\u7aef\\u7c7b\\u578b:"': 't("ctx_backend_type")',
    '"\\U0001f4be \\u5e94\\u7528\\u8bbe\\u7f6e"': 't("ctx_btn_save_backend")',
    '"\\U0001f50c \\u6d4b\\u8bd5\\u8fde\\u63a5"': 't("ctx_btn_test_conn")',
    '"\\U0001f504 \\u62c9\\u53d6\\u6a21\\u578b\\u5217\\u8868"': 't("ctx_btn_fetch_models")',
    '"\\u5de5\\u4f5c\\u6d41\\u4ea4\\u4e92"': 't("ctx_workflow_interaction")',
    '"\\u300a\\u6ce8\\u610f\\u300b\\u95ee\\u9898\\u4f1a\\u50cf\\u804a\\u5929\\u4e00\\u6837\\u5728\\u53f3\\u4e0b\\u89d2\\u6d6e\\u73b0\\u6c14\\u6ce1\\uff0c\\u53ef\\u4ee5\\u70b9\\u51fb\\u4e92\\u52a8\\u6216\\u5ffd\\u7565 5 \\u79d2\\u540e\\u81ea\\u52a8\\u6d88\\u5931\\u3002"': 't("ctx_proactive_hint2")',

    # Backend combo items
    '"EchoBackend (\\u672c\\u5730\\u6d4b\\u8bd5\\uff0c\\u4e0d\\u53d1\\u8bf7\\u6c42)"': 't("ctx_backend_echo")',
    '"OpenAI \\u5171\\u5bb9 (Hermes\\/Qianlia\\/\\u672c\\u5730\\u6a21\\u578b)"': 't("ctx_backend_openai")',

    # Backend placeholder hints
    '"\\u4f8b\\u5982\\uff1a\\u4e2d\\u6587 \\/ English \\/ \\u65e5\\u672c\\u8a9e"': 't("ctx_placeholder_trans_lang")',
    '"\\u89c4\\u5219\\u540d\\u79f0\\uff0c\\u5982 Git \\u4ed3\\u5e93\\u8def\\u5f84"': 't("ctx_placeholder_rule_name")',
    '"\\u6b63\\u5219\\u8868\\u8fbe\\u5f0f\\uff0c\\u5982 ^git@"': 't("ctx_placeholder_pattern")',
    '"\\u8fdb\\u7a0b\\u540d\\uff0c\\u5982 1Password.exe"': 't("ctx_placeholder_process")',
    '"\\u53ef\\u9009\\uff1aTavily API Key\\uff0c\\u8054\\u7f51\\u641c\\u7d22\\u4f18\\u5148\\u4f7f\\u7528 Tavily"': 't("ctx_placeholder_tavily")',
    '"\\u4f8b\\u5982\\uff1a\\u5c71\\u4e0a\\u3001\\u6444\\u5f71\\u3001\\u68a6\\u6885"': 't("ctx_placeholder_hobbies")',
    '"\\u4f8b\\u5982\\uff1aAI\\u3001\\u52a0\\u5bc6\\u8d27\\u5e01\\u3001\\u72ec\\u7acb\\u6e38\\u620f"': 't("ctx_placeholder_interests")',
    '"\\u4f8b\\u5982\\uff1aRust \\u7f16\\u7a0b\\u3001\\u7cfb\\u7edf\\u8bbe\\u8ba1"': 't("ctx_placeholder_learning")',
    '"\\u4f8b\\u5982\\uff1a\\u684c\\u9762\\u81ea\\u52a8\\u5316\\u3001Python \\u540e\\u7aef"': 't("ctx_placeholder_work")',
    '"\\u4f8b\\u5982\\uff1a\\u9e23\\u6f6e,\\u539f\\u795e,\\u5d29\\u574f\\u661f\\u7a57\\u94c1\\u9053"': 't("ctx_placeholder_keywords")',

    # Proactive panel
    '"\\U0001f3af \\u542f\\u7528\\u4e3b\\u52a8\\u5616\\u89c9"': 't("ctx_proactive_switch")',
    '"\\u6bcf\\u65e5\\u4e3b\\u52a8\\u6b21\\u6570"': 't("ctx_daily_count")',
    '"\\u72b6\\u6001:"': 't("ctx_proactive_status")',
    '"\\u7528\\u6237\\u6863\\u6848\\uff08\\u9a71\\u52a8\\u8bdd\\u9898\\u4e3b\\u9898\\uff09"': 't("ctx_profile_gb")',
    '"\\u7231\\u597d:"': 't("ctx_profile_hobbies")',
    '"\\u5174\\u8da3:"': 't("ctx_profile_interests")',
    '"\\u5b66\\u4e60:"': 't("ctx_profile_learning")',
    '"\\u5de5\\u4f5c:"': 't("ctx_profile_work")',
    '"\\u884c\\u4e3a\\u5173\\u952e\\u8bcd:"': 't("ctx_profile_keywords")',
    '"\\U0001f4a1 \\u5f53\\u68c0\\u6d4b\\u5230\\u7a97\\u53e3\\/\\u8fdb\\u7a0b\\u540d\\u5305\\u542b\\u8fd9\\u4e9b\\u5173\\u952e\\u8bcd\\u65f6\\uff0c\\u7acb\\u5373\\u63a8\\u9001\\u76f8\\u5173\\u8bdd\\u9898\\uff085\\u5206\\u949f\\/\\u6b21\\u51b7\\u5374\\uff09"': 't("ctx_kw_hint")',
    '"\\u6700\\u8fd1\\u95ee\\u8fc7\\u7684\\u95ee\\u9898"': 't("ctx_history_gb")',
    '"\\U0001f4a1 \\u73b0\\u5728\\u751f\\u6210\\u4e00\\u4e2a"': 't("ctx_btn_now")',
    '"\\U0001f9f9 \\u6e05\\u7a7a\\u5386\\u53f2"': 't("ctx_btn_clear")',

    # Log panel
    '"\\U0001f9f9 \\u6e05\\u7a7a"': 't("ctx_btn_clear_log")',
    '"0 \\u6761\\u8bb0\\u5f55"': 't("ctx_log_count", count=0)',
    '"1 \\u6761\\u8bb0\\u5f55"': 't("ctx_log_count", count=1)',
    '"{count} \\u6761\\u8bb0\\u5f55"': 't("ctx_log_count", count="{count}")',

    # Proactive hint
    '"\\U0001f4a1 \\u5f00\\u542f\\u540e\\uff0c\\u8fdb\\u7a0b\\u4e8b\\u4ef6\\u4f1a\\u6309\\u300c\\u4e3b\\u52a8\\u5616\\u89c9\\u6863\\u6848\\u300d\\u89c4\\u5219\\u89e6\\u53d1 AI \\u5206\\u6790\\u3002\\n\\u9700\\u8981\\u540c\\u65f6\\u5f00\\u542f\\u4e0a\\u65b9\\u300c\\u8fdb\\u7a0b\\u76d1\\u542c\\u300d\\u590d\\u9009\\u6846\\u3002"': 't("ctx_proactive_hint")',

    # Status labels in event handlers
    '"\\U0001f7e2 \\u8fd0\\u884c\\u4e2d"': 't("ctx_status_running")',
    '"\\u26aa \\u5df2\\u505c\\u6b62"': 't("ctx_status_stopped")',

    # Master on/off
    '"\\U0001f7e2 \\u5df2\\u542f\\u7528"': 't("ctx_master_on")',
    '"\\U0001f534 \\u5df2\\u505c\\u7528"': 't("ctx_master_off")',

    # Backend form labels
    '"Base URL:"': 't("ctx_base_url")',
    '"API Key:"': 't("ctx_api_key")',
    '"Model:"': 't("ctx_model")',
    '"\\u8d85\\u65f6:"': 't("ctx_timeout")',
    '"Tavily Key:"': 't("ctx_tavily_key")',
    '"\\u6b21\\/:\\u5929"': 't("ctx_count_suffix")',
    '" \\u79d2"': 't("ctx_seconds_suffix")',

    # Backend info
    '"\\u2022 \\u6c14\\u6ce1\\u70b9\\u51fb\\u540e\\u4f1a\\u8c03\\u7528 AI \\u63a8\\u8350\\u7684\\u5de5\\u5177\\uff08MCP \\u5de5\\u5177\\u6216\\u5de5\\u4f5c\\u6d41\\uff09\\n\\u2022 \\u5f53\\u524d\\u652f\\u6301\\u7684\\u5de5\\u5177\\uff1asearch_local_files \\/ run_workflow \\/ launch_shortcut\\n\\u2022 \\u63a8\\u8350\\u5de5\\u4f5c\\u6d41\\u9700\\u8981\\u5148\\u5728\\u300c\\u5de5\\u4f5c\\u6d41\\u300d\\u6807\\u7b7e\\u9875\\u521b\\u5efa\\n\\u2022 \\u6574\\u4e2a\\u8fc7\\u7a0b\\u53ef\\u5728\\u300c\\u65e5\\u5fd7\\u300d\\u6807\\u7b7e\\u9875\\u67e5\\u770b\\u5b9e\\u65f6\\u6d3b\\u52a8"': 't("ctx_workflow_info")',
}

# Apply replacements
for old, new in REPLS.items():
    if old in txt:
        txt = txt.replace(old, new)
        print(f'REPL: {old[:50]}...')
    else:
        print(f'NOT FOUND: {old[:50]}')

# Fix specific setText calls that use variables (can't use simple string replace)
# These need more careful handling
txt = txt.replace(
    'self.status_label.setText("\\U0001f7e2 \\u8fd0\\u884c\\u4e2d")',
    'self.status_label.setText(t("ctx_status_running"))'
)
txt = txt.replace(
    'self.status_label.setText("\\u26aa \\u5df2\\u505c\\u6b62")',
    'self.status_label.setText(t("ctx_status_stopped"))'
)
txt = txt.replace(
    'self.status_label.setText("\\u26a0\\ufe0f \\u5df2\\u505c\\u6b62")',
    'self.status_label.setText(t("ctx_status_stopped"))'
)

# Fix log count label
txt = txt.replace(
    'self.log_count_label.setText(f"{self.log_view.document().blockCount()} \\u6761\\u8bb0\\u5f55")',
    'self.log_count_label.setText(t("ctx_log_count", count=self.log_view.document().blockCount()))'
)

# Fix spinbox suffixes
txt = txt.replace('self.timeout_spin.setSuffix(" \\u79d2")', 'self.timeout_spin.setSuffix(t("ctx_seconds_suffix"))')
txt = txt.replace('self.daily_count_spin.setSuffix(" \\u6b21\\/\\u5929")', 'self.daily_count_spin.setSuffix(t("ctx_count_suffix"))')

# Fix proactive status
txt = txt.replace(
    'self.proactive_status.setText(f"\\u72b6\\u6001: {\\u6697\\u793a}");',
    'self.proactive_status.setText(t("ctx_proactive_status") + " " + \\u6697\\u793a)'
)
txt = txt.replace(
    'self.proactive_status.setText(f"\\u72b6\\u6001: {\\u6697\\u793a}")',
    'self.proactive_status.setText(t("ctx_proactive_status") + " " + \\u6697\\u793a)'
)

# Fix status bar setText in _on_master_toggle
txt = txt.replace(
    'self.status_label.setText("\\u26aa \\u5df2\\u505c\\u6b62")',
    'self.status_label.setText(t("ctx_status_stopped"))'
)

# Add t() import at top of file if not already there
if 'from i18n import t' not in txt:
    # Find first import line position
    lines = txt.split('\n')
    insert_at = 0
    for i, line in enumerate(lines):
        if line.startswith('from __future__'):
            insert_at = i + 1
        elif line.startswith('from ') or line.startswith('import '):
            insert_at = i + 1
    lines.insert(insert_at, 'from i18n import t')
    txt = '\n'.join(lines)
    print('Added: from i18n import t')

# Also fix combo items
txt = txt.replace(
    '"EchoBackend (\\u672c\\u5730\\u6d4b\\u8bd5\\uff0c\\u4e0d\\u53d1\\u8bf7\\u6c42)"',
    't("ctx_backend_echo")'
)
txt = txt.replace(
    '"OpenAI \\u5171\\u5bb9 (Hermes\\/Qianlia\\/\\u672c\\u5730\\u6a21\\u578b)"',
    't("ctx_backend_openai")'
)

Path('context_tab.py').write_text(txt, encoding='utf-8')
print('context_tab.py patched and saved')
