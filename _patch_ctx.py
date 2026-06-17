# -*- coding: utf-8 -*-
"""Patch context_tab.py: replace hardcoded Chinese UI strings with t() calls."""
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')

# Step 1: Add missing i18n keys
txt = Path('i18n.py').read_text(encoding='utf-8')

NEW_KEYS = [
    # context_tab new keys
    ("ctx_master_switch", "\ud83d\udfe2 \u542f\u7528\u4e0a\u4e0b\u6587\u611f\u77e5", "Enable AI Awareness"),
    ("ctx_status_stopped", "\u5df2\u505c\u6b62", "Stopped"),
    ("ctx_status_running", "\ud83d\udfe2 \u8fd0\u884c\u4e2d", "Running"),
    ("ctx_tab_sensor", "\ud83c\udf00 \u611f\u77e5\u884c\u4e3a", "Sensors"),
    ("ctx_tab_chat", "\ud83d\udcac AI \u5bf9\u8bdd", "AI Chat"),
    ("ctx_tab_rules", "\ud83d\udccb \u5616\u89c9\u89c4\u5219", "Sniff Rules"),
    ("ctx_tab_blacklist", "\ud83d\udd2b \u8fdb\u7a0b\u9ed1\u540d\u5355", "Process Blacklist"),
    ("ctx_tab_backend", "\u2699\ufe0f \u540e\u7aef", "Backend"),
    ("ctx_tab_proactive", "\ud83c\udfaf \u4e3b\u52a8\u5616\u89c9", "Proactive"),
    ("ctx_tab_log", "\ud83d\udcca \u65e5\u5fd7", "Log"),
    ("ctx_sensor_box", "\u611f\u901a\u5668\uff08\u591a\u9009\uff09", "Sensors (multi-select)"),
    ("ctx_chk_clipboard", "\ud83d\udccb \u526a\u8d34\u677f\u76d1\u542c\uff08\u63a8\u8350\u5f00\u542c\uff0c\u96f6\u5f00\u9500\uff09", "Clipboard monitor"),
    ("ctx_chk_window", "\ud83d\ude3f \u524d\u53f0\u7a97\u53e3\u5207\u6362\u76d1\u542c", "Foreground window monitor"),
    ("ctx_chk_file", "\ud83d\udcc1 \u6587\u4ef6\u7cfb\u7edf\u76d1\u89c6\uff08\u624b\u52a8\u6dfb\u52a0\u76ee\u5f55\uff09", "File system monitor"),
    ("ctx_chk_process", "\u2699\ufe0f \u8fdb\u7a0b\u542f\u52a8\/\u9000\u51fa\u76d1\u542c\uff08\u914d\u5408\u4e3b\u52a8\u5616\u89c9\u7528\u6237\u6863\u6848\u89e6\u53d1\uff09", "Process start/exit monitor"),
    ("ctx_file_watch_path", "\u6587\u4ef6\u76d1\u89c6\u8def\u5f84", "File watch paths"),
    ("ctx_btn_add_dir", "\u2795 \u6dfb\u52a0\u76ee\u5f55", "Add Directory"),
    ("ctx_btn_rm_dir", "\u2796 \u79fb\u9664\u9009\u4e2d", "Remove Selected"),
    ("ctx_btn_test_clipboard", "\ud83e\uddea \u6d4b\u8bd5\u526a\u8d34\u677f\u6349\u53d6", "Test Clipboard"),
    ("ctx_btn_test_toast", "\ud83d\udcac \u6d4b\u8bd5\u6c14\u6ce1", "Test Toast"),
    ("ctx_btn_clear_toasts", "\ud83e\uddf9 \u6e05\u9664\u6240\u6709\u6c14\u6ce1", "Clear All Toasts"),
    ("ctx_clipboard_hint", "\ud83d\udca1 \u53ea\u6709\u5f53\u526a\u8d34\u677f\u5185\u5bb9\u547d\u4e2d\u4e0b\u65b9\u4efb\u4e00\u89c4\u5219\u65f6\uff0c\u624d\u4f1a\u88ab\u53d1\u9001\u5230 AI \u63a8\u7406\u3002\n\u53d6\u6d88\u52fe\u9009\u53ef\u7981\u7528\u5bf9\u5e94\u89c4\u5219\u3002", "Only matching clipboard content is sent to AI."),
    ("ctx_learning_settings", "\u5b66\u4e60\u89c4\u5219\u8bbe\u7f6e", "Learning Rules"),
    ("ctx_default_trans_lang", "\u9ed8\u8ba4\u7ffb\u8bd1\u8bed\u8a00:", "Default translation:"),
    ("ctx_rule_tip", "\u52fe\u9009\u89c4\u5219\u540e\uff1a\u68c0\u6d4b\u5230\u82f1\u6587 \u2192 \u63a8\u9001 AI \u7ffb\u8bd1\uff1b\u68c0\u6d4b\u5230\u5b66\u672f\u8bcd\u6c47 \u2192 \u63a8\u9001 AI \u89e3\u91ca\u3002", "English to AI translation; academic terms to AI explanation."),
    ("ctx_rule_tip_label", "\u8bf4\u660e:", "Note:"),
    ("ctx_custom_rule", "\u6dfb\u52a0\u81ea\u5b9a\u4e49\u89c4\u5219", "Add Custom Rule"),
    ("ctx_rule_name", "\u540d\u79f0:", "Name:"),
    ("ctx_rule_pattern", "\u6b63\u5219:", "Pattern:"),
    ("ctx_btn_add_rule", "\u2795 \u6dfb\u52a0", "Add"),
    ("ctx_btn_rm_rule", "\u2796 \u5220\u9664\u9009\u4e2d", "Remove"),
    ("ctx_blacklist_hint", "\ud83d\udee1\ufe0f \u9ed1\u540d\u5355\u4e2d\u7684\u8fdb\u7a0b\u7edd\u5bf9\u4e0d\u4f1a\u88ab\u611f\u77e5\u3002\n\u5bc6\u7801\u7ba1\u7406\u5668\u3001SSH \u79c1\u94a5\u5de5\u5177\u7b49\u5efa\u8bae\u52a0\u5165\u3002", "Blacklisted processes never sensed."),
    ("ctx_add_process", "\u6dfb\u52a0\u8fdb\u7a0b", "Add Process"),
    ("ctx_backend_title", "AI \u540e\u7aef", "AI Backend"),
    ("ctx_backend_type", "\u540e\u7aef\u7c7b\u578b:", "Backend type:"),
    ("ctx_btn_save_backend", "\ud83d\udcbe \u5e94\u7528\u8bbe\u7f6e", "Apply Settings"),
    ("ctx_btn_test_conn", "\ud83d\udd0c \u6d4b\u8bd5\u8fde\u63a5", "Test Connection"),
    ("ctx_btn_fetch_models", "\ud83d\udd04 \u62c9\u53d6\u6a21\u578b\u5217\u8868", "Fetch Model List"),
    ("ctx_workflow_interaction", "\u5de5\u4f5c\u6d41\u4ea4\u4e92", "Workflow Interaction"),
    ("ctx_proactive_hint2", "\u300a\u6ce8\u610f\u300b\u95ee\u9898\u4f1a\u50cf\u804a\u5929\u4e00\u6837\u5728\u53f3\u4e0b\u89d2\u6d6e\u73b0\u6c14\u6ce1\uff0c\u53ef\u4ee5\u70b9\u51fb\u4e92\u52a8\u6216\u5ffd\u7565 5 \u79d2\u540e\u81ea\u52a8\u6d88\u5931\u3002", "Questions appear as bubbles in bottom-right corner."),
    ("ctx_proactive_switch", "\ud83c\udfaf \u542f\u7528\u4e3b\u52a8\u5616\u89c9", "Enable Proactive Sniff"),
    ("ctx_daily_count", "\u6bcf\u65e5\u4e3b\u52a8\u6b21\u6570", "Daily proactive count"),
    ("ctx_proactive_status", "\u72b6\u6001:", "Status:"),
    ("ctx_profile_gb", "\u7528\u6237\u6863\u6848\uff08\u9a71\u52a8\u8bdd\u9898\u4e3b\u9898\uff09", "User Profile"),
    ("ctx_profile_hobbies", "\u7231\u597d:", "Hobbies:"),
    ("ctx_profile_interests", "\u5174\u8da3:", "Interests:"),
    ("ctx_profile_learning", "\u5b66\u4e60:", "Learning:"),
    ("ctx_profile_work", "\u5de5\u4f5c:", "Work:"),
    ("ctx_profile_keywords", "\u884c\u4e3a\u5173\u952e\u8bcd:", "Behavior Keywords:"),
    ("ctx_kw_hint", "\ud83d\udca1 \u5f53\u68c0\u6d4b\u5230\u7a97\u53e3\/\u8fdb\u7a0b\u540d\u5305\u542b\u8fd9\u4e9b\u5173\u952e\u8bcd\u65f6\uff0c\u7acb\u5373\u63a8\u9001\u76f8\u5173\u8bdd\u9898\uff085\u5206\u949f\/\u6b21\u51b7\u5374\uff09", "When window/process matches keywords, push topic immediately."),
    ("ctx_history_gb", "\u6700\u8fd1\u95ee\u8fc7\u7684\u95ee\u9898", "Recent Questions"),
    ("ctx_btn_now", "\ud83d\udca1 \u73b0\u5728\u751f\u6210\u4e00\u4e2a", "Generate Now"),
    ("ctx_btn_clear", "\ud83e\uddf9 \u6e05\u7a7a\u5386\u53f2", "Clear History"),
    ("ctx_proactive_hint", "\ud83d\udca1 \u5f00\u542f\u540e\uff0c\u8fdb\u7a0b\u4e8b\u4ef6\u4f1a\u6309\u300c\u4e3b\u52a8\u5616\u89c9\u6863\u6848\u300d\u89c4\u5219\u89e6\u53d1 AI \u5206\u6790\u3002\n\u9700\u8981\u540c\u65f6\u5f00\u542f\u4e0a\u65b9\u300c\u8fdb\u7a0b\u76d1\u542c\u300d\u590d\u9009\u6846\u3002", "When enabled, process events trigger AI analysis."),
    ("ctx_master_on", "\ud83d\udfe2 \u5df2\u542f\u7528", "Enabled"),
    ("ctx_master_off", "\ud83d\udd34 \u5df2\u505c\u7528", "Disabled"),
    ("ctx_count_suffix", "\u6b21/\u5929", " /day"),
    ("ctx_seconds_suffix", "\u79d2", " sec"),
    ("ctx_log_count", "\u6761\u8bb0\u5f55", "records"),
    ("ctx_btn_clear_log", "\ud83e\uddf9 \u6e05\u7a7a", "Clear"),
    ("ctx_system_log", "[\u7cfb\u7edf] \u4e0a\u4e0b\u6587\u611f\u77e5\u5df2\u542f\u52a8\uff0c\u542f\u7528\u6a21\u5f0f: {modes}", "[System] AI Awareness started, modes: {modes}"),
    ("ctx_system_stopped", "[\u7cfb\u7edf] \u4e0a\u4e0b\u6587\u611f\u77e5\u5df2\u505c\u6b62", "[System] AI Awareness stopped"),
    ("ctx_proactive_started", "[\u4e3b\u52a8\u5616\u89c9] \u5df2\u542f\u52a8 ({count}\u6b21/\u5929)", "[Proactive] Started ({count}/day)"),
    ("ctx_proactive_stopped", "[\u4e3b\u52a8\u5616\u89c9] \u5df2\u505c\u6b62", "[Proactive] Stopped"),
]

added = 0
for key, zh, en in NEW_KEYS:
    zh_line = f'    {key!r}: {zh!r},\n'
    en_line = f'    {key!r}: {en!r},\n'
    if f'{key!r}:' in txt:
        print(f'SKIP: {key}')
        continue
    zh_start = txt.find('_STRINGS_ZH: dict[str, str] = {')
    en_start = txt.find('_STRINGS_EN: dict[str, str] = {')
    zh_section = txt[zh_start:en_start]
    last_brace_in_zh = zh_section.rfind('}')
    zh_dict_end = zh_start + last_brace_in_zh
    txt = txt[:zh_dict_end] + zh_line + txt[zh_dict_end:]
    en_section = txt[en_start:]
    last_brace_in_en = en_section.rfind('}')
    en_dict_end = en_start + last_brace_in_en
    txt = txt[:en_dict_end] + en_line + txt[en_dict_end:]
    added += 1
    print(f'ADD: {key}')

Path('i18n.py').write_text(txt, encoding='utf-8')
print(f'Added {added} keys to i18n.py')
