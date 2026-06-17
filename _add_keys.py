# -*- coding: utf-8 -*-
"""Add new i18n keys to i18n.py - pure ASCII source."""
import sys as s
s.stdout.reconfigure(encoding='utf-8')
from pathlib import Path

NEW_KEYS = [
    ("ctx_sensor_box", "\u611f\u901a\u5668\uff08\u591a\u9009\uff09", "Sensors (multi-select)"),
    ("ctx_chk_clipboard", "\ud83d\udccb \u526a\u8d34\u677f\u76d1\u542c\uff08\u63a8\u8350\u5f00\u542c\uff0c\u96f6\u5f00\u9500\uff09", "Clipboard monitor"),
    ("ctx_chk_window", "\ud83d\ude3f \u524d\u53f0\u7a97\u53e3\u5207\u6362\u76d1\u542c", "Foreground window monitor"),
    ("ctx_chk_file", "\ud83d\udcc1 \u6587\u4ef6\u7cfb\u7edf\u76d1\u89c6\uff08\u624b\u52a8\u6dfb\u52a0\u76ee\u5f55\uff09", "File system monitor"),
    ("ctx_chk_process", "\u2699\ufe0f \u8fdb\u7a0b\u542f\u52a8\/\u9000\u51fa\u76d1\u542c\uff08\u914d\u5408\u4e3b\u52a8\u5616\u89c9\u7528\u6237\u6863\u6848\u89e6\u53d1\uff09", "Process start/exit monitor"),
    ("ctx_file_watch_path", "\u6587\u4ef6\u76d1\u89c6\u8def\u5f84", "File watch paths"),
    ("ctx_btn_add_dir", "\u2795 \u6dfb\u52a0\u76ee\u5f55", "Add Directory"),
    ("ctx_btn_rm_dir", "\u2796 \u79fb\u9664\u9009\u4e2d", "Remove Selected"),
    ("ctx_btn_test_clipboard", "\ud83e\uddea \u6d4b\u8bd5\u526a\u8d34\u677f\u6349\u53d6", "Test Clipboard Capture"),
    ("ctx_btn_test_toast", "\ud83d\udcac \u6d4b\u8bd5\u6c14\u6ce1", "Test Toast"),
    ("ctx_btn_clear_toasts", "\ud83e\uddf9 \u6e05\u9664\u6240\u6709\u6c14\u6ce1", "Clear All Toasts"),
    ("ctx_clipboard_hint", "\ud83d\udca1 \u53ea\u6709\u5f53\u526a\u8d34\u677f\u5185\u5bb9\u547d\u4e2d\u4e0b\u65b9\u4efb\u4e00\u89c4\u5219\u65f6\uff0c\u624d\u4f1a\u88ab\u53d1\u9001\u5230 AI \u63a8\u7406\u3002\n\u53d6\u6d88\u52fe\u9009\u53ef\u7981\u7528\u5bf9\u5e94\u89c4\u5219\u3002", "Only clipboard content matching a rule is sent to AI. Uncheck to disable."),
    ("ctx_learning_settings", "\u5b66\u4e60\u89c4\u5219\u8bbe\u7f6e", "Learning Rules Settings"),
    ("ctx_default_trans_lang", "\u9ed8\u8ba4\u7ffb\u8bd1\u8bed\u8a00:", "Default translation language:"),
    ("ctx_rule_tip", "\u52fe\u9009\u89c4\u5219\u540e\uff1a\u68c0\u6d4b\u5230\u82f1\u6587 \u2192 \u63a8\u9001 AI \u7ffb\u8bd1\uff1b\u68c0\u6d4b\u5230\u5b66\u672f\u8bcd\u6c47 \u2192 \u63a8\u9001 AI \u89e3\u91ca\u3002", "Enabled: English to AI translation; academic terms to AI explanation."),
    ("ctx_rule_tip_label", "\u8bf4\u660e:", "Note:"),
    ("ctx_custom_rule", "\u6dfb\u52a0\u81ea\u5b9a\u4e49\u89c4\u5219", "Add Custom Rule"),
    ("ctx_rule_name", "\u540d\u79f0:", "Name:"),
    ("ctx_rule_pattern", "\u6b63\u5219:", "Pattern:"),
    ("ctx_btn_add_rule", "\u2795 \u6dfb\u52a0", "Add"),
    ("ctx_btn_rm_rule", "\u2796 \u5220\u9664\u9009\u4e2d", "Remove Selected"),
    ("ctx_blacklist_hint", "\ud83d\udee1\ufe0f \u9ed1\u540d\u5355\u4e2d\u7684\u8fdb\u7a0b\u7edd\u5bf9\u4e0d\u4f1a\u88ab\u611f\u77e5\u3002\n\u5bc6\u7801\u7ba1\u7406\u5668\u3001SSH \u79c1\u94a5\u5de5\u5177\u7b49\u5efa\u8bae\u52a0\u5165\u3002", "Blacklisted processes never sensed. Password managers, SSH tools recommended."),
    ("ctx_add_process", "\u6dfb\u52a0\u8fdb\u7a0b", "Add Process"),
    ("ctx_backend_title", "AI \u540e\u7aef", "AI Backend"),
    ("ctx_btn_save_backend", "\ud83d\udcbe \u4fdd\u5b58\u8bbe\u7f6e", "Save Settings"),
    ("ctx_btn_test_conn", "\ud83d\udd0c \u6d4b\u8bd5\u8fde\u63a5", "Test Connection"),
    ("ctx_log_box", "\ud83d\udcca AI \u611f\u77e5\u6d3b\u52a8\u65e5\u5fd7", "AI Awareness Activity Log"),
    ("ctx_proactive_hint", "\ud83d\udca1 \u5f00\u542f\u540e\uff0c\u8fdb\u7a0b\u4e8b\u4ef6\u4f1a\u6309\u300c\u4e3b\u52a8\u5616\u89c9\u6863\u6848\u300d\u89c4\u5219\u89e6\u53d1 AI \u5206\u6790\u3002\n\u9700\u8981\u540c\u65f6\u5f00\u542f\u4e0a\u65b9\u300c\u8fdb\u7a0b\u76d1\u542c\u300d\u590d\u9009\u6846\u3002", "When enabled, process events trigger AI analysis. Requires Process monitor."),
    ("ctx_master_on", "\ud83d\udfe2 \u5df2\u542f\u7528", "Enabled"),
    ("ctx_master_off", "\ud83d\udd34 \u5df2\u505c\u7528", "Disabled"),
    ("ql_info_selected", "\u9009\u4e2d\u4e00\u4e2a\u5feb\u6377\u65b9\u5f0f", "Select a shortcut"),
    ("ql_radio_direct", "\ud83d\ude80 \u76f4\u63a5\u542f\u52a8 (Popen,\u6700\u4f18\u5148,\u6700\u7a33\u5b9a)", "Direct Launch (Popen, fastest, most stable)"),
    ("ql_radio_desktop", "\ud83d\uddb1\ufe0f \u9f20\u6807\u53cc\u51fb\u684c\u9762\u56fe\u6807 (\u5907\u9009)", "Double-click Desktop Icon (fallback)"),
    ("ql_radio_shell", "\u2699\ufe0f Shell \u542f\u52a8 (cmd /c,\u7279\u6b8a\u573a\u666f)", "Shell Launch (cmd /c, special cases)"),
    ("ql_radio_image", "\ud83d\udcf8 \u57fa\u4e8e\u56fe\u6807\u8bc6\u522b\u7684\u5750\u6807\u70b9\u51fb", "Image Match / Coord Click"),
    ("ql_chk_notepad", "\u542f\u52a8\u540e\u6a21\u62df\u952e\u9f20\u4ea4\u4e92 (\u4ec5\u8bb0\u4e8b\u672c\u751f\u6548)", "Simulate keyboard/mouse after launch (notepad only)"),
    ("ql_chk_show_desktop", "\u6267\u884c\u524d\u5148\u663e\u793a\u684c\u9762 (Win+D)", "Show desktop before execution (Win+D)"),
    ("ql_btn_bind_mode", "\ud83d\udcbe \u7ed1\u5b9a\u5f53\u524d\u542f\u52a8\u65b9\u5f0f", "Bind Current Launch Mode"),
    ("ql_btn_clear_bind", "\ud83d\uddd1 \u6e05\u9664\u7ed1\u5b9a", "Clear Binding"),
    ("ql_coord_status", "\ud83d\udccd \u5750\u6807\u72b6\u6001:", "Coord Status:"),
    ("ql_coord_not_set", "\u672a\u8bbe\u7f6e", "Not set"),
    ("ql_search_placeholder", "\ud83d\udd0d \u641c\u7d22\u5feb\u6377\u65b9\u5f0f...", "Search shortcuts..."),
    ("ql_btn_refresh", "\ud83d\udd04 \u5237\u65b0\u5217\u8868", "Refresh List"),
    ("ql_btn_add_custom", "\u2795 \u6dfb\u52a0\u81ea\u5b9a\u4e49", "Add Custom"),
    ("ql_btn_show_desktop", "\ud83d\uddd4 Win+D", "Win+D"),
    ("ql_label_log", "\ud83d\udddc \u64cd\u4f5c\u65e5\u5fd7", "Activity Log"),
    ("ql_no_target", "(\u672a\u9009\u4e2d)", "(none)"),
    ("ql_no_template", "\u672a\u8bbe\u7f6e", "Not set"),
    ("ql_click_double", "\u53cc\u51fb", "Double"),
    ("ql_click_single", "\u5355\u51fb", "Single"),
    ("ql_click_right", "\u53f3\u51fb", "Right"),
]

def add_keys():
    txt = Path('i18n.py').read_text(encoding='utf-8')
    added = 0
    for key, zh, en in NEW_KEYS:
        zh_line = f'    {key!r}: {zh!r},\n'
        en_line = f'    {key!r}: {en!r},\n'
        if f'{key!r}:' in txt:
            print(f'SKIP: {key}')
            continue
        zh_pat = '_STRINGS_ZH: dict[str, str] = {'
        zh_pos = txt.find(zh_pat)
        zh_end = txt.find('}', zh_pos + len(zh_pat))
        txt = txt[:zh_end] + zh_line + txt[zh_end:]
        en_pat = '_STRINGS_EN: dict[str, str] = {'
        en_pos = txt.find(en_pat)
        en_end = txt.find('}', en_pos + len(en_pat))
        txt = txt[:en_end] + en_line + txt[en_end:]
        added += 1
        print(f'ADD: {key}')
    Path('i18n.py').write_text(txt, encoding='utf-8')
    print(f'Total added: {added}')

if __name__ == '__main__':
    add_keys()
